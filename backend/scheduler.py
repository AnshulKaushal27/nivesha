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

from ops.holidays import is_trading_day  # self-maintaining NSE calendar (static seed + NSE refresh + fixed national days)
from ops.alerts import raise_alert, resolve

def guarded(name: str):
    """Wrap a job so any exception becomes a recorded alert (never a silent skip), and success resolves it."""
    def deco(fn):
        async def wrapper(*a, **kw):
            try:
                result = await fn(*a, **kw)
                resolve(f"job_failed:{name}")
                return result
            except Exception as exc:  # noqa: BLE001
                logger.exception("job %s crashed", name)
                raise_alert(f"job_failed:{name}", f"Scheduled job '{name}' crashed: {type(exc).__name__}: {str(exc)[:300]}", "warning",
                            detail=repr(exc)[:1500])
                return {"error": str(exc)}
        wrapper.__name__ = fn.__name__
        return wrapper
    return deco


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

@guarded("morning_job")
async def morning_job():
    if not is_trading_day():
        logger.info(f"Skipping morning job — {date.today()} is not a trading day")
        return

    """8:40 AM IST — fetch data, rank, generate portfolios."""
    logger.info("━━━ 🌅  Morning job started ━━━")
    db    = SessionLocal()
    today = date.today()

    try:
        # ① Market data — Upstox when a token exists, otherwise from daily_bars
        from data.universe import universe_tickers
        from services.market_data import fetch_stock_data_from_db, market_source
        tickers = universe_tickers(db)
        src = market_source()
        logger.info(f"Fetching market data for {len(tickers)} tickers via {src}...")
        if src == "db":
            stocks = await asyncio.to_thread(fetch_stock_data_from_db, db, tickers)
        else:
            stocks = await asyncio.to_thread(fetch_stock_data, tickers)
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

        # ④ Generate portfolio per model (respecting the daily AI budget)
        from ops.llm_usage import enforce_budget
        model_results = []
        if not enforce_budget("arena"):
            logger.warning("Daily AI budget exhausted — AI managers skip today's round")
            return {"candidates": candidates, "model_results": [], "error": "Daily AI budget used up; the round was skipped"}
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


@guarded("nightly_job")
async def nightly_job():
    """20:15 IST — universe, daily bars, Buy Rank. Runs in a thread: it is I/O-heavy and synchronous."""
    if not is_trading_day():
        logger.info(f"Skipping nightly job — {date.today()} is not a trading day")
        return
    from jobs.nightly import run_nightly
    logger.info("━━━ 🌙  Nightly data job started ━━━")
    try:
        summary = await asyncio.to_thread(run_nightly, "upstox", 0, None, True)
        logger.info(f"━━━ ✅  Nightly done — {summary.get('bars_written', 0)} bars, "
                    f"{summary.get('scores_written', 0)} scores ━━━")
    except Exception as exc:
        logger.error(f"Nightly job error: {exc}")


@guarded("predictor_job")
async def predictor_job():
    """Saturday 09:00 IST — retrain the beat-the-market model on full history."""
    from database import SessionLocal as _SL
    from quant.predict import retrain_if_due
    logger.info("━━━ 🔮  Predictor upkeep started ━━━")
    try:
        def _go():
            with _SL() as db:
                return retrain_if_due(db)
        status = await asyncio.to_thread(_go)
        logger.info(f"━━━ ✅  Predictor upkeep — {status} ━━━")
    except Exception as exc:
        logger.error(f"Predictor job error: {exc}")


@guarded("closing_job")
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



async def heartbeat_job():
    """07:30 daily — one tiny LLM call: names credits-exhausted / bad key / gateway down, and updates the credit projection."""
    from ops.checks import llm_heartbeat
    res = await asyncio.to_thread(llm_heartbeat)
    logger.info(f"LLM heartbeat: {res}")


async def upstox_check_job():
    """07:45 trading days — is the Upstox token still valid before the morning round?"""
    if not is_trading_day():
        return
    from ops.checks import upstox_check
    logger.info(f"Upstox check: {await asyncio.to_thread(upstox_check)}")


async def freshness_job():
    """21:30 trading days — did bars, scores and the model keep up today? Any job failures?"""
    from ops.checks import data_freshness
    res = await asyncio.to_thread(data_freshness)
    logger.info(f"Freshness: bars {res.get('latest_bar')} scores {res.get('latest_rank')} model {res.get('model_as_of')}")


async def holidays_job():
    """1st of every month 07:00 — merge NSE's published holiday list (next year appears in December)."""
    from ops.checks import holidays_refresh
    logger.info(f"Holiday refresh: {await asyncio.to_thread(holidays_refresh)}")


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

    scheduler.add_job(
        nightly_job,
        CronTrigger(
            hour=settings.NIGHTLY_HOUR,
            minute=settings.NIGHTLY_MINUTE,
            day_of_week="mon-fri",
            timezone=IST,
        ),
        id="nightly_job",
        replace_existing=True,
        name="Nightly bars + Buy Rank",
        misfire_grace_time=3600,
    )

    # Retraining is handled inside the nightly job (retrain_if_due); the Saturday
    # run is a safety net for weeks where every nightly run was skipped.
    scheduler.add_job(
        predictor_job,
        CronTrigger(hour=9, minute=0, day_of_week="sat", timezone=IST),
        id="predictor_job",
        replace_existing=True,
        name="Weekly predictor safety retrain",
        misfire_grace_time=6 * 3600,
    )

    for fn, trig, jid, name in (
        (heartbeat_job,    CronTrigger(hour=7,  minute=30, timezone=IST),                    "heartbeat_job",    "LLM heartbeat + credit projection"),
        (upstox_check_job, CronTrigger(hour=7,  minute=45, day_of_week="mon-fri", timezone=IST), "upstox_check_job", "Upstox token check"),
        (freshness_job,    CronTrigger(hour=21, minute=30, day_of_week="mon-fri", timezone=IST), "freshness_job",    "Data freshness + job outcomes"),
        (holidays_job,     CronTrigger(day=1,   hour=7, minute=0, timezone=IST),             "holidays_job",     "NSE holiday list refresh"),
    ):
        scheduler.add_job(fn, trig, id=jid, replace_existing=True, name=name, misfire_grace_time=3600, coalesce=True)

    # Seed the trading calendar so every job above can ask is_trading_day() from day one.
    try:
        from ops.holidays import seed_static
        with SessionLocal() as db:
            n = seed_static(db)
        logger.info(f"Trading calendar ready ({n} holiday rows added)")
    except Exception as exc:  # noqa: BLE001 — before the migration runs, the table may not exist yet
        logger.warning(f"Holiday seed skipped: {exc}")

    return scheduler


def job_schedule(scheduler) -> list[dict]:
    """For the status page: every job with its next fire time."""
    out = []
    for j in scheduler.get_jobs():
        nxt = j.next_run_time
        out.append({"id": j.id, "name": j.name, "next_run": nxt.isoformat() if nxt else None, "trigger": str(j.trigger)})
    return sorted(out, key=lambda r: r["next_run"] or "")


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