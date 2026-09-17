"""
Cross-sectional factor engine for Buy Rank.

Everything is vectorised over a (date × ticker) price panel so the same code
produces today's scores and a multi-year history for research/factor_eval.py.

Pipeline
--------
bars (long)  →  panels (close, volume)  →  raw components (per date, per ticker)
             →  cross-sectional z-scores (winsorised ±3σ)  →  composite factors

Factor sign convention: every composite is oriented so that *higher is better*
except `overheat`, which is a penalty and carries a negative weight in config.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from config import settings

# Composite factors that feed TOPSIS, in a fixed order.
FACTOR_NAMES: list[str] = [
    "mom_12_1", "mom_6_1", "trend", "low_vol", "liquidity", "vol_conf", "overheat",
]

# Raw components computed from the panel. Some composites average two of these.
RAW_COMPONENTS: list[str] = [
    "mom_12_1", "mom_6_1", "trend_frac", "trend_slope", "neg_vol_60",
    "log_turnover_20", "vol_conf", "ret_5d", "rsi_excess",
]

WINSOR_SIGMA = 3.0
TRADING_DAYS = 252


# ── Panels ─────────────────────────────────────────────────────────────────

def bars_to_panels(bars: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Long bars → (close, volume) wide panels indexed by date, columns = tickers.
    `bars` needs columns: ticker, date, close, volume.
    """
    if bars.empty:
        empty = pd.DataFrame()
        return empty, empty
    b = bars.copy()
    b["date"] = pd.to_datetime(b["date"])
    close = b.pivot_table(index="date", columns="ticker", values="close", aggfunc="last").sort_index()
    volume = b.pivot_table(index="date", columns="ticker", values="volume", aggfunc="last").sort_index()
    volume = volume.reindex(columns=close.columns).fillna(0.0)
    return close, volume


# ── Indicators (vectorised across columns) ─────────────────────────────────

def rsi_wilder(close: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    return rsi.where(loss > 0, 100.0)


# ── Raw components ─────────────────────────────────────────────────────────

def compute_raw(close: pd.DataFrame, volume: pd.DataFrame) -> pd.DataFrame:
    """
    Return a long DataFrame indexed by (date, ticker) with RAW_COMPONENTS plus
    the bookkeeping columns needed for eligibility and display:
    close, turnover_med20, rsi14, n_obs.
    """
    logp = np.log(close)
    rets = logp.diff()

    sma50 = close.rolling(50, min_periods=50).mean()
    above = (close > sma50).astype(float).where(sma50.notna())
    turnover = close * volume

    comp = {
        "mom_12_1":        logp.shift(21) - logp.shift(TRADING_DAYS),
        "mom_6_1":         logp.shift(21) - logp.shift(126),
        "trend_frac":      above.rolling(60, min_periods=40).mean(),
        "trend_slope":     sma50 / sma50.shift(20) - 1.0,
        "neg_vol_60":      -(rets.rolling(60, min_periods=40).std() * np.sqrt(TRADING_DAYS)),
        "log_turnover_20": np.log(turnover.rolling(20, min_periods=15).median().replace(0, np.nan)),
        "vol_conf":        (volume.rolling(20, min_periods=15).mean()
                            / volume.rolling(60, min_periods=40).mean().replace(0, np.nan)).clip(upper=3.0),
        "ret_5d":          logp - logp.shift(5),
        "rsi_excess":      (rsi_wilder(close) - 70.0).clip(lower=0.0),
        # bookkeeping
        "close":           close,
        "turnover_med20":  turnover.rolling(20, min_periods=15).median(),
        "rsi14":           rsi_wilder(close),
        "n_obs":           close.notna().cumsum(),
    }
    long = pd.concat({k: v.stack(future_stack=True) for k, v in comp.items()}, axis=1)
    long.index.names = ["date", "ticker"]
    return long.dropna(subset=["close"])


# ── Eligibility ────────────────────────────────────────────────────────────

def eligibility(raw: pd.DataFrame) -> pd.Series:
    """Boolean per (date, ticker): enough history, liquid enough, not a penny stock."""
    min_turnover = settings.MIN_TURNOVER_CR * 1e7      # crore → rupees
    return (
        (raw["n_obs"] >= settings.MIN_HISTORY_ROWS)
        & (raw["close"] >= settings.MIN_PRICE)
        & (raw["turnover_med20"] >= min_turnover)
        & raw["mom_12_1"].notna()
        & raw["neg_vol_60"].notna()
    )


# ── Cross-sectional normalisation ──────────────────────────────────────────

def zscore_by_date(values: pd.DataFrame, winsor: float = WINSOR_SIGMA) -> pd.DataFrame:
    """Per-date z-score, winsorised at ±winsor σ. NaNs stay NaN."""
    g = values.groupby(level="date")
    mean = g.transform("mean")
    std = g.transform("std").replace(0, np.nan)
    z = (values - mean) / std
    return z.clip(lower=-winsor, upper=winsor)


def compute_factors(raw: pd.DataFrame, eligible: pd.Series | None = None) -> pd.DataFrame:
    """
    Raw components → composite factor z-scores (FACTOR_NAMES).
    z-scores are computed across the *eligible* cross-section only, so
    illiquid names cannot distort the distribution, but every row gets a value
    where its inputs exist (for display of ineligible stocks).
    """
    if eligible is None:
        eligible = eligibility(raw)

    comps = raw[RAW_COMPONENTS]
    stats_src = comps[eligible]
    g = stats_src.groupby(level="date")
    mean = g.mean()
    std = g.std().replace(0, np.nan)

    dates = comps.index.get_level_values("date")
    z = (comps - mean.reindex(dates).to_numpy()) / std.reindex(dates).to_numpy()
    z = z.clip(lower=-WINSOR_SIGMA, upper=WINSOR_SIGMA)

    out = pd.DataFrame(index=raw.index)
    out["mom_12_1"]  = z["mom_12_1"]
    out["mom_6_1"]   = z["mom_6_1"]
    out["trend"]     = 0.5 * z["trend_frac"] + 0.5 * z["trend_slope"]
    out["low_vol"]   = z["neg_vol_60"]
    out["liquidity"] = z["log_turnover_20"]
    out["vol_conf"]  = z["vol_conf"]
    out["overheat"]  = 0.5 * z["ret_5d"] + 0.5 * z["rsi_excess"]
    return out[FACTOR_NAMES]


def factor_panel(bars: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Convenience: bars → (raw, factors_z, eligible)."""
    close, volume = bars_to_panels(bars)
    if close.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.Series(dtype=bool)
    raw = compute_raw(close, volume)
    eligible = eligibility(raw)
    z = compute_factors(raw, eligible)
    return raw, z, eligible
