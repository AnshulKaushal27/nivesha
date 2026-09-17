"""Predictions API: latest model run, per-stock odds."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import math

from config import settings
from database import DailyBar, FactorScore, ModelRun, Prediction, PredictionScore, get_db
from quant.predict import FEATURES, HORIZON, MODEL_KIND, TRAIN_STRIDE, next_maturity


def _closes_on(db: Session, on, tickers: list[str]) -> dict[str, float]:
    return dict(db.execute(select(DailyBar.ticker, DailyBar.close).where(DailyBar.date == on, DailyBar.ticker.in_(tickers))).all())


def _latest_bar_date(db: Session):
    return db.execute(select(func.max(DailyBar.date))).scalar()


def _so_far(db: Session, run_date, tickers: list[str]) -> tuple[dict[str, float], float | None, object]:
    """Per-ticker % move since the prediction date, and the median move across all predicted tickers."""
    latest = _latest_bar_date(db)
    if latest is None or latest <= run_date:
        return {}, None, latest
    c0, c1 = _closes_on(db, run_date, tickers), _closes_on(db, latest, tickers)
    moves = {t: (c1[t] / c0[t] - 1) * 100 for t in tickers if t in c0 and t in c1 and c0[t]}
    med = None
    if moves:
        vals = sorted(moves.values())
        med = vals[len(vals) // 2] if len(vals) % 2 else (vals[len(vals) // 2 - 1] + vals[len(vals) // 2]) / 2
    return moves, med, latest

router = APIRouter(prefix="/predict", tags=["predict"])


def _latest_run(db: Session) -> ModelRun | None:
    return db.execute(select(ModelRun).where(ModelRun.kind == MODEL_KIND)
                      .order_by(ModelRun.as_of.desc(), ModelRun.id.desc()).limit(1)).scalar_one_or_none()


def _item(p: Prediction, rank: int | None) -> dict:
    return {
        "ticker": p.ticker, "symbol": p.ticker.replace(".NS", ""), "date": str(p.date), "horizon": p.horizon,
        "prob_up": p.prob_up, "pct_rank": p.pct_rank, "sector": p.sector, "close": p.close,
        "buy_rank": rank, "features": p.features,
    }


@router.get("")
def latest(limit: int = Query(20, ge=1, le=600), offset: int = Query(0, ge=0),
           sector: str | None = None, db: Session = Depends(get_db)):
    run = _latest_run(db)
    if run is None:
        return {"run": None, "count": 0, "items": []}
    stmt = select(Prediction).where(Prediction.date == run.as_of, Prediction.horizon == run.meta["horizon_days"])
    if sector:
        stmt = stmt.where(Prediction.sector == sector)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar()
    rows = db.execute(stmt.order_by(Prediction.prob_up.desc()).offset(offset).limit(limit)).scalars().all()

    latest_rank_date = db.execute(select(func.max(FactorScore.date))).scalar()
    ranks = {}
    if latest_rank_date and rows:
        ranks = dict(db.execute(select(FactorScore.ticker, FactorScore.buy_rank)
                                .where(FactorScore.date == latest_rank_date, FactorScore.ticker.in_([r.ticker for r in rows]))).all())
    # progress since the prediction date: the stock's move vs the median predicted stock
    all_tickers = db.execute(select(Prediction.ticker).where(Prediction.date == run.as_of)).scalars().all()
    moves, market_med, latest = _so_far(db, run.as_of, all_tickers)
    items = []
    for p in rows:
        it = _item(p, ranks.get(p.ticker))
        it["so_far_pct"] = moves.get(p.ticker)
        it["market_so_far_pct"] = market_med
        it["beating_so_far"] = None if p.ticker not in moves or market_med is None else moves[p.ticker] > market_med
        items.append(it)
    return {"run": run.meta, "count": total, "as_of_prices": str(latest) if latest else None, "market_so_far_pct": market_med, "items": items}


@router.get("/{ticker}/track")
def track(ticker: str, db: Session = Depends(get_db)):
    """Prediction vs reality for one stock: indexed price path since the prediction date against the median predicted stock."""
    ticker = ticker.upper() if ticker.endswith(".NS") else f"{ticker.upper()}.NS"
    run = _latest_run(db)
    if run is None:
        raise HTTPException(404, "No prediction run yet")
    p = db.execute(select(Prediction).where(Prediction.ticker == ticker, Prediction.date == run.as_of)).scalars().first()
    if p is None:
        raise HTTPException(404, f"No prediction for {ticker}")
    all_tickers = db.execute(select(Prediction.ticker).where(Prediction.date == run.as_of)).scalars().all()
    rows = db.execute(select(DailyBar.date, DailyBar.ticker, DailyBar.close)
                      .where(DailyBar.date >= run.as_of, DailyBar.ticker.in_(all_tickers)).order_by(DailyBar.date)).all()
    by_date: dict = {}
    for d, t, c in rows:
        by_date.setdefault(d, {})[t] = c
    dates = sorted(by_date)
    base = by_date.get(run.as_of, {})
    series = []
    for d in dates:
        day = by_date[d]
        if ticker not in day or ticker not in base or not base[ticker]:
            continue
        rel = [day[t] / base[t] for t in day if t in base and base[t]]
        rel.sort()
        med = rel[len(rel) // 2] if rel else None
        series.append({"date": str(d), "stock": round(day[ticker] / base[ticker] * 100, 2), "market": round(med * 100, 2) if med else None})
    elapsed = max(0, len(series) - 1)
    last = series[-1] if series else None
    stock_pct = (last["stock"] - 100) if last else None
    market_pct = (last["market"] - 100) if last and last["market"] else None
    # a horizon-end marker in calendar terms for the chart
    from datetime import timedelta
    expected_end = run.as_of + timedelta(days=int(p.horizon * 7 / 5) + 4)
    return {
        "symbol": ticker.replace(".NS", ""), "prediction_date": str(run.as_of), "horizon_days": p.horizon,
        "odds_pct": round(p.prob_up * 100, 1), "pct_rank": p.pct_rank,
        "days_elapsed": elapsed, "days_total": p.horizon, "expected_end": str(expected_end),
        "stock_pct": None if stock_pct is None else round(stock_pct, 2), "market_pct": None if market_pct is None else round(market_pct, 2),
        "beating": None if stock_pct is None or market_pct is None else stock_pct > market_pct,
        "verdict": ("too early" if elapsed < 3 else "on track" if (stock_pct or 0) > (market_pct or 0) else "behind") if series else "no prices yet",
        "series": series,
    }


@router.get("/live")
def live(db: Session = Depends(get_db)):
    """Live scorecard: matured prediction batches vs what actually happened, plus the retrain policy."""
    rows = db.execute(select(PredictionScore).order_by(PredictionScore.run_date)).scalars().all()
    run = _latest_run(db)
    runs = db.execute(select(ModelRun.as_of).where(ModelRun.kind == MODEL_KIND).order_by(ModelRun.as_of.desc()).limit(12)).scalars().all()
    return {
        "scores": [{"run_date": str(r.run_date), "matured_on": str(r.matured_on), "horizon": r.horizon, "n": r.n, "auc": r.auc,
                    "accuracy": r.accuracy, "top_decile_hit": r.top_decile_hit, "top_decile_excess_pct": r.top_decile_excess_pct,
                    "median_return_pct": r.median_return_pct} for r in rows],
        "next_maturity": next_maturity(db),
        "training_history": [str(d) for d in runs],
        "model_card": {
            "algorithm": "HistGradientBoostingClassifier (scikit-learn), 300 boosting rounds, early stopping",
            "target": f"beats the NIFTY 500 median return over the next {HORIZON} trading days",
            "features": FEATURES,
            "validation": "walk-forward by calendar year; labels end 63 trading days before each test year",
            "training_stride_days": TRAIN_STRIDE,
            "retrain_policy": f"nightly check; retrains when the last training is older than {settings.PREDICTOR_RETRAIN_DAYS} days, plus a Saturday safety run",
            "last_trained": str(run.as_of) if run else None,
            "history_years": run.meta.get("history_years") if run else None,
            "n_train_rows": run.meta.get("n_train_rows") if run else None,
        },
    }


@router.get("/{ticker}")
def one(ticker: str, db: Session = Depends(get_db)):
    ticker = ticker.upper() if ticker.endswith(".NS") else f"{ticker.upper()}.NS"
    run = _latest_run(db)
    if run is None:
        raise HTTPException(404, "No prediction run yet")
    p = db.execute(select(Prediction).where(Prediction.ticker == ticker, Prediction.date == run.as_of)
                   .order_by(Prediction.horizon)).scalars().first()
    if p is None:
        raise HTTPException(404, f"No prediction for {ticker}")
    rank = db.execute(select(FactorScore.buy_rank).where(FactorScore.ticker == ticker)
                      .order_by(FactorScore.date.desc()).limit(1)).scalar()
    return {**_item(p, rank), "oos": run.meta.get("oos"), "history_years": run.meta.get("history_years")}
