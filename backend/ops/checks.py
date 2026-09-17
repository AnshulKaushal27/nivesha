"""
Scheduled health checks. Each one raises or resolves a named alert.

  llm_heartbeat      07:30 daily      one tiny model call → credits / auth / gateway state
  upstox_check       07:45 trading    is the Upstox token still accepted?
  data_freshness     21:30 trading    did today's bars, ranks arrive? is the model recent?
  holidays_refresh   1st of month     pull NSE's holiday list for the year(s) it publishes
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import settings
from database import DailyBar, FactorScore, IngestRun, ModelRun, SessionLocal
from ops import holidays
from ops.alerts import KIND_HELP, classify_llm_error, raise_alert, resolve
from ops.llm_usage import check_credit_projection

logger = logging.getLogger(__name__)


def llm_heartbeat() -> dict:
    """Minimal call through the gateway; classifies any failure so credits exhaustion is named, not guessed."""
    from llm.gateway import chat, llm_available
    if not llm_available():
        raise_alert("llm_auth_failed", "No AICREDITS_API_KEY configured; every AI feature is off.", "critical")
        return {"ok": False, "kind": "llm_auth_failed"}
    from llm.gateway import fallback_configured, mark_primary_down, mark_primary_up, provider_status
    mark_primary_up()                               # the heartbeat always probes the primary first
    try:
        llm = chat(model=settings.CHAT_GUARD_MODEL, temperature=0, max_tokens=5, max_retries=1, read_timeout=20.0).with_config(tags=["heartbeat"])
        llm.invoke([("user", "Reply with the single word OK.")])
    except Exception as exc:                        # noqa: BLE001
        kind, severity = classify_llm_error(exc)
        note = ""
        if fallback_configured():
            mark_primary_down()
            try:
                chat(temperature=0, max_tokens=5, max_retries=1, read_timeout=20.0).with_config(tags=["heartbeat"]).invoke([("user", "Reply with the single word OK.")])
                note = f" Running on the fallback provider ({settings.LLM_FALLBACK_MODEL}) meanwhile."
                severity = "info" if severity == "warning" else severity
            except Exception as exc2:               # noqa: BLE001
                note = f" The fallback provider failed too ({type(exc2).__name__})."
        raise_alert(kind, f"{KIND_HELP.get(kind, 'LLM heartbeat failed.')}{note}", severity, detail=f"{type(exc).__name__}: {exc}"[:1500])
        return {"ok": False, "kind": kind, "error": str(exc)[:300], "provider": provider_status()}
    for k in ("credits_exhausted", "llm_auth_failed", "llm_gateway_down", "llm_rate_limited", "llm_error"):
        resolve(k)
    from ops.llm_usage import budget_status
    with SessionLocal() as db:
        proj = check_credit_projection(db)
        budget = budget_status(db)
    if not budget["exhausted"]:
        resolve("budget_exceeded")                  # new day, new budget
    return {"ok": True, "projection": proj, "budget": budget}


def upstox_token_info(token: str | None = None) -> dict:
    """Read the token's own claims (no network): type, expiry, days left."""
    import base64
    import json
    token = settings.UPSTOX_ANALYTICS_TOKEN if token is None else token
    if not token or token.count(".") != 2:
        return {"present": bool(token), "decodable": False}
    try:
        payload = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
        exp = datetime.utcfromtimestamp(payload["exp"]).date() if "exp" in payload else None
        return {"present": True, "decodable": True, "extended": bool(payload.get("isExtended")),
                "expires_on": str(exp) if exp else None, "days_left": (exp - date.today()).days if exp else None,
                "plus_plan": bool(payload.get("isPlusPlan")), "user": payload.get("sub")}
    except Exception:                               # noqa: BLE001
        return {"present": True, "decodable": False}


def upstox_check() -> dict:
    """
    Trading mornings: confirm the Upstox token works before the morning round needs it.
    Probes a market-data endpoint (the only kind an *extended* token may call) — the
    user-profile endpoint answers 401 for extended tokens even when they are valid.
    """
    if not settings.UPSTOX_ANALYTICS_TOKEN:
        resolve("upstox_token_expired")
        resolve("upstox_token_expiring")
        return {"ok": None, "note": "no Upstox token configured; data comes from the fallback source"}
    info = upstox_token_info()
    try:
        r = httpx.get("https://api.upstox.com/v3/market-quote/ltp", params={"instrument_key": "NSE_EQ|INE002A01018"},
                      headers={"Authorization": f"Bearer {settings.UPSTOX_ANALYTICS_TOKEN}", "Accept": "application/json"},
                      timeout=httpx.Timeout(20, connect=5))
        if r.status_code == 401:
            raise_alert("upstox_token_expired", KIND_HELP["upstox_token_expired"], "warning", detail=r.text[:300])
            return {"ok": False, "status": 401, "token": info}
        r.raise_for_status()
    except httpx.HTTPError as exc:
        raise_alert("upstox_unreachable", f"Upstox API not reachable: {exc}", "warning")
        return {"ok": False, "error": str(exc)[:300], "token": info}
    resolve("upstox_token_expired")
    resolve("upstox_unreachable")
    if info.get("days_left") is not None and info["days_left"] <= 14:
        raise_alert("upstox_token_expiring", f"The Upstox {'extended ' if info.get('extended') else ''}token expires on {info['expires_on']} "
                    f"({info['days_left']} days). Generate a new one at Upstox and update UPSTOX_ANALYTICS_TOKEN before then.", "warning")
    else:
        resolve("upstox_token_expiring")
    return {"ok": True, "token": info}


def data_freshness(db: Session | None = None) -> dict:
    """Evening check: bars and ranks for today (if a trading day), model age, last job outcomes."""
    own = db is None
    db = db or SessionLocal()
    try:
        today = date.today()
        out: dict = {"date": str(today), "trading_day": holidays.is_trading_day(today)}
        latest_bar = db.execute(select(func.max(DailyBar.date))).scalar()
        latest_rank = db.execute(select(func.max(FactorScore.date))).scalar()
        last_model = db.execute(select(func.max(ModelRun.as_of))).scalar()
        out.update(latest_bar=str(latest_bar), latest_rank=str(latest_rank), model_as_of=str(last_model))

        if holidays.is_trading_day(today):
            if latest_bar != today:
                raise_alert("data_stale", f"{KIND_HELP['data_stale']} Latest bars: {latest_bar}.", "warning", db=db)
            else:
                resolve("data_stale", db=db)
            if latest_rank != latest_bar:
                raise_alert("ranks_stale", f"{KIND_HELP['ranks_stale']} Bars: {latest_bar}, scores: {latest_rank}.", "warning", db=db)
            else:
                resolve("ranks_stale", db=db)
        if last_model and (today - last_model).days > 14:
            raise_alert("predictor_stale", f"{KIND_HELP['predictor_stale']} Last trained {last_model}.", "warning", db=db)
        elif last_model:
            resolve("predictor_stale", db=db)

        # last outcome per job
        jobs = {}
        for job in db.execute(select(IngestRun.job).distinct()).scalars().all():
            r = db.execute(select(IngestRun).where(IngestRun.job == job).order_by(IngestRun.started_at.desc()).limit(1)).scalar_one_or_none()
            jobs[job] = {"status": r.status, "at": str(r.started_at), "rows": r.rows, "detail": (r.detail or "")[:200]}
            if r.status == "failed":
                raise_alert(f"job_failed:{job}", f"Job '{job}' failed: {(r.detail or '')[:300]}", "warning", db=db)
            else:
                resolve(f"job_failed:{job}", db=db)
        out["jobs"] = jobs
        return out
    finally:
        if own:
            db.close()


def holidays_refresh() -> dict:
    with SessionLocal() as db:
        try:
            res = holidays.refresh_from_nse(db)
            resolve("holidays_unrefreshed", db=db)
            return res
        except Exception as exc:                    # noqa: BLE001
            raise_alert("holidays_unrefreshed", f"{KIND_HELP['holidays_unrefreshed']} ({exc})", "info", db=db)
            return {"error": str(exc)[:300]}


def run_all() -> dict:
    return {"heartbeat": llm_heartbeat(), "upstox": upstox_check(), "freshness": data_freshness(), "holidays": holidays_refresh()}
