"""Buy Rank API. Shapes are what the Rank page and the stock page render."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import FactorScore, get_db
from llm.explain import explain_rank

router = APIRouter(prefix="/rank", tags=["rank"])


def _latest_date(db: Session) -> date | None:
    return db.execute(select(func.max(FactorScore.date))).scalar()


def _item(s: FactorScore, full: bool = False) -> dict:
    d = {
        "ticker": s.ticker, "symbol": s.ticker.replace(".NS", ""), "date": str(s.date),
        "buy_rank": s.buy_rank, "band": s.band, "regime": s.regime, "sector": s.sector,
        "close": s.close, "topsis": s.topsis, "eligible": bool(s.eligible),
        "contributions": s.contributions,
    }
    if full:
        d.update({"z": s.z, "raw": s.raw})
    return d


@router.get("")
def list_rank(
    on: Optional[date] = Query(None, description="score date; defaults to latest"),
    limit: int = Query(50, ge=1, le=600),
    offset: int = Query(0, ge=0),
    sector: Optional[str] = None,
    band: Optional[str] = None,
    min_rank: int = Query(1, ge=1, le=100),
    db: Session = Depends(get_db),
):
    on = on or _latest_date(db)
    if on is None:
        return {"date": None, "count": 0, "items": []}
    # position = overall place among all ranked stocks that day (1 = best), independent of filters
    all_rows = db.execute(select(FactorScore.ticker).where(FactorScore.date == on)
                          .order_by(FactorScore.buy_rank.desc(), FactorScore.topsis.desc())).scalars().all()
    position = {t: i + 1 for i, t in enumerate(all_rows)}
    stmt = select(FactorScore).where(FactorScore.date == on, FactorScore.buy_rank >= min_rank)
    if sector:
        stmt = stmt.where(FactorScore.sector == sector)
    if band:
        stmt = stmt.where(FactorScore.band == band)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar()
    rows = db.execute(stmt.order_by(FactorScore.buy_rank.desc(), FactorScore.topsis.desc())
                      .offset(offset).limit(limit)).scalars().all()
    return {"date": str(on), "count": total, "universe": len(all_rows),
            "items": [{**_item(s), "position": position.get(s.ticker)} for s in rows]}


@router.get("/dates")
def rank_dates(limit: int = Query(30, ge=1, le=500), db: Session = Depends(get_db)):
    rows = db.execute(select(FactorScore.date).distinct().order_by(FactorScore.date.desc()).limit(limit)).scalars().all()
    return {"dates": [str(d) for d in rows]}


@router.get("/sectors")
def rank_sectors(db: Session = Depends(get_db)):
    on = _latest_date(db)
    if on is None:
        return {"date": None, "sectors": []}
    rows = db.execute(
        select(FactorScore.sector, func.count(), func.avg(FactorScore.buy_rank))
        .where(FactorScore.date == on).group_by(FactorScore.sector).order_by(func.avg(FactorScore.buy_rank).desc())
    ).all()
    return {"date": str(on), "sectors": [{"sector": s, "count": n, "avg_rank": round(a, 1)} for s, n, a in rows]}


@router.get("/{ticker}")
def rank_detail(ticker: str, history: int = Query(60, ge=1, le=500), db: Session = Depends(get_db)):
    ticker = ticker.upper() if ticker.endswith(".NS") else f"{ticker.upper()}.NS"
    rows = db.execute(select(FactorScore).where(FactorScore.ticker == ticker)
                      .order_by(FactorScore.date.desc()).limit(history)).scalars().all()
    if not rows:
        raise HTTPException(404, f"No Buy Rank for {ticker}")
    latest = rows[0]
    better = db.execute(select(func.count()).select_from(FactorScore).where(
        FactorScore.date == latest.date,
        (FactorScore.buy_rank > latest.buy_rank) | ((FactorScore.buy_rank == latest.buy_rank) & (FactorScore.topsis > latest.topsis)))).scalar()
    universe = db.execute(select(func.count()).select_from(FactorScore).where(FactorScore.date == latest.date)).scalar()
    return {
        **_item(latest, full=True),
        "position": (better or 0) + 1, "universe": universe,
        "history": [{"date": str(r.date), "buy_rank": r.buy_rank, "close": r.close} for r in reversed(rows)],
    }


@router.get("/{ticker}/explain")
def rank_explain(ticker: str, db: Session = Depends(get_db)):
    ticker = ticker.upper() if ticker.endswith(".NS") else f"{ticker.upper()}.NS"
    out = explain_rank(db, ticker)
    if out is None:
        raise HTTPException(404, f"No Buy Rank for {ticker}")
    return out
