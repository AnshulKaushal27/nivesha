"""
valuation.py (FIXED)
~~~~~~~~~~~~~~~~~~~~
Mark-to-market engine with proper error visibility.
Prices sourced from Upstox LTP V3 via get_latest_prices()
in services/market_data.py — single API call for all held tickers.
"""

import logging
from datetime import date
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from database import Portfolio, DailyValuation
from services.market_data import get_latest_prices

logger = logging.getLogger(__name__)


def update_valuations(db: Session, target_date: Optional[date] = None) -> int:
    """
    Mark-to-market every portfolio whose date == target_date.

    Price source  : Upstox LTP V3 (live price during session,
                    last traded price after close)
    Fallback      : holding.entry_price  (if Upstox has no quote)
    Returns       : number of portfolios updated
    """
    if target_date is None:
        target_date = date.today()

    portfolios: List[Portfolio] = (
        db.query(Portfolio)
        .filter(Portfolio.date == target_date)
        .all()
    )

    if not portfolios:
        logger.warning(f"No portfolios found for {target_date}")
        return 0

    # One LTP call for every unique ticker across all portfolios
    all_tickers = list({h.ticker for p in portfolios for h in p.holdings})
    
    logger.info(f"🔍 Fetching prices for {len(all_tickers)} unique tickers: {all_tickers}")
    
    prices: Dict[str, float] = get_latest_prices(all_tickers)
    
    # ⚠️  CHECK: Did we actually get prices?
    fetched_count = len(prices)
    logger.warning(f"⚠️  PRICES FETCHED: {fetched_count}/{len(all_tickers)}")
    if fetched_count < len(all_tickers):
        missing = set(all_tickers) - set(prices.keys())
        logger.error(f"❌ MISSING PRICES: {missing}")
    
    if not prices:
        logger.critical("❌ FATAL: Zero prices fetched! Valuations will be incorrect (using entry prices as fallback)")

    updated = 0

    for portfolio in portfolios:
        if not portfolio.holdings:
            continue

        current_value = portfolio.remaining_cash

        for holding in portfolio.holdings:
            px = prices.get(holding.ticker, holding.entry_price)
            
            # Log if we're using fallback price
            if holding.ticker not in prices:
                logger.debug(f"  ⚠️  [{holding.ticker}] Using entry price ₹{holding.entry_price} (no live quote)")
            
            current_value += holding.quantity * px

        return_pct = (
            (current_value - portfolio.starting_capital)
            / portfolio.starting_capital
        ) * 100
        unrealised = current_value - portfolio.starting_capital

        existing = (
            db.query(DailyValuation)
            .filter(
                DailyValuation.portfolio_id == portfolio.id,
                DailyValuation.date         == target_date,
            )
            .first()
        )

        if existing:
            existing.portfolio_value = round(current_value, 2)
            existing.return_pct      = round(return_pct,    4)
            existing.unrealized_pnl  = round(unrealised,    2)
        else:
            db.add(DailyValuation(
                portfolio_id    = portfolio.id,
                date            = target_date,
                portfolio_value = round(current_value, 2),
                return_pct      = round(return_pct,    4),
                unrealized_pnl  = round(unrealised,    2),
            ))

        logger.info(
            f"  [{portfolio.model:<10}]  "
            f"₹{current_value:>10,.2f}  ({return_pct:+.3f}%)"
        )
        updated += 1

    db.commit()
    logger.info(f"Committed valuations for {updated} portfolios on {target_date}")
    return updated