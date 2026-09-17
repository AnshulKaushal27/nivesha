"""Buy Rank API. Shapes are what the Rank page and the stock page render."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import FactorScore, ModelRun, Prediction, get_db
from llm.explain import explain_rank

router = APIRouter(prefix="/rank", tags=["rank"])


def _latest_date(db: Session) -> date | None:
    return db.execute(select(func.max(FactorScore.date))).scalar()


def _date_n_back(db: Session, on: date, n: int) -> date | None:
    """The n-th distinct score date before `on` (n trading days back)."""
    return db.execute(select(FactorScore.date).distinct().where(FactorScore.date < on)
                      .order_by(FactorScore.date.desc()).offset(n - 1).limit(1)).scalar()


def _previous(db: Session, on: date, n: int) -> tuple[date | None, dict[str, tuple[int, float]]]:
    prev = _date_n_back(db, on, n)
    if prev is None:
        return None, {}
    rows = db.execute(select(FactorScore.ticker, FactorScore.buy_rank, FactorScore.close).where(FactorScore.date == prev)).all()
    return prev, {t: (r, c) for t, r, c in rows}


def _latest_odds(db: Session) -> dict[str, float]:
    run = db.execute(select(ModelRun).order_by(ModelRun.as_of.desc(), ModelRun.id.desc()).limit(1)).scalar_one_or_none()
    if run is None:
        return {}
    return dict(db.execute(select(Prediction.ticker, Prediction.prob_up)
                           .where(Prediction.date == run.as_of, Prediction.horizon == run.meta.get("horizon_days", 63))).all())


def _pct(a: float | None, b: float | None) -> float | None:
    return None if not a or not b else (a / b - 1) * 100


def _fine_score(position: int | None, n: int) -> float | None:
    """Exact percentile (one decimal) from the position: #1 of N → 100.0, #N → ≈0.2.
    Consistent with buy_rank = ceil(percentile)."""
    if position is None or n <= 0:
        return None
    return round(100.0 * (1 - (position - 1) / n), 1)


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
    prev_date, prev = _previous(db, on, 20)
    odds = _latest_odds(db)
    n = max(1, len(all_rows))
    items = []
    for s in rows:
        p = prev.get(s.ticker)
        pos = position.get(s.ticker)
        items.append({
            **_item(s), "position": pos,
            # exact percentile with one decimal: 100.0 is the very top, unique per stock
            "score": _fine_score(pos, n),
            "rank_change_20d": (s.buy_rank - p[0]) if p else None,
            "price_change_20d_pct": _pct(s.close, p[1]) if p else None,
            "prob_up": odds.get(s.ticker),
        })
    return {"date": str(on), "count": total, "universe": len(all_rows), "compare_date": str(prev_date) if prev_date else None, "items": items}


@router.get("/movers")
def rank_movers(days: int = Query(20, ge=1, le=120), limit: int = Query(6, ge=1, le=20), db: Session = Depends(get_db)):
    """Biggest rises and falls in Buy Rank over the last `days` trading days (eligible stocks only)."""
    on = _latest_date(db)
    if on is None:
        return {"date": None, "compare_date": None, "risers": [], "fallers": []}
    prev_date, prev = _previous(db, on, days)
    cur = db.execute(select(FactorScore).where(FactorScore.date == on, FactorScore.eligible == 1)).scalars().all()
    moves = []
    for s in cur:
        p = prev.get(s.ticker)
        if not p:
            continue
        moves.append({"ticker": s.ticker, "symbol": s.ticker.replace(".NS", ""), "sector": s.sector,
                      "from_rank": p[0], "to_rank": s.buy_rank, "change": s.buy_rank - p[0], "band": s.band,
                      "close": s.close, "price_change_pct": _pct(s.close, p[1])})
    moves.sort(key=lambda m: m["change"])
    return {"date": str(on), "compare_date": str(prev_date) if prev_date else None, "days": days,
            "risers": list(reversed(moves[-limit:])) if moves else [], "fallers": moves[:limit]}


@router.get("/bands-track")
def bands_track(days: int = Query(20, ge=5, le=120), db: Session = Depends(get_db)):
    """
    Did the ranking hold up? Take each band as it stood `days` trading days ago and
    index an equal-weight basket of its stocks from then to now, against all stocks.
    """
    from database import DailyBar
    on = _latest_date(db)
    if on is None:
        return {"date": None, "compare_date": None, "series": [], "summary": []}
    prev_date = _date_n_back(db, on, days)
    if prev_date is None:
        return {"date": str(on), "compare_date": None, "series": [], "summary": []}
    then = db.execute(select(FactorScore.ticker, FactorScore.band).where(FactorScore.date == prev_date, FactorScore.eligible == 1)).all()
    band_of = {t: b for t, b in then}
    tickers = list(band_of)
    rows = db.execute(select(DailyBar.date, DailyBar.ticker, DailyBar.close)
                      .where(DailyBar.date >= prev_date, DailyBar.date <= on, DailyBar.ticker.in_(tickers)).order_by(DailyBar.date)).all()
    by_date: dict = {}
    for d, t, c in rows:
        by_date.setdefault(d, {})[t] = c
    base = by_date.get(prev_date, {})
    bands = ["Strong", "Good", "Neutral", "Weak"]
    series = []
    for d in sorted(by_date):
        day = by_date[d]
        point = {"date": str(d)}
        for b in bands + ["All"]:
            rel = [day[t] / base[t] for t in day if t in base and base[t] and (b == "All" or band_of.get(t) == b)]
            point[b] = round(100 * sum(rel) / len(rel), 2) if rel else None
        series.append(point)
    last = series[-1] if series else {}
    summary = []
    for b in bands:
        n = sum(1 for t in band_of if band_of[t] == b)
        v = last.get(b)
        summary.append({"band": b, "n": n, "change_pct": None if v is None else round(v - 100, 2)})
    market = None if not last or last.get("All") is None else round(last["All"] - 100, 2)
    strong, weak = next((s["change_pct"] for s in summary if s["band"] == "Strong"), None), next((s["change_pct"] for s in summary if s["band"] == "Weak"), None)
    verdict = None if strong is None or weak is None else ("held up" if strong > weak else "did not hold up")
    return {"date": str(on), "compare_date": str(prev_date), "days": days, "series": series, "summary": summary,
            "market_change_pct": market, "verdict": verdict, "spread_pct": None if strong is None or weak is None else round(strong - weak, 2)}


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
        "score": _fine_score((better or 0) + 1, universe or 1),
        "history": [{"date": str(r.date), "buy_rank": r.buy_rank, "close": r.close} for r in reversed(rows)],
    }


@router.get("/{ticker}/explain")
def rank_explain(ticker: str, db: Session = Depends(get_db)):
    ticker = ticker.upper() if ticker.endswith(".NS") else f"{ticker.upper()}.NS"
    out = explain_rank(db, ticker)
    if out is None:
        raise HTTPException(404, f"No Buy Rank for {ticker}")
    return out
