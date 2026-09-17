"""
Alerts: the one place every "a human should know" event goes.

raise_alert() writes/updates a SystemAlert row (one open row per kind), logs
it, and pushes it to Telegram and/or a webhook if configured. resolve()
closes it. Notifications are sent at most once per open alert per 6 hours so
a flapping gateway does not spam you.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from database import SessionLocal, SystemAlert

logger = logging.getLogger(__name__)

RENOTIFY_AFTER = timedelta(hours=6)
SEVERITIES = ("info", "warning", "critical")

# Human wording for the kinds the system raises itself.
KIND_HELP = {
    "credits_exhausted": "The LLM gateway is refusing calls because the credits are used up. Top up at your gateway, then the next heartbeat clears this.",
    "credits_low": "At the current burn rate the LLM credits will run out soon. Top up before the date shown.",
    "llm_auth_failed": "The gateway rejected the API key (401). Check AICREDITS_API_KEY in backend/.env and restart.",
    "llm_gateway_down": "The LLM gateway is unreachable. Voxa, explanations and the AI managers pause until it is back; nothing else is affected.",
    "upstox_token_expired": "Upstox rejected the token for market data. A daily access token dies at 03:30 IST; an extended token lasts a year. Generate a new one at Upstox, put it in UPSTOX_ANALYTICS_TOKEN, restart. Until then daily bars come from the fallback.",
    "upstox_token_expiring": "The Upstox token is about to expire. Generate a new one and update UPSTOX_ANALYTICS_TOKEN before the date shown.",
    "data_stale": "No fresh daily bars arrived for a trading day. Check the nightly job and the data source.",
    "ranks_stale": "Strength Scores were not recomputed for the latest bars.",
    "predictor_stale": "The 3-Month Odds model has not retrained for more than two weeks.",
    "holidays_unrefreshed": "The NSE holiday list could not be refreshed; fixed national holidays are the fallback for future years.",
}


def _push(kind: str, severity: str, message: str, detail: str | None) -> bool:
    text = f"[Nivesha] {severity.upper()} · {kind}\n{message}" + (f"\n{detail[:800]}" if detail else "")
    sent = False
    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
        try:
            httpx.post(f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
                       json={"chat_id": settings.TELEGRAM_CHAT_ID, "text": text}, timeout=10).raise_for_status()
            sent = True
        except Exception as exc:                    # noqa: BLE001
            logger.warning("telegram push failed: %s", exc)
    if settings.ALERT_WEBHOOK_URL:
        try:
            httpx.post(settings.ALERT_WEBHOOK_URL, json={"kind": kind, "severity": severity, "message": message,
                                                         "detail": detail, "text": text}, timeout=10).raise_for_status()
            sent = True
        except Exception as exc:                    # noqa: BLE001
            logger.warning("webhook push failed: %s", exc)
    return sent


def raise_alert(kind: str, message: str, severity: str = "warning", detail: str | None = None, db: Session | None = None) -> SystemAlert:
    assert severity in SEVERITIES
    own = db is None
    db = db or SessionLocal()
    try:
        row = db.execute(select(SystemAlert).where(SystemAlert.kind == kind, SystemAlert.resolved_at.is_(None))).scalar_one_or_none()
        now = datetime.utcnow()
        if row:
            row.count = (row.count or 1) + 1
            row.last_seen = now
            row.message = message
            row.detail = detail
            if severity == "critical":
                row.severity = "critical"
        else:
            row = SystemAlert(kind=kind, severity=severity, message=message, detail=detail)
            db.add(row)
        db.flush()
        log = logger.critical if severity == "critical" else logger.warning if severity == "warning" else logger.info
        log("ALERT %s: %s", kind, message)
        if row.notified_at is None or now - row.notified_at > RENOTIFY_AFTER:
            if _push(kind, row.severity, message, detail):
                row.notified_at = now
        db.commit()
        db.refresh(row)
        db.expunge(row)          # usable after the session closes (no lazy loads needed)
        return row
    finally:
        if own:
            db.close()


def resolve(kind: str, db: Session | None = None) -> bool:
    own = db is None
    db = db or SessionLocal()
    try:
        row = db.execute(select(SystemAlert).where(SystemAlert.kind == kind, SystemAlert.resolved_at.is_(None))).scalar_one_or_none()
        if not row:
            return False
        row.resolved_at = datetime.utcnow()
        db.commit()
        logger.info("alert resolved: %s", kind)
        return True
    finally:
        if own:
            db.close()


def open_alerts(db: Session) -> list[SystemAlert]:
    return db.execute(select(SystemAlert).where(SystemAlert.resolved_at.is_(None))
                      .order_by(SystemAlert.severity.desc(), SystemAlert.last_seen.desc())).scalars().all()


# ── LLM error classification (shared by chat, explain, arena, heartbeat) ───

def classify_llm_error(exc: BaseException) -> tuple[str, str]:
    """→ (kind, severity). Walks the cause chain and looks at status codes and wording."""
    chain, e = [], exc
    while e is not None and len(chain) < 6:
        chain.append(e)
        e = e.__cause__ or e.__context__
    text = " ".join(f"{type(c).__name__} {c}" for c in chain).lower()
    status = next((getattr(c, "status_code", None) for c in chain if getattr(c, "status_code", None)), None)
    if status == 402 or any(w in text for w in ("insufficient", "credit", "quota", "billing", "balance", "payment required", "exceeded your")):
        return "credits_exhausted", "critical"
    if status == 401 or "invalid api key" in text or "unauthorized" in text or "incorrect api key" in text:
        return "llm_auth_failed", "critical"
    if status == 429:
        return "llm_rate_limited", "warning"
    if any(w in text for w in ("connection", "timeout", "timed out", "reset by peer", "unreachable", "gatewaydown", "502", "503", "504")):
        return "llm_gateway_down", "warning"
    return "llm_error", "warning"


def report_llm_failure(exc: BaseException, feature: str) -> str:
    kind, severity = classify_llm_error(exc)
    raise_alert(kind, f"{KIND_HELP.get(kind, 'An LLM call failed.')} (while: {feature})", severity, detail=f"{type(exc).__name__}: {exc}"[:1500])
    return kind
