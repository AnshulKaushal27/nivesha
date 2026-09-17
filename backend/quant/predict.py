"""
Predictions: which *type* of stock tends to rise next, from up to 20 years of history.

This is a probability model, not a crystal ball, and the page says so.

Target      P(stock beats the universe median return over the next 63 trading days)
Features    the seven Buy Rank factor z-scores, the stock's sector, and two
            market-state features (median 12-1 momentum, breadth above 50-DMA)
Model       HistGradientBoostingClassifier (scikit-learn), walk-forward by year,
            training labels always end `HORIZON` days before the test year starts
Reports     out-of-sample AUC / accuracy / top-decile hit rate per fold, a
            calibration table, permutation importance, "type of stock" profiles,
            sector outlook with historical continuation rate, and 20-year band
            base rates for the Buy Rank bands.
"""

from __future__ import annotations

import logging
import math
from datetime import date as DateType

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.inspection import permutation_importance
from sklearn.metrics import accuracy_score, roc_auc_score
from sqlalchemy.orm import Session

from config import settings
from data.bars import load_bars
from data.db_utils import upsert_replace
from data.universe import sector_lookup, universe_tickers
from database import DailyBar, ModelRun, Prediction, PredictionScore
from quant.buyrank import band_for, rank_cross_section
from quant.factors import FACTOR_NAMES, bars_to_panels, compute_factors, compute_raw, eligibility

logger = logging.getLogger(__name__)

HORIZON = 63                       # ≈ 3 months
BASE_RATE_HORIZONS = (21, 63, 126)
MARKET_FEATURES = ["mkt_mom", "breadth"]
FEATURES = FACTOR_NAMES + MARKET_FEATURES + ["sector"]
MIN_TRAIN_YEARS = 3
TRAIN_STRIDE = 5                   # use every 5th date for training (weekly) — same information, 5× faster
MODEL_KIND = f"beat_market_{HORIZON}d"

FEATURE_LABEL = {
    "mom_12_1": "12-month momentum", "mom_6_1": "6-month momentum", "trend": "trend quality",
    "low_vol": "calmness (low volatility)", "liquidity": "liquidity", "vol_conf": "volume confirmation",
    "overheat": "overheat penalty", "mkt_mom": "market momentum", "breadth": "market breadth", "sector": "sector",
}


# ── Dataset ────────────────────────────────────────────────────────────────

def build_dataset(bars: pd.DataFrame, sectors: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Returns (df, close) where df is indexed by (date, ticker) with FEATURES,
    topsis, fwd_{h} for each base-rate horizon, excess, y. Only eligible rows.
    """
    close, volume = bars_to_panels(bars)
    raw = compute_raw(close, volume)
    eligible = eligibility(raw)
    z = compute_factors(raw, eligible)
    ranked = rank_cross_section(z, eligible)

    logp = np.log(close)
    fwd = {}
    for h in sorted(set(BASE_RATE_HORIZONS) | {HORIZON}):
        s = (logp.shift(-h) - logp).stack(future_stack=True)
        s.index.names = ["date", "ticker"]
        fwd[f"fwd_{h}"] = s

    df = pd.concat([z, ranked[["topsis", "buy_rank"]], pd.DataFrame(fwd)], axis=1)
    df = df[eligible.reindex(df.index).fillna(False).astype(bool)]

    # market-state features from the eligible cross-section
    el_raw = raw[eligible]
    mkt = pd.DataFrame({
        "mkt_mom": el_raw["mom_12_1"].groupby(level="date").median(),
        "breadth": el_raw["trend_frac"].groupby(level="date").mean(),
    })
    dates = df.index.get_level_values("date")
    for c in MARKET_FEATURES:
        df[c] = mkt[c].reindex(dates).to_numpy()

    tickers = df.index.get_level_values("ticker")
    df["sector"] = pd.Categorical([sectors.get(t, "Unknown") for t in tickers])

    med = df[f"fwd_{HORIZON}"].groupby(level="date").transform("median")
    df["excess"] = df[f"fwd_{HORIZON}"] - med
    df["y"] = (df["excess"] > 0).astype(float).where(df["excess"].notna())
    return df, close


def _model() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=200,
        l2_regularization=1.0, categorical_features="from_dtype",
        early_stopping=True, validation_fraction=0.1, n_iter_no_change=20, random_state=7,
    )


def _stride(df: pd.DataFrame, stride: int) -> pd.DataFrame:
    dates = df.index.get_level_values("date").unique().sort_values()
    keep = set(dates[::stride])
    return df[df.index.get_level_values("date").isin(keep)]


# ── Walk-forward evaluation ────────────────────────────────────────────────

def walk_forward(df: pd.DataFrame) -> tuple[list[dict], pd.DataFrame]:
    labelled = df.dropna(subset=["y"])
    all_dates = labelled.index.get_level_values("date")
    trading_days = pd.Index(df.index.get_level_values("date").unique().sort_values())
    years = sorted(set(all_dates.year))
    folds: list[dict] = []
    oos_parts: list[pd.DataFrame] = []

    for yr in years:
        test_start = pd.Timestamp(yr, 1, 1)
        if test_start <= all_dates.min() + pd.DateOffset(years=MIN_TRAIN_YEARS):
            continue
        # labels of training rows must be fully known before the test year starts
        pos = trading_days.searchsorted(test_start)
        if pos - HORIZON <= 0:
            continue
        train_cut = trading_days[pos - HORIZON - 1]
        train = _stride(labelled[all_dates <= train_cut], TRAIN_STRIDE)
        test = labelled[(all_dates >= test_start) & (all_dates < pd.Timestamp(yr + 1, 1, 1))]
        if len(train) < 5_000 or len(test) < 1_000:
            continue
        m = _model().fit(train[FEATURES], train["y"])
        p = m.predict_proba(test[FEATURES])[:, 1]
        t = test.assign(p=p)
        top = t[t["p"] >= t["p"].quantile(0.9)]
        folds.append({
            "year": int(yr), "n_train": int(len(train)), "n_test": int(len(test)),
            "auc": float(roc_auc_score(t["y"], t["p"])),
            "accuracy": float(accuracy_score(t["y"], (t["p"] > 0.5).astype(float))),
            "top_decile_hit": float(top["y"].mean()),
            "top_decile_excess_pct": float((math.e ** top["excess"].mean() - 1) * 100),
        })
        oos_parts.append(t[["p", "y", "excess"]])
        logger.info("fold %s: auc %.3f acc %.3f top-decile hit %.3f", yr, folds[-1]["auc"], folds[-1]["accuracy"], folds[-1]["top_decile_hit"])

    oos = pd.concat(oos_parts) if oos_parts else pd.DataFrame(columns=["p", "y", "excess"])
    return folds, oos


def calibration(oos: pd.DataFrame, bins: int = 5) -> list[dict]:
    if oos.empty:
        return []
    edges = np.linspace(0, 1, bins + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        b = oos[(oos["p"] >= lo) & (oos["p"] < hi if hi < 1 else oos["p"] <= hi)]
        if len(b) == 0:
            continue
        out.append({"bin_lo": round(float(lo), 2), "bin_hi": round(float(hi), 2),
                    "predicted": float(b["p"].mean()), "actual": float(b["y"].mean()), "n": int(len(b))})
    return out


# ── Interpretation ─────────────────────────────────────────────────────────

def profiles(latest: pd.DataFrame) -> list[dict]:
    """For each factor: mean predicted odds for the top vs bottom quintile today."""
    out = []
    for f in FACTOR_NAMES + MARKET_FEATURES[:0]:
        s = latest[f].dropna()
        if len(s) < 25:
            continue
        hi = latest.loc[s[s >= s.quantile(0.8)].index, "p"].mean()
        lo = latest.loc[s[s <= s.quantile(0.2)].index, "p"].mean()
        out.append({"feature": f, "label": FEATURE_LABEL[f],
                    "high_prob": float(hi), "low_prob": float(lo), "edge": float(hi - lo)})
    return sorted(out, key=lambda r: -abs(r["edge"]))


def sector_outlook(latest: pd.DataFrame, close: pd.DataFrame, sectors: dict[str, str]) -> list[dict]:
    """Current odds by sector, 6-month relative strength, and how often a top-3 sector stayed ahead."""
    # sector equal-weight log-return indices
    rets = np.log(close).diff()
    sec_of = pd.Series({t: sectors.get(t, "Unknown") for t in close.columns})
    sec_ret = rets.T.groupby(sec_of).mean().T           # date × sector
    cum = sec_ret.cumsum()
    rs6 = cum - cum.shift(126)
    fwd = cum.shift(-HORIZON) - cum

    # continuation: on monthly dates, was a top-3 sector by rs6 above the sector median over the next horizon?
    monthly = rs6.dropna(how="all").iloc[::21]
    hits, n = 0, 0
    for d, row in monthly.iterrows():
        if d not in fwd.index or fwd.loc[d].isna().all():
            continue
        top3 = row.dropna().nlargest(3).index
        med = fwd.loc[d].median()
        hits += int((fwd.loc[d, top3] > med).sum())
        n += len(top3)
    continuation = hits / n if n else float("nan")

    last_rs = rs6.iloc[-1]
    by = latest.groupby(latest["sector"].astype(str), observed=True)
    out = []
    for sec, g in by:
        out.append({
            "sector": sec, "n": int(len(g)), "avg_prob": float(g["p"].mean()),
            "top_stock": str(g["p"].idxmax()[1]) if len(g) else None,
            "rel_strength_6m_pct": float((math.e ** last_rs.get(sec, np.nan) - 1) * 100) if pd.notna(last_rs.get(sec, np.nan)) else None,
        })
    out.sort(key=lambda r: -r["avg_prob"])
    ranked = sorted([r for r in out if r["rel_strength_6m_pct"] is not None], key=lambda r: -r["rel_strength_6m_pct"])
    for i, r in enumerate(ranked):
        r["rs_rank"] = i + 1
    return [{**r, "top3_continuation_rate": continuation} for r in out]


def band_base_rates(df: pd.DataFrame) -> list[dict]:
    """Over the whole sample: how did each Buy Rank band do afterwards?"""
    d = df.dropna(subset=["buy_rank"]).copy()
    d["band"] = [band_for(int(r), None) for r in d["buy_rank"]]
    out = []
    for h in BASE_RATE_HORIZONS:
        col = f"fwd_{h}"
        med = d[col].groupby(level="date").transform("median")
        beat = (d[col] > med)
        for band, g in d.groupby("band"):
            v = g[col].dropna()
            if len(v) < 200:
                continue
            out.append({
                "band": band, "horizon": h, "n": int(len(v)),
                "hit_rate": float((v > 0).mean()),
                "median_return_pct": float((math.e ** v.median() - 1) * 100),
                "beat_market_rate": float(beat.loc[v.index].mean()),
            })
    order = {"Strong": 0, "Good": 1, "Neutral": 2, "Weak": 3}
    return sorted(out, key=lambda r: (r["horizon"], order.get(r["band"], 9)))


# ── Orchestration ──────────────────────────────────────────────────────────

def train_and_store(db: Session, min_years_history: int = 3) -> dict:
    tickers = universe_tickers(db)
    sectors = sector_lookup(db)
    start = DateType(1990, 1, 1)
    if settings.PREDICTOR_MAX_YEARS > 0:            # small instances: cap the training window
        start = DateType.today().replace(year=DateType.today().year - settings.PREDICTOR_MAX_YEARS)
    bars = load_bars(db, tickers=tickers, start=start)
    if bars.empty:
        raise RuntimeError("No bars in the database")
    logger.info("Predictor: %d bars, %d tickers, %s → %s", len(bars), bars["ticker"].nunique(), bars["date"].min().date(), bars["date"].max().date())

    df, close = build_dataset(bars, sectors)
    span_years = (df.index.get_level_values("date").max() - df.index.get_level_values("date").min()).days / 365.25
    if span_years < min_years_history:
        raise RuntimeError(f"Only {span_years:.1f} years of eligible history; need {min_years_history}")

    folds, oos = walk_forward(df)

    # final model on everything with known labels; predict the latest cross-section
    labelled = _stride(df.dropna(subset=["y"]), TRAIN_STRIDE)
    model = _model().fit(labelled[FEATURES], labelled["y"])
    last_date = df.index.get_level_values("date").max()
    latest = df.xs(last_date, level="date", drop_level=False).copy()
    latest["p"] = model.predict_proba(latest[FEATURES])[:, 1]
    latest["pct_rank"] = np.clip(np.ceil(latest["p"].rank(pct=True) * 100), 1, 100).astype(int)

    # permutation importance on the most recent OOS-like slice (last 250 dates, sampled)
    recent = df.dropna(subset=["y"])
    recent = recent[recent.index.get_level_values("date") >= recent.index.get_level_values("date").unique().sort_values()[-250]]
    recent = recent.sample(min(len(recent), 40_000), random_state=7)
    imp = permutation_importance(model, recent[FEATURES], recent["y"], n_repeats=3, random_state=7, scoring="roc_auc")
    importance = sorted(
        [{"feature": f, "label": FEATURE_LABEL[f], "importance": float(v)} for f, v in zip(FEATURES, imp.importances_mean)],
        key=lambda r: -r["importance"],
    )

    oos_summary = {
        "auc": float(roc_auc_score(oos["y"], oos["p"])) if len(oos) else None,
        "accuracy": float(accuracy_score(oos["y"], (oos["p"] > 0.5).astype(float))) if len(oos) else None,
        "top_decile_hit": float(np.mean([f["top_decile_hit"] for f in folds])) if folds else None,
        "top_decile_excess_pct": float(np.mean([f["top_decile_excess_pct"] for f in folds])) if folds else None,
        "n_oos": int(len(oos)),
    }

    meta = {
        "kind": MODEL_KIND, "as_of": str(last_date.date()), "horizon_days": HORIZON,
        "history_start": str(df.index.get_level_values("date").min().date()),
        "history_years": round(span_years, 1),
        "n_rows": int(len(df)), "n_train_rows": int(len(labelled)), "n_tickers": int(df.index.get_level_values("ticker").nunique()),
        "folds": folds, "oos": oos_summary, "calibration": calibration(oos),
        "importance": importance, "profiles": profiles(latest),
        "sectors": sector_outlook(latest, close, sectors),
        "band_base_rates": band_base_rates(df),
        "market_now": {"mkt_mom_pct": float((math.e ** latest["mkt_mom"].iloc[0] - 1) * 100), "breadth": float(latest["breadth"].iloc[0])},
    }

    rows = []
    for (d, t), r in latest.iterrows():
        rows.append({
            "ticker": t, "date": d.date(), "horizon": HORIZON, "prob_up": float(r["p"]), "pct_rank": int(r["pct_rank"]),
            "sector": str(r["sector"]), "close": float(close.loc[d, t]) if pd.notna(close.loc[d, t]) else None,
            "features": {f: (None if pd.isna(r[f]) else round(float(r[f]), 4)) for f in FACTOR_NAMES + MARKET_FEATURES},
        })
    upsert_replace(db, Prediction.__table__, rows, ["ticker", "date", "horizon"])
    db.add(ModelRun(kind=MODEL_KIND, as_of=last_date.date(), meta=meta))
    db.commit()
    logger.info("Predictor stored: %d predictions for %s; OOS AUC %.3f", len(rows), last_date.date(), oos_summary["auc"] or float("nan"))
    return meta


# ── Self-maintenance: live scoring and automatic retraining ────────────────

def score_matured(db: Session) -> list[dict]:
    """
    For every prediction batch whose horizon has passed, compare the odds with
    what actually happened and store a PredictionScore row. Idempotent.
    """
    from sqlalchemy import distinct, select

    trading_days = [d for (d,) in db.execute(select(distinct(DailyBar.date)).order_by(DailyBar.date)).all()]
    if not trading_days:
        return []
    idx = {d: i for i, d in enumerate(trading_days)}
    batches = db.execute(select(distinct(Prediction.date), Prediction.horizon)
                         .group_by(Prediction.date, Prediction.horizon).order_by(Prediction.date)).all()
    already = {(r.run_date, r.horizon) for r in db.execute(select(PredictionScore)).scalars().all()}

    out = []
    for run_date, horizon in batches:
        if (run_date, horizon) in already or run_date not in idx:
            continue
        j = idx[run_date] + horizon
        if j >= len(trading_days):
            continue                                   # not matured yet
        matured_on = trading_days[j]
        preds = db.execute(select(Prediction.ticker, Prediction.prob_up)
                           .where(Prediction.date == run_date, Prediction.horizon == horizon)).all()
        tickers = [t for t, _ in preds]
        c0 = dict(db.execute(select(DailyBar.ticker, DailyBar.close).where(DailyBar.date == run_date, DailyBar.ticker.in_(tickers))).all())
        c1 = dict(db.execute(select(DailyBar.ticker, DailyBar.close).where(DailyBar.date == matured_on, DailyBar.ticker.in_(tickers))).all())
        rows = [(p, math.log(c1[t] / c0[t])) for t, p in preds if t in c0 and t in c1 and c0[t] and c1[t]]
        if len(rows) < 50:
            continue
        df = pd.DataFrame(rows, columns=["p", "ret"])
        med = df["ret"].median()
        df["y"] = (df["ret"] > med).astype(int)
        top = df[df["p"] >= df["p"].quantile(0.9)]
        auc = float(roc_auc_score(df["y"], df["p"])) if df["y"].nunique() > 1 else None
        score = PredictionScore(
            run_date=run_date, horizon=horizon, matured_on=matured_on, n=int(len(df)), auc=auc,
            accuracy=float(((df["p"] > 0.5).astype(int) == df["y"]).mean()),
            top_decile_hit=float(top["y"].mean()),
            top_decile_excess_pct=float((math.e ** (top["ret"].mean() - med) - 1) * 100),
            median_return_pct=float((math.e ** med - 1) * 100),
        )
        db.add(score)
        out.append({"run_date": str(run_date), "matured_on": str(matured_on), "n": score.n, "auc": auc,
                    "top_decile_hit": score.top_decile_hit, "top_decile_excess_pct": score.top_decile_excess_pct})
        logger.info("Scored batch %s → %s: top-decile hit %.2f, excess %+.2f%%", run_date, matured_on, score.top_decile_hit, score.top_decile_excess_pct)
    db.commit()
    return out


def retrain_if_due(db: Session, force: bool = False) -> dict:
    """
    Retrain when there is no model, or the last training is older than
    PREDICTOR_RETRAIN_DAYS. Called nightly, so the model keeps learning from
    each new week of prices without anyone pressing a button.
    """
    from sqlalchemy import select

    last = db.execute(select(ModelRun).where(ModelRun.kind == MODEL_KIND)
                      .order_by(ModelRun.as_of.desc()).limit(1)).scalar_one_or_none()
    age = (DateType.today() - last.as_of).days if last else None
    due = force or last is None or age >= settings.PREDICTOR_RETRAIN_DAYS
    if not due:
        return {"retrained": False, "last_as_of": str(last.as_of), "age_days": age, "next_in_days": settings.PREDICTOR_RETRAIN_DAYS - age}
    meta = train_and_store(db)
    return {"retrained": True, "as_of": meta["as_of"], "oos": meta["oos"], "previous_as_of": str(last.as_of) if last else None}


def next_maturity(db: Session) -> dict | None:
    """When does the oldest unscored batch mature? (for the UI's 'first live result on …')"""
    from sqlalchemy import distinct, select

    scored = {(r.run_date, r.horizon) for r in db.execute(select(PredictionScore)).scalars().all()}
    batches = db.execute(select(distinct(Prediction.date), Prediction.horizon)
                         .group_by(Prediction.date, Prediction.horizon).order_by(Prediction.date)).all()
    pending = [(d, h) for d, h in batches if (d, h) not in scored]
    if not pending:
        return None
    d, h = pending[0]
    from datetime import timedelta
    approx = d + timedelta(days=int(h * 7 / 5) + 4)      # trading days → calendar, plus holidays
    return {"run_date": str(d), "horizon": h, "expected_on": str(approx), "pending_batches": len(pending)}
