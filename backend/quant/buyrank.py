"""
Buy Rank: TOPSIS over the factor z-matrix, reported as a 1–100 percentile.

Why percentile and not the raw closeness coefficient: C* shifts with the
universe composition from day to day, so "0.62" means nothing stable. The
percentile across today's eligible universe does.
"""

from __future__ import annotations

import logging
import math
from datetime import date as DateType
from typing import Iterable

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from config import SECTOR_MAP, settings
from data.bars import load_bars
from data.db_utils import upsert_replace
from data.universe import sector_lookup, universe_tickers
from database import FactorScore
from quant.factors import FACTOR_NAMES, factor_panel

logger = logging.getLogger(__name__)

# Band thresholds (Strong / Good / Neutral) per Market Weather state.
BANDS = {
    "Sunny":  (80, 60, 40),
    "Cloudy": (85, 70, 50),
    None:     (80, 60, 40),      # until Weather ships, behave as Sunny
}


def band_for(rank: int, regime: str | None) -> str:
    if regime == "Stormy":
        return "Watch" if rank >= 90 else "Wait"
    strong, good, neutral = BANDS.get(regime, BANDS[None])
    if rank >= strong:
        return "Strong"
    if rank >= good:
        return "Good"
    if rank >= neutral:
        return "Neutral"
    return "Weak"


# ── TOPSIS ─────────────────────────────────────────────────────────────────

def topsis_closeness(Z: np.ndarray, weights: np.ndarray) -> np.ndarray:
    """
    Z: n × k matrix of *benefit-oriented* criteria (higher = better).
    weights: k non-negative weights. Returns C* in [0, 1] per row.
    NaNs are treated as neutral (0 after z-scoring).
    """
    Z = np.nan_to_num(np.asarray(Z, dtype=float), nan=0.0)
    if Z.ndim != 2 or Z.shape[0] == 0:
        return np.array([])
    norms = np.sqrt((Z ** 2).sum(axis=0))
    norms[norms == 0] = 1.0
    V = (Z / norms) * weights
    best, worst = V.max(axis=0), V.min(axis=0)
    d_best = np.sqrt(((V - best) ** 2).sum(axis=1))
    d_worst = np.sqrt(((V - worst) ** 2).sum(axis=1))
    return d_worst / (d_best + d_worst + 1e-12)


def _oriented(z: pd.DataFrame, weights: dict[str, float]) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Flip penalty factors so every TOPSIS criterion is a benefit."""
    names = [f for f in FACTOR_NAMES if weights.get(f, 0.0) != 0.0]
    cols, w = [], []
    for f in names:
        wf = weights[f]
        cols.append(z[f].to_numpy() * (1.0 if wf > 0 else -1.0))
        w.append(abs(wf))
    return np.column_stack(cols), np.asarray(w), names


def rank_cross_section(
    z: pd.DataFrame,
    eligible: pd.Series,
    weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    """
    For every date in `z`, compute TOPSIS on eligible rows and the percentile
    Buy Rank. Returns a DataFrame indexed like `z` with columns:
    topsis, buy_rank, plus one `c_<factor>` contribution column per factor.
    """
    weights = weights or settings.FACTOR_WEIGHTS
    out = pd.DataFrame(index=z.index)
    out["topsis"] = np.nan
    out["buy_rank"] = np.nan
    for f in FACTOR_NAMES:
        out[f"c_{f}"] = z[f] * weights.get(f, 0.0)

    dates = z.index.get_level_values("date").unique()
    for d in dates:
        idx = z.index.get_level_values("date") == d
        mask = idx & eligible.to_numpy()
        n = int(mask.sum())
        if n < 5:
            continue
        Z, w, _ = _oriented(z[mask], weights)
        c = topsis_closeness(Z, w)
        pct = pd.Series(c).rank(method="average", pct=True).to_numpy()
        rank = np.clip(np.ceil(pct * 100.0), 1, 100).astype(int)
        out.loc[mask, "topsis"] = c
        out.loc[mask, "buy_rank"] = rank
    return out


# ── Orchestration ──────────────────────────────────────────────────────────

def compute_scores(
    bars: pd.DataFrame,
    regime: str | None = None,
    only_dates: Iterable[DateType] | None = None,
) -> pd.DataFrame:
    """
    Full pipeline on a bars DataFrame. Returns one row per (date, ticker)
    with everything FactorScore stores. `only_dates` limits the output rows
    (the panel is still computed on full history).
    """
    raw, z, eligible = factor_panel(bars)
    if z.empty:
        return pd.DataFrame()
    ranked = rank_cross_section(z, eligible)

    df = pd.concat(
        [raw[["close"]], z.add_prefix("z_"), ranked, eligible.rename("eligible")],
        axis=1,
    )
    df["regime"] = regime
    if only_dates is not None:
        wanted = {pd.Timestamp(d) for d in only_dates}
        df = df[df.index.get_level_values("date").isin(wanted)]
    return df


def _rows_for_db(df: pd.DataFrame, raw: pd.DataFrame, sectors: dict[str, str]) -> list[dict]:
    rows: list[dict] = []
    for (d, t), r in df.iterrows():
        if pd.isna(r["buy_rank"]):
            continue
        rank = int(r["buy_rank"])
        rows.append({
            "ticker": t,
            "date": pd.Timestamp(d).date(),
            "buy_rank": rank,
            "topsis": float(r["topsis"]),
            "band": band_for(rank, r["regime"]),
            "regime": r["regime"],
            "sector": sectors.get(t) or SECTOR_MAP.get(t, "Unknown"),
            "close": float(r["close"]),
            "raw": {k: _num(v) for k, v in raw.loc[(d, t)].items() if k != "n_obs"},
            "z": {f: _num(r[f"z_{f}"]) for f in FACTOR_NAMES},
            "contributions": {f: _num(r[f"c_{f}"]) for f in FACTOR_NAMES},
            "eligible": int(bool(r["eligible"])),
        })
    return rows


def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else round(f, 6)


def compute_and_store(
    db: Session,
    as_of: DateType | None = None,
    backfill_days: int = 0,
    regime: str | None = None,
) -> int:
    """
    Compute Buy Rank for the latest bar date (or `as_of`) and store it.
    `backfill_days > 0` also stores that many earlier trading days, which is
    what research and the history sparkline need.
    """
    tickers = universe_tickers(db)
    bars = load_bars(db, tickers=tickers)
    if bars.empty:
        logger.warning("compute_and_store: no bars loaded")
        return 0

    raw, z, eligible = factor_panel(bars)
    ranked = rank_cross_section(z, eligible)
    df = pd.concat(
        [raw[["close"]], z.add_prefix("z_"), ranked, eligible.rename("eligible")], axis=1
    )
    df["regime"] = regime

    all_dates = sorted(df.index.get_level_values("date").unique())
    if as_of is not None:
        all_dates = [d for d in all_dates if d.date() <= as_of]
    if not all_dates:
        return 0
    keep = all_dates[-(backfill_days + 1):]
    df = df[df.index.get_level_values("date").isin(keep)]

    rows = _rows_for_db(df, raw, sector_lookup(db))
    written = upsert_replace(db, FactorScore.__table__, rows, ["ticker", "date"])
    db.commit()
    logger.info("Buy Rank stored: %d rows across %d date(s), latest %s",
                written, len(keep), keep[-1].date())
    return written
