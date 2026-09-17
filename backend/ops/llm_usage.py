"""
Meter every model call and project when the credits run out.

A LangChain callback (attached in llm/gateway.py) records tokens per
(day, model, feature). Cost is an estimate from a public price table (USD per
1M tokens) — override with LLM_PRICES_JSON if your gateway prices differ. If
LLM_CREDITS_USD / LLM_CREDITS_AS_OF are set, the projection subtracts the
estimated spend since that date and divides by the 30-day burn rate.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import settings
from database import LlmUsage, SessionLocal

logger = logging.getLogger(__name__)

# USD per 1M tokens: (input, output). Estimates as of 2026; edit via LLM_PRICES_JSON.
DEFAULT_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60), "openai/gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4.1-nano": (0.10, 0.40), "gpt-4.1-nano": (0.10, 0.40),
    "openai/gpt-4.1-mini": (0.40, 1.60), "gpt-5-mini": (0.25, 2.00), "gpt-5-nano": (0.05, 0.40),
    "google/gemini-2.5-flash": (0.30, 2.50), "gemini-2.5-flash-lite-preview-09-2025": (0.10, 0.40),
    "deepseek/deepseek-v3.2": (0.28, 0.42), "mistralai/voxtral-small-24b-2507": (0.10, 0.30),
    "anthropic/claude-haiku-4.5": (1.00, 5.00),
}
FALLBACK_PRICE = (0.50, 1.50)

FEATURE_TAGS = ("chat", "guard", "compress", "explain", "arena", "heartbeat", "intel")


def prices() -> dict[str, tuple[float, float]]:
    table = dict(DEFAULT_PRICES)
    if settings.LLM_PRICES_JSON:
        try:
            table.update({k: (float(v[0]), float(v[1])) for k, v in json.loads(settings.LLM_PRICES_JSON).items()})
        except Exception as exc:                    # noqa: BLE001
            logger.warning("LLM_PRICES_JSON ignored: %s", exc)
    return table


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pin, pout = prices().get(model, FALLBACK_PRICE)
    return (input_tokens * pin + output_tokens * pout) / 1_000_000


def record(model: str, feature: str, input_tokens: int, output_tokens: int, error: bool = False) -> None:
    """Upsert one call into today's (model, feature) row."""
    try:
        with SessionLocal() as db:
            row = db.execute(select(LlmUsage).where(LlmUsage.date == date.today(), LlmUsage.model == model,
                                                    LlmUsage.feature == feature)).scalar_one_or_none()
            if row is None:
                row = LlmUsage(date=date.today(), model=model, feature=feature)
                db.add(row)
            row.calls = (row.calls or 0) + 1
            row.input_tokens = (row.input_tokens or 0) + input_tokens
            row.output_tokens = (row.output_tokens or 0) + output_tokens
            row.est_cost_usd = (row.est_cost_usd or 0.0) + estimate_cost(model, input_tokens, output_tokens)
            if error:
                row.errors = (row.errors or 0) + 1
            db.commit()
    except Exception as exc:                        # noqa: BLE001 — metering must never break a request
        logger.debug("usage record skipped: %s", exc)


class UsageRecorder(BaseCallbackHandler):
    """Attach to every ChatOpenAI; picks the feature from the run's tags."""

    def __init__(self) -> None:
        self._runs: dict[UUID, tuple[str, str]] = {}

    def on_chat_model_start(self, serialized: dict, messages: Any, *, run_id: UUID, tags: list[str] | None = None,
                            metadata: dict | None = None, **kwargs: Any) -> None:
        params = kwargs.get("invocation_params") or {}
        model = params.get("model_name") or params.get("model") or (serialized or {}).get("kwargs", {}).get("model_name") or "unknown"
        feature = next((t for t in (tags or []) if t in FEATURE_TAGS), "other")
        self._runs[run_id] = (model, feature)

    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        model, feature = self._runs.pop(run_id, ("unknown", "other"))
        usage = {}
        try:
            usage = (response.llm_output or {}).get("token_usage") or {}
            if not usage:
                gen = response.generations[0][0]
                um = getattr(getattr(gen, "message", None), "usage_metadata", None) or {}
                usage = {"prompt_tokens": um.get("input_tokens", 0), "completion_tokens": um.get("output_tokens", 0)}
        except Exception:                           # noqa: BLE001
            usage = {}
        record(model, feature, int(usage.get("prompt_tokens", 0) or 0), int(usage.get("completion_tokens", 0) or 0))

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        model, feature = self._runs.pop(run_id, ("unknown", "other"))
        record(model, feature, 0, 0, error=True)


recorder = UsageRecorder()


# ── Daily budget (₹) ───────────────────────────────────────────────────────

_budget_cache: dict = {"day": None, "at": 0.0, "spent_usd": 0.0}


def today_spend_usd(db: Session | None = None) -> float:
    own = db is None
    db = db or SessionLocal()
    try:
        return float(db.execute(select(func.coalesce(func.sum(LlmUsage.est_cost_usd), 0.0)).where(LlmUsage.date == date.today())).scalar() or 0.0)
    finally:
        if own:
            db.close()


def budget_status(db: Session | None = None) -> dict:
    """Today's estimated spend against LLM_DAILY_BUDGET_INR."""
    spent_usd = today_spend_usd(db)
    spent_inr = spent_usd * settings.USD_INR
    cap = settings.LLM_DAILY_BUDGET_INR
    return {
        "budget_inr": cap, "spent_inr": round(spent_inr, 4), "spent_usd": round(spent_usd, 6),
        "remaining_inr": round(max(0.0, cap - spent_inr), 4) if cap > 0 else None,
        "pct_used": round(100 * spent_inr / cap, 1) if cap > 0 else None,
        "exhausted": cap > 0 and spent_inr >= cap, "usd_inr": settings.USD_INR,
    }


def budget_exhausted() -> bool:
    """Cheap check before an optional model call; cached for 20 s so chat turns don't hammer the DB."""
    import time
    cap = settings.LLM_DAILY_BUDGET_INR
    if cap <= 0:
        return False
    now = time.monotonic()
    if _budget_cache["day"] != date.today() or now - _budget_cache["at"] > 20:
        try:
            _budget_cache.update(day=date.today(), at=now, spent_usd=today_spend_usd())
        except Exception:                           # noqa: BLE001 — never block on a metering hiccup
            return False
    return _budget_cache["spent_usd"] * settings.USD_INR >= cap


def enforce_budget(feature: str) -> bool:
    """True if the call may proceed. On the first refusal of the day raises an info alert."""
    if not budget_exhausted():
        return True
    from ops.alerts import raise_alert
    raise_alert("budget_exceeded", f"Today's AI budget of ₹{settings.LLM_DAILY_BUDGET_INR:.0f} is used up; optional AI features "
                f"(Voxa, explanations, AI managers) pause until midnight. Raise LLM_DAILY_BUDGET_INR to change this. (blocked: {feature})", "info")
    return False


BUDGET_MESSAGE = "Today's AI budget (₹{cap:.0f}) is used up, so I can't call the model right now. Everything on the page still works; I'm back after midnight."


# ── Reporting and projection ───────────────────────────────────────────────

def summary(db: Session) -> dict:
    today = date.today()
    d30 = today - timedelta(days=30)

    def agg(since: date | None):
        q = select(func.coalesce(func.sum(LlmUsage.calls), 0), func.coalesce(func.sum(LlmUsage.input_tokens), 0),
                   func.coalesce(func.sum(LlmUsage.output_tokens), 0), func.coalesce(func.sum(LlmUsage.est_cost_usd), 0.0),
                   func.coalesce(func.sum(LlmUsage.errors), 0))
        if since:
            q = q.where(LlmUsage.date >= since)
        c, i, o, cost, e = db.execute(q).one()
        return {"calls": int(c), "input_tokens": int(i), "output_tokens": int(o), "est_cost_usd": round(float(cost), 4), "errors": int(e)}

    today_s, m30, total = agg(today), agg(d30), agg(None)
    first = db.execute(select(func.min(LlmUsage.date))).scalar()
    days_metered = max(1, min(30, (today - first).days + 1)) if first else 1
    burn_per_day = m30["est_cost_usd"] / days_metered

    by_feature = [{"feature": f, "calls": int(c), "est_cost_usd": round(float(cost), 4)} for f, c, cost in db.execute(
        select(LlmUsage.feature, func.sum(LlmUsage.calls), func.sum(LlmUsage.est_cost_usd)).where(LlmUsage.date >= d30)
        .group_by(LlmUsage.feature).order_by(func.sum(LlmUsage.est_cost_usd).desc())).all()]
    by_model = [{"model": m, "calls": int(c), "est_cost_usd": round(float(cost), 4)} for m, c, cost in db.execute(
        select(LlmUsage.model, func.sum(LlmUsage.calls), func.sum(LlmUsage.est_cost_usd)).where(LlmUsage.date >= d30)
        .group_by(LlmUsage.model).order_by(func.sum(LlmUsage.est_cost_usd).desc())).all()]
    daily = [{"date": str(d), "est_cost_usd": round(float(cost), 4), "calls": int(c)} for d, cost, c in db.execute(
        select(LlmUsage.date, func.sum(LlmUsage.est_cost_usd), func.sum(LlmUsage.calls)).where(LlmUsage.date >= d30)
        .group_by(LlmUsage.date).order_by(LlmUsage.date)).all()]

    projection = None
    if settings.LLM_CREDITS_USD > 0 and settings.LLM_CREDITS_AS_OF:
        try:
            as_of = date.fromisoformat(settings.LLM_CREDITS_AS_OF)
            spent = db.execute(select(func.coalesce(func.sum(LlmUsage.est_cost_usd), 0.0)).where(LlmUsage.date >= as_of)).scalar()
            remaining = settings.LLM_CREDITS_USD - float(spent)
            days_left = (remaining / burn_per_day) if burn_per_day > 0 else None
            projection = {
                "balance_usd": settings.LLM_CREDITS_USD, "as_of": str(as_of), "spent_since_usd": round(float(spent), 4),
                "remaining_usd": round(remaining, 4), "remaining_pct": round(100 * remaining / settings.LLM_CREDITS_USD, 1),
                "burn_per_day_usd": round(burn_per_day, 4),
                "days_left": None if days_left is None else round(days_left, 1),
                "runs_out_on": None if days_left is None else str(today + timedelta(days=int(days_left))),
            }
        except ValueError:
            projection = {"error": "LLM_CREDITS_AS_OF must be an ISO date like 2026-09-17"}

    return {"today": today_s, "last_30_days": m30, "all_time": total, "burn_per_day_usd": round(burn_per_day, 4),
            "budget": budget_status(db),
            "by_feature_30d": by_feature, "by_model_30d": by_model, "daily_30d": daily, "projection": projection,
            "note": "Costs are estimates from a public price table; your gateway may bill differently. Set LLM_CREDITS_USD and LLM_CREDITS_AS_OF for a run-out date."}


def check_credit_projection(db: Session) -> dict | None:
    """Raise/resolve the credits_low alert from the projection. Called by the daily heartbeat."""
    from ops.alerts import raise_alert, resolve
    s = summary(db)
    p = s.get("projection")
    if not p or "error" in p:
        return None
    low = p["remaining_pct"] < settings.ALERT_CREDITS_LOW_PCT or (p["days_left"] is not None and p["days_left"] < settings.ALERT_CREDITS_LOW_DAYS)
    if p["remaining_usd"] <= 0:
        raise_alert("credits_exhausted", f"Estimated LLM credits are used up (balance ${p['balance_usd']:.2f} on {p['as_of']}, "
                    f"≈${p['spent_since_usd']:.2f} spent since). Top up and update LLM_CREDITS_USD / LLM_CREDITS_AS_OF.", "critical", db=db)
    elif low:
        raise_alert("credits_low", f"≈${p['remaining_usd']:.2f} of ${p['balance_usd']:.2f} left ({p['remaining_pct']}%); at ≈${p['burn_per_day_usd']:.3f}/day "
                    f"that is about {p['days_left']} days — runs out around {p['runs_out_on']}.", "warning", db=db)
    else:
        resolve("credits_low", db=db)
    return p
