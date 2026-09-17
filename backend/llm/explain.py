"""
"Why this rank?" — a small LangGraph graph with a hard grounding loop.

    START → generate → audit ─┬─ ok ─────────→ END
                              ├─ retry ──────→ generate (with the audit errors)
                              └─ strip ──────→ END (offending bullets removed)

The model sees only the factor table for one stock. Every number it writes is
checked against that table. Without an API key the deterministic template is
used, so the endpoint always answers.
"""

from __future__ import annotations

import logging
import math
from datetime import date as DateType
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from database import FactorScore, RankExplanation
from llm.audit import allowed_from, offending_numbers
from llm.gateway import llm_available, run_config, structured
from quant.factors import FACTOR_NAMES

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2


# ── Schema ─────────────────────────────────────────────────────────────────

class Explanation(BaseModel):
    bullets: list[str] = Field(
        description="Exactly three short plain-English sentences, each about one factor. "
                    "Quote numbers only from the table. No advice, no prediction.",
        min_length=3, max_length=3,
    )
    watch_out: str = Field(
        description="One sentence on the biggest weakness or risk visible in the table.",
    )


class ExplainState(TypedDict, total=False):
    ticker: str
    date: str
    rank: int
    band: str
    table: str
    allowed: set[str]
    draft: dict | None
    offending: list[str]
    attempts: int
    dropped: int
    final: dict | None


# ── Human-readable factor table ────────────────────────────────────────────

LABELS = {
    "mom_12_1":  "12-month momentum (skipping last month)",
    "mom_6_1":   "6-month momentum (skipping last month)",
    "trend":     "Trend quality (time above 50-day average, slope)",
    "low_vol":   "Calmness (lower volatility is better)",
    "liquidity": "Liquidity (how easily it trades)",
    "vol_conf":  "Volume confirmation (recent vs usual volume)",
    "overheat":  "Overheat penalty (recent spike, RSI)",
}


def _fmt_raw(raw: dict) -> dict[str, str]:
    """Raw components in units a person understands."""
    def pct(x):  return None if x is None else f"{(math.exp(x) - 1) * 100:.1f}%"
    def num(x, f="{:.2f}"): return None if x is None else f.format(x)
    g = raw.get
    return {
        "mom_12_1":  pct(g("mom_12_1")),
        "mom_6_1":   pct(g("mom_6_1")),
        "trend":     (f"{(g('trend_frac') or 0) * 100:.0f}% of last 60 days above 50-DMA, "
                      f"50-DMA slope {(g('trend_slope') or 0) * 100:.1f}% over 20 days"),
        "low_vol":   None if g("neg_vol_60") is None else f"volatility {-g('neg_vol_60') * 100:.1f}% a year",
        "liquidity": None if g("log_turnover_20") is None else f"₹{math.exp(g('log_turnover_20')) / 1e7:.1f} crore traded a day",
        "vol_conf":  num(g("vol_conf"), "{:.2f}x usual volume"),
        "overheat":  (f"5-day move {pct(g('ret_5d'))}, RSI {num(g('rsi14'), '{:.0f}')}"),
    }


def build_table(score: FactorScore) -> tuple[str, set[str]]:
    raw_h = _fmt_raw(score.raw or {})
    z, c = score.z or {}, score.contributions or {}
    lines = [
        f"Stock: {score.ticker.replace('.NS', '')}   Date: {score.date}   Strength Score: {score.buy_rank}/100   Band: {score.band}",
        f"Price: {score.close:.2f}   Sector: {score.sector}",
        "",
        f"{'Factor':<52} {'Value':<48} {'Z':>6} {'Weight':>7} {'Contrib':>8}",
        "-" * 125,
    ]
    allowed_vals: list = [score.buy_rank, score.close, str(score.date)]
    for f in FACTOR_NAMES:
        w = settings.FACTOR_WEIGHTS.get(f, 0.0)
        zf, cf = z.get(f), c.get(f)
        val = raw_h.get(f) or "n/a"
        lines.append(f"{LABELS[f]:<52} {val:<48} {_n(zf):>6} {w:>+7.2f} {_n(cf, signed=True):>8}")
        allowed_vals += [zf, cf, w, val]
    table = "\n".join(lines)
    return table, allowed_from(allowed_vals)


def _n(x, signed: bool = False) -> str:
    if x is None:
        return "n/a"
    return f"{x:+.2f}" if signed else f"{x:.2f}"


# ── Deterministic fallback ─────────────────────────────────────────────────

def template_explanation(score: FactorScore) -> dict:
    c = score.contributions or {}
    ranked = sorted(((v or 0.0), k) for k, v in c.items())
    top = [k for _, k in reversed(ranked[-3:])]
    worst = ranked[0][1] if ranked else None
    raw_h = _fmt_raw(score.raw or {})
    bullets = [f"{LABELS[k].split(' (')[0]}: {raw_h.get(k) or 'n/a'} (contribution {_n(c.get(k))})." for k in top]
    return {
        "bullets": bullets,
        "watch_out": (f"Weakest area: {LABELS[worst].split(' (')[0].lower()} at {raw_h.get(worst) or 'n/a'}."
                      if worst else "No weakness stands out in the table."),
        "model": "template",
        "attempts": 0,
        "dropped": 0,
    }


# ── Graph nodes ────────────────────────────────────────────────────────────

SYSTEM = """You explain a stock's Strength Score (a 1–100 percentile, formerly called Buy Rank) to a complete beginner.

Rules, all mandatory:
1. Use ONLY numbers that appear in the table. Never compute, convert, or invent a number.
2. Write exactly three bullets. Each names one factor in plain words and says whether it helped or hurt the rank.
3. No advice ("buy", "sell", "should"), no prediction, no mention of the future.
4. Expand jargon: say "12-month price momentum", not "mom_12_1"; "50-day average price", not "50-DMA".
5. One short sentence per bullet, under 25 words.
6. watch_out: the single biggest weakness in the table, one sentence."""


def generate(state: ExplainState) -> ExplainState:
    user = f"{state['table']}\n\nWrite the three bullets and the watch_out."
    if state.get("offending"):
        user += ("\n\nYour previous draft used numbers that are NOT in the table: "
                 f"{', '.join(state['offending'])}. Rewrite using only numbers from the table.")
    llm = structured(Explanation).with_config(tags=["explain"])
    result: Explanation = llm.invoke([("system", SYSTEM), ("user", user)])
    return {"draft": result.model_dump(), "attempts": state.get("attempts", 0) + 1}


def audit(state: ExplainState) -> ExplainState:
    draft = state["draft"] or {}
    bad: list[str] = []
    for text in [*draft.get("bullets", []), draft.get("watch_out", "")]:
        bad += offending_numbers(text, state["allowed"])
    return {"offending": sorted(set(bad))}


def route(state: ExplainState) -> Literal["ok", "retry", "strip"]:
    if not state["offending"]:
        return "ok"
    return "retry" if state["attempts"] < MAX_ATTEMPTS else "strip"


def strip(state: ExplainState) -> ExplainState:
    draft = dict(state["draft"] or {})
    kept = [b for b in draft.get("bullets", []) if not offending_numbers(b, state["allowed"])]
    dropped = len(draft.get("bullets", [])) - len(kept)
    if offending_numbers(draft.get("watch_out", ""), state["allowed"]):
        draft["watch_out"] = "See the factor table for the weakest area."
        dropped += 1
    draft["bullets"] = kept or ["The rank is driven by the factors in the table above."]
    return {"draft": draft, "dropped": dropped}


def _build_graph():
    g = StateGraph(ExplainState)
    g.add_node("generate", generate)
    g.add_node("audit", audit)
    g.add_node("strip", strip)
    g.add_edge(START, "generate")
    g.add_edge("generate", "audit")
    g.add_conditional_edges("audit", route, {"ok": END, "retry": "generate", "strip": "strip"})
    g.add_edge("strip", END)
    return g.compile()


explain_graph = _build_graph()


# ── Public entry point ─────────────────────────────────────────────────────

def explain_rank(db: Session, ticker: str, as_of: DateType | None = None) -> dict | None:
    """Cached explanation for the latest (or given) FactorScore of `ticker`."""
    stmt = select(FactorScore).where(FactorScore.ticker == ticker)
    if as_of:
        stmt = stmt.where(FactorScore.date <= as_of)
    score = db.execute(stmt.order_by(FactorScore.date.desc()).limit(1)).scalar_one_or_none()
    if score is None:
        return None

    cached = db.execute(
        select(RankExplanation).where(RankExplanation.ticker == ticker, RankExplanation.date == score.date)
    ).scalar_one_or_none()
    if cached:
        return _out(score, cached.bullets, cached.watch_out, cached.model, cached.attempts, cached.audit_dropped, True)

    from ops.llm_usage import enforce_budget
    if not llm_available() or not enforce_budget("explain"):
        t = template_explanation(score)
        return _persist(db, score, t["bullets"], t["watch_out"], "template", 0, 0)

    table, allowed = build_table(score)
    try:
        final = explain_graph.invoke(
            {"ticker": ticker, "date": str(score.date), "rank": score.buy_rank, "band": score.band,
             "table": table, "allowed": allowed, "attempts": 0, "offending": [], "dropped": 0},
            config=run_config("buyrank.explain", ["explain"], ticker=ticker, date=str(score.date)),
        )
        draft = final["draft"]
        return _persist(db, score, draft["bullets"], draft["watch_out"], settings.LLM_MODEL,
                        final.get("attempts", 1), final.get("dropped", 0))
    except Exception as exc:                            # noqa: BLE001 — fall back, never 500
        logger.warning("explain graph failed for %s: %s — using template", ticker, exc)
        try:
            from ops.alerts import report_llm_failure
            report_llm_failure(exc, "explain")
        except Exception:                               # noqa: BLE001
            pass
        t = template_explanation(score)
        return _persist(db, score, t["bullets"], t["watch_out"], "template", 0, 0)


def _persist(db, score, bullets, watch_out, model, attempts, dropped) -> dict:
    db.add(RankExplanation(ticker=score.ticker, date=score.date, bullets=bullets, watch_out=watch_out,
                           model=model, attempts=attempts, audit_dropped=dropped))
    db.commit()
    return _out(score, bullets, watch_out, model, attempts, dropped, False)


def _out(score, bullets, watch_out, model, attempts, dropped, cached) -> dict:
    return {
        "ticker": score.ticker, "date": str(score.date), "buy_rank": score.buy_rank, "band": score.band,
        "bullets": bullets, "watch_out": watch_out,
        "model": model, "attempts": attempts, "audit_dropped": dropped, "cached": cached,
    }
