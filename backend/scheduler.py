import asyncio
import logging
from datetime import date

import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from config import settings
from database import (
    SessionLocal, Base, engine,
    Portfolio, Holding, MarketSnapshot,
)
from services.market_data import fetch_stock_data, apply_topsis
from services.ai_engine import generate_portfolio, SUPPORTED_MODELS
from services.valuation import update_valuations

logger = logging.getLogger(__name__)
IST = pytz.timezone("Asia/Kolkata")

# Ensure tables exist
Base.metadata.create_all(bind=engine)

import httpx
from datetime import date

NSE_HOLIDAYS_2025_2026 = {
    # 2025
    # ===== 2026 =====
    date(2026, 1, 15),   # Municipal Corporation Election - Maharashtra
    date(2026, 1, 26),   # Republic Day
    date(2026, 3, 3),    # Holi
    date(2026, 3, 26),   # Shri Ram Navami
    date(2026, 3, 31),   # Shri Mahavir Jayanti
    date(2026, 4, 3),    # Good Friday
    date(2026, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
    date(2026, 5, 1),    # Maharashtra Day
    date(2026, 5, 28),   # Bakri Id
    date(2026, 6, 26),   # Muharram
    date(2026, 9, 14),   # Ganesh Chaturthi
    date(2026, 10, 2),   # Gandhi Jayanti
    date(2026, 10, 20),  # Dussehra
    date(2026, 11, 10),  # Diwali-Balipratipada
    date(2026, 11, 24),  # Guru Nanak Jayanti
    date(2026, 12, 25),  # Christmas
    # ===== 2027 =====
    date(2027, 1, 26),   # Republic Day
    date(2027, 3, 1),    # Mahashivratri
    date(2027, 3, 22),   # Holi
    date(2027, 3, 30),   # Good Friday
    date(2027, 4, 11),   # Id-Ul-Fitr (tentative)
    date(2027, 4, 14),   # Dr. Baba Saheb Ambedkar Jayanti
    date(2027, 4, 21),   # Ram Navami
    date(2027, 5, 1),    # Maharashtra Day
    date(2027, 6, 17),   # Bakri Id (tentative)
    date(2027, 8, 15),   # Independence Day
    date(2027, 9, 5),    # Ganesh Chaturthi
    date(2027, 10, 2),   # Gandhi Jayanti
    date(2027, 10, 9),   # Dussehra
    date(2027, 11, 1),   # Diwali Laxmi Pujan
    date(2027, 11, 2),   # Diwali Balipratipada
    date(2027, 11, 15),  # Guru Nanak Jayanti
    date(2027, 12, 25),  # Christmas
}


def is_trading_day(d: date | None = None) -> bool:
    """Returns True only if d is a weekday and not an NSE holiday."""
    d = d or date.today()
    if d.weekday() >= 5:          # Saturday=5, Sunday=6
        return False
    if d in NSE_HOLIDAYS_2025_2026:
        return False
    return True
# ── Helper ─────────────────────────────────────────────────────────────────

def _get_prev_context(db, model_name: str) -> dict | None:
    """Return last portfolio's performance stats for the prompt."""
    last = (
        db.query(Portfolio)
        .filter(Portfolio.model == model_name)
        .order_by(Portfolio.date.desc())
        .first()
    )
    if not last:
        return None

    from database import DailyValuation
    valuations = (
        db.query(DailyValuation)
        .join(Portfolio)
        .filter(Portfolio.model == model_name)
        .all()
    )
    returns = [v.return_pct for v in valuations] if valuations else []

    return {
        "last_return":  valuations[-1].return_pct if valuations else 0.0,
        "avg_return":   (sum(returns) / len(returns)) if returns else 0.0,
        "last_holdings": [
            {"ticker": h.ticker, "entry_price": h.entry_price}
            for h in last.holdings
        ],
    }


# ── Jobs ───────────────────────────────────────────────────────────────────

async def morning_job():
    if not is_trading_day():
        logger.info(f"Skipping morning job — {date.today()} is not a trading day")
        return

    """8:40 AM IST — fetch data, rank, generate portfolios."""
    logger.info("━━━ 🌅  Morning job started ━━━")
    db    = SessionLocal()
    today = date.today()

    try:
        # ① Market data
        logger.info("Fetching NIFTY200 market data...")
        stocks = fetch_stock_data(settings.NIFTY_200_TICKERS)
        if not stocks:
            logger.error("No stock data. Aborting morning job.")
            return {"error": "No market data"}

        # ② TOPSIS
        candidates = apply_topsis(stocks, n_candidates=settings.TOP_CANDIDATES)
        logger.info(f"Top {len(candidates)} candidates selected by TOPSIS")

        # ③ Save market snapshot (upsert)
        for snap_data in candidates:
            existing_snap = (
                db.query(MarketSnapshot)
                .filter(MarketSnapshot.date == today, MarketSnapshot.ticker == snap_data["ticker"])
                .first()
            )
            if existing_snap:
                continue  # already saved today
            db.add(MarketSnapshot(
                date            = today,
                ticker          = snap_data["ticker"],
                current_price   = snap_data.get("current_price", 0),
                rsi             = snap_data.get("rsi", 0),
                sma20           = snap_data.get("sma20", 0),
                sma50           = snap_data.get("sma50", 0),
                volatility      = snap_data.get("volatility", 0),
                volume_ratio    = snap_data.get("volume_ratio", 0),
                one_month_return= snap_data.get("one_month_return", 0),
                sector          = snap_data.get("sector", "Unknown"),
                trend_score     = snap_data.get("trend_score", 0),
                rsi_distance    = snap_data.get("rsi_distance", 0),
                topsis_score    = snap_data.get("topsis_score", 0),
            ))
        db.commit()

        # ④ Generate portfolio per model
        model_results = []
        for model_name in SUPPORTED_MODELS:
            try:
                # Skip if already done today
                exists = (
                    db.query(Portfolio)
                    .filter(Portfolio.model == model_name, Portfolio.date == today)
                    .first()
                )
                if exists:
                    logger.info(f"[{model_name}] Portfolio already exists today — skipping")
                    # Still include in results for API response
                    model_results.append(_portfolio_to_dict(exists))
                    continue

                prev_ctx = _get_prev_context(db, model_name)
                result   = await generate_portfolio(
                    model_name      = model_name,
                    candidates      = candidates,
                    starting_capital= settings.DEFAULT_CAPITAL,
                    prev_context    = prev_ctx,
                )

                # Persist
                p = Portfolio(
                    model            = model_name,
                    date             = today,
                    starting_capital = result["starting_capital"],
                    total_invested   = result["total_invested"],
                    remaining_cash   = result["remaining_cash"],
                    strategy_summary = result.get("strategy_summary"),
                    risk_level       = result.get("risk_level"),
                )
                db.add(p)
                db.flush()

                for h in result["portfolio"]:
                    db.add(Holding(
                        portfolio_id       = p.id,
                        ticker             = h["ticker"],
                        quantity           = h.get("quantity", 0),
                        entry_price        = h.get("entry_price", 0),
                        invested_amount    = h.get("invested_amount", 0),
                        allocation_percent = h.get("allocation_percent", 0),
                        confidence         = h.get("confidence", 70),
                        reasoning          = h.get("reasoning", ""),
                        sector             = h.get("sector", "Unknown"),
                    ))
                db.commit()
                logger.info(f"[{model_name}] ✓ Portfolio saved ({len(result['portfolio'])} holdings)")

                # Build frontend-compatible result object
                model_results.append({
                    "model":           model_name,
                    "starting_capital": result["starting_capital"],
                    "remaining_cash":  result["remaining_cash"],
                    "portfolio": [
                        {
                            "ticker":          h["ticker"],
                            "quantity":        h["quantity"],
                            "price":           h["entry_price"],   # frontend uses "price"
                            "invested_amount": h["invested_amount"],
                            "confidence":      h["confidence"],
                            "reasoning":       h["reasoning"],
                        }
                        for h in result["portfolio"]
                    ],
                })

            except Exception as exc:
                logger.error(f"[{model_name}] Failed: {exc}")
                db.rollback()

        logger.info("━━━ ✅  Morning job complete ━━━")
        return {"candidates": candidates, "model_results": model_results}

    except Exception as exc:
        logger.error(f"Morning job crashed: {exc}")
        db.rollback()
        return {"error": str(exc)}
    finally:
        db.close()


async def closing_job():
    if not is_trading_day():
        logger.info(f"Skipping closing job — {date.today()} is not a trading day")
        return
    """3:45 PM IST — update valuations for today's portfolios."""
    logger.info("━━━ 📊  Closing job started ━━━")
    db = SessionLocal()
    try:
        count = update_valuations(db)
        logger.info(f"━━━ ✅  Closing job done — {count} portfolios updated ━━━")
    except Exception as exc:
        logger.error(f"Closing job error: {exc}")
    finally:
        db.close()


# ── Scheduler factory ──────────────────────────────────────────────────────

def setup_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=IST)

    scheduler.add_job(
        morning_job,
        CronTrigger(
            hour=settings.MORNING_HOUR,
            minute=settings.MORNING_MINUTE,
            day_of_week="mon-fri",
            timezone=IST,
        ),
        id="morning_job",
        replace_existing=True,
        name="Morning Portfolio Generation",
        misfire_grace_time=300,  # allow 5-min late fire
    )

    scheduler.add_job(
        closing_job,
        CronTrigger(
            hour=settings.CLOSING_HOUR,
            minute=settings.CLOSING_MINUTE,
            day_of_week="mon-fri",
            timezone=IST,
        ),
        id="closing_job",
        replace_existing=True,
        name="Closing Valuation Update",
        misfire_grace_time=300,
    )

    return scheduler


def _portfolio_to_dict(p: Portfolio) -> dict:
    return {
        "model":            p.model,
        "starting_capital": p.starting_capital,
        "remaining_cash":   p.remaining_cash,
        "portfolio": [
            {
                "ticker":          h.ticker,
                "quantity":        h.quantity,
                "price":           h.entry_price,
                "invested_amount": h.invested_amount,
                "confidence":      h.confidence,
                "reasoning":       h.reasoning,
            }
            for h in p.holdings
        ],
    }