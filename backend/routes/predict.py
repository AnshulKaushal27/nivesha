"""Predictions API: latest model run, per-stock odds."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import FactorScore, ModelRun, Prediction, get_db
from quant.predict import MODEL_KIND

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
