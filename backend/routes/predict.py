"""Predictions API: latest model run, per-stock odds."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import settings
from database import FactorScore, ModelRun, Prediction, PredictionScore, get_db
from quant.predict import FEATURES, HORIZON, MODEL_KIND, TRAIN_STRIDE, next_maturity

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
    return {"run": run.meta, "count": total, "items": [_item(p, ranks.get(p.ticker)) for p in rows]}


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
