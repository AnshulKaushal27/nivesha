from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db, MarketSnapshot

router = APIRouter()


@router.get("/market")
def get_market(db: Session = Depends(get_db)):
    """Latest TOPSIS-ranked candidates snapshot."""
    latest = (
        db.query(MarketSnapshot.date)
        .order_by(MarketSnapshot.date.desc())
        .first()
    )
    if not latest:
        return {"date": None, "candidates": []}

    snaps = (
        db.query(MarketSnapshot)
        .filter(MarketSnapshot.date == latest[0])
        .order_by(MarketSnapshot.topsis_score.desc())
        .all()
    )

    return {
        "date": str(latest[0]),
        "candidates": [
            {
                "ticker":           s.ticker,
                "current_price":    s.current_price,
                "rsi":              s.rsi,
                "rsi_distance":     s.rsi_distance,
                "sma20":            s.sma20,
                "sma50":            s.sma50,
                "volatility":       s.volatility,
                "volume_ratio":     s.volume_ratio,
                "one_month_return": s.one_month_return,
                "sector":           s.sector,
                "trend_score":      s.trend_score,
                "topsis_score":     s.topsis_score,
            }
            for s in snaps
        ],
    }