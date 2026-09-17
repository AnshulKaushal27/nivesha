from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db, Portfolio, DailyValuation

router = APIRouter()


@router.get("/portfolios")
def list_portfolios(
    model:     Optional[str]  = Query(None),
    from_date: Optional[date] = Query(None),
    to_date:   Optional[date] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Portfolio)
    if model:
        q = q.filter(Portfolio.model == model)
    if from_date:
        q = q.filter(Portfolio.date >= from_date)
    if to_date:
        q = q.filter(Portfolio.date <= to_date)

    portfolios = q.order_by(Portfolio.date.desc()).all()
    return [
        {
            "id":              p.id,
            "model":           p.model,
            "date":            str(p.date),
            "starting_capital":p.starting_capital,
            "total_invested":  p.total_invested,
            "remaining_cash":  p.remaining_cash,
            "strategy_summary":p.strategy_summary,
            "risk_level":      p.risk_level,
            "holdings_count":  len(p.holdings),
        }
        for p in portfolios
    ]


@router.get("/portfolios/{portfolio_id}")
def get_portfolio(portfolio_id: int, db: Session = Depends(get_db)):
    p = db.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Portfolio not found")

    valuations_sorted = sorted(p.valuations, key=lambda v: v.date, reverse=True)
    latest_val = valuations_sorted[0] if valuations_sorted else None

    return {
        "id":              p.id,
        "model":           p.model,
        "date":            str(p.date),
        "starting_capital":p.starting_capital,
        "total_invested":  p.total_invested,
        "remaining_cash":  p.remaining_cash,
        "strategy_summary":p.strategy_summary,
        "risk_level":      p.risk_level,
        "holdings": [
            {
                "ticker":            h.ticker,
                "quantity":          h.quantity,
                "entry_price":       h.entry_price,
                "invested_amount":   h.invested_amount,
                "allocation_percent":h.allocation_percent,
                "confidence":        h.confidence,
                "reasoning":         h.reasoning,
                "sector":            h.sector,
            }
            for h in p.holdings
        ],
        "latest_valuation": {
            "portfolio_value": latest_val.portfolio_value,
            "return_pct":      latest_val.return_pct,
            "unrealized_pnl":  latest_val.unrealized_pnl,
        } if latest_val else None,
        "valuation_history": [
            {
                "date":            str(v.date),
                "portfolio_value": v.portfolio_value,
                "return_pct":      v.return_pct,
            }
            for v in sorted(p.valuations, key=lambda v: v.date)
        ],
    }