from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from services.valuation import update_valuations
# routes/admin.py
from database import DailyValuation  # add this

router = APIRouter()


@router.post("/simulate-and-save")
async def simulate_and_save(db: Session = Depends(get_db)):
    """
    Manually trigger a full morning run.
    Returns full market_candidates + model_results
    so the frontend PortfolioCards and MarketIntelPanel populate immediately.
    """
    from scheduler import morning_job
    result = await morning_job()

    if "error" in result:
        return {"message": f"Simulation failed: {result['error']}", "results": {}}

    return {
        "message": "Portfolios saved",
        "results": {
            "market_candidates": result.get("candidates", []),
            "model_results":     result.get("model_results", []),
        },
    }


@router.get("/status")
def system_status(request: Request, db: Session = Depends(get_db)):
    """Everything a human needs to know the system is healthy: jobs, alerts, data, credits, calendar."""
    from datetime import datetime
    from sqlalchemy import func, select
    from database import DailyBar, FactorScore, IngestRun, ModelRun
    from ops import holidays
    from ops.alerts import KIND_HELP, open_alerts
    from ops.llm_usage import summary as usage_summary
    from scheduler import job_schedule

    alerts = [{"id": a.id, "kind": a.kind, "severity": a.severity, "message": a.message, "detail": a.detail, "count": a.count,
               "first_seen": str(a.first_seen), "last_seen": str(a.last_seen), "help": KIND_HELP.get(a.kind)} for a in open_alerts(db)]
    jobs = {}
    for job in db.execute(select(IngestRun.job).distinct()).scalars().all():
        r = db.execute(select(IngestRun).where(IngestRun.job == job).order_by(IngestRun.started_at.desc()).limit(1)).scalar_one_or_none()
        jobs[job] = {"status": r.status, "started_at": str(r.started_at), "finished_at": str(r.finished_at), "rows": r.rows, "detail": (r.detail or "")[:300]}
    sched = getattr(request.app.state, "scheduler", None)
    last_model = db.execute(select(ModelRun).order_by(ModelRun.as_of.desc()).limit(1)).scalar_one_or_none()
    worst = "critical" if any(a["severity"] == "critical" for a in alerts) else "warning" if any(a["severity"] == "warning" for a in alerts) else "ok"
    return {
        "overall": worst,
        "checked_at": datetime.utcnow().isoformat() + "Z",
        "today": {"date": str(date.today()), "trading_day": holidays.is_trading_day(), "holiday": holidays.holiday_name(date.today()),
                  "next_trading_day": str(holidays.next_trading_day())},
        "alerts": alerts,
        "jobs": jobs,
        "schedule": job_schedule(sched) if sched else [],
        "data": {"latest_bars": str(db.execute(select(func.max(DailyBar.date))).scalar()),
                 "latest_scores": str(db.execute(select(func.max(FactorScore.date))).scalar()),
                 "model_trained": str(last_model.as_of) if last_model else None,
                 "model_oos": last_model.meta.get("oos") if last_model else None},
        "llm": usage_summary(db),
        "provider": __import__("llm.gateway", fromlist=["provider_status"]).provider_status(),
        "calendar": holidays.coverage(),
        "channels": {"telegram": bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID), "webhook": bool(settings.ALERT_WEBHOOK_URL)},
    }


@router.post("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    from datetime import datetime
    from database import SystemAlert
    a = db.get(SystemAlert, alert_id)
    if not a:
        return {"ok": False}
    a.resolved_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "kind": a.kind}


@router.post("/checks/run")
async def run_checks():
    """Run every health check now (heartbeat, Upstox, freshness, holidays)."""
    import asyncio
    from ops.checks import run_all
    return await asyncio.to_thread(run_all)


@router.post("/alerts/test")
def test_alert():
    """Send a test alert through every configured channel."""
    from ops.alerts import raise_alert, resolve
    a = raise_alert("test_alert", "This is a test alert from Nivesha. If you can read this, notifications work.", "info")
    resolve("test_alert")
    return {"ok": True, "notified": a.notified_at is not None,
            "channels": {"telegram": bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID), "webhook": bool(settings.ALERT_WEBHOOK_URL)}}


@router.post("/train-predictor")
async def trigger_train_predictor():
    """Retrain the beat-the-market model now (takes a minute or two)."""
    import asyncio
    from jobs.train_predictor import run as train
    meta = await asyncio.to_thread(train)
    return {"message": "Predictor trained", "as_of": meta["as_of"], "oos": meta["oos"]}


@router.post("/update-valuations")
def trigger_update_valuations(db: Session = Depends(get_db)):
    """Manually update today's portfolio valuations."""
    count = update_valuations(db)
    return {"message": "Valuations updated", "portfolios_updated": count}


@router.post("/simulate")
async def simulate_only():
    """
    Lightweight simulation preview — does NOT persist.
    Returns market candidates only (no LLM calls).
    """
    from services.market_data import fetch_stock_data, apply_topsis
    from config import settings

    stocks     = fetch_stock_data(settings.NIFTY_200_TICKERS)
    candidates = apply_topsis(stocks, n_candidates=settings.TOP_CANDIDATES)
    return {"candidates": candidates, "count": len(candidates)}


@router.get("/analytics/history")
def performance_history(db: Session = Depends(get_db)):
    """
    Per-model time-series data for the frontend charts.
    Returns { model_name: [{date, return_pct, portfolio_value}] }
    """
    from database import Portfolio, DailyValuation

    models = [row[0] for row in db.query(Portfolio.model).distinct().all()]
    history = {}

    for model_name in models:
        rows = (
            db.query(DailyValuation.date, DailyValuation.return_pct, DailyValuation.portfolio_value)
            .join(Portfolio)
            .filter(Portfolio.model == model_name)
            .order_by(DailyValuation.date.asc())
            .all()
        )
        history[model_name] = [
            {"date": str(d), "return_pct": r, "portfolio_value": v}
            for d, r, v in rows
        ]

    return history

@router.get("/simulation/today")
def get_today_simulation(db: Session = Depends(get_db)):
    """
    Returns today's simulation data. If today has no portfolios yet,
    falls back to the most recent day that does.
    """
    from database import Portfolio, Holding, MarketSnapshot

    # Find the most recent date that has portfolios
    latest_date = (
        db.query(Portfolio.date)
        .order_by(Portfolio.date.desc())
        .first()
    )
    if not latest_date:
        return {"date": None, "market_candidates": [], "model_results": []}

    target_date = latest_date[0]

    # Portfolios for that date
    portfolios = (
        db.query(Portfolio)
        .filter(Portfolio.date == target_date)
        .all()
    )

    # Market snapshot for that date
    snaps = (
        db.query(MarketSnapshot)
        .filter(MarketSnapshot.date == target_date)
        .order_by(MarketSnapshot.topsis_score.desc())
        .all()
    )

    model_results = []
    for p in portfolios:
        # Get latest valuation for this portfolio
        latest_val = (
            db.query(DailyValuation)
            .filter(DailyValuation.portfolio_id == p.id)
            .order_by(DailyValuation.date.desc())
            .first()
        )
        model_results.append({
            "model":            p.model,
            "starting_capital": p.starting_capital,
            "remaining_cash":   p.remaining_cash,
            "strategy_summary": p.strategy_summary,
            "risk_level":       p.risk_level,
            "current_return":   latest_val.return_pct if latest_val else None,
            "portfolio_value":  latest_val.portfolio_value if latest_val else None,
            "portfolio": [
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
        })

    return {
        "date": str(target_date),
        "market_candidates": [
            {
                "ticker":           s.ticker,
                "current_price":    s.current_price,
                "rsi":              s.rsi,
                "volatility":       s.volatility,
                "volume_ratio":     s.volume_ratio,
                "one_month_return": s.one_month_return,
                "sector":           s.sector,
                "trend_score":      s.trend_score,
                "topsis_score":     s.topsis_score,
            }
            for s in snaps
        ],
        "model_results": model_results,
    }