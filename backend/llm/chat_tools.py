"""
Tools the chat assistant can call. Each reads the app's own data or the web,
returns compact JSON-able results, and never raises (errors come back as text
so the model can say "I couldn't look that up").
"""

from __future__ import annotations

import logging
from typing import Optional

from langchain_core.tools import tool
from sqlalchemy import func, select

from config import settings
from database import DailyValuation, FactorScore, ModelRun, Portfolio, Prediction, SessionLocal

logger = logging.getLogger(__name__)


def _sym(symbol: str) -> str:
    s = symbol.strip().upper()
    return s if s.endswith(".NS") else f"{s}.NS"


def _short(t: str) -> str:
    return t.replace(".NS", "")


# ── Buy Rank ───────────────────────────────────────────────────────────────

@tool
def get_rank_detail(symbol: str) -> dict:
    """Latest Strength Score (buy_rank) for one NSE stock: score 1–100, band, sector, price, the factor values
    behind it (in plain units) and each factor's contribution. Use for any question about
    why a specific stock ranks where it does."""
    from llm.explain import _fmt_raw
    with SessionLocal() as db:
        s = db.execute(select(FactorScore).where(FactorScore.ticker == _sym(symbol))
                       .order_by(FactorScore.date.desc()).limit(1)).scalar_one_or_none()
        if not s:
            return {"error": f"No Buy Rank found for {symbol}. It may not be in the NIFTY 500 or may be ineligible."}
        hist = db.execute(select(FactorScore.date, FactorScore.buy_rank).where(FactorScore.ticker == s.ticker)
                          .order_by(FactorScore.date.desc()).limit(30)).all()
        return {
            "symbol": _short(s.ticker), "date": str(s.date), "buy_rank": s.buy_rank, "band": s.band,
            "sector": s.sector, "price": s.close, "eligible": bool(s.eligible),
            "factor_values": _fmt_raw(s.raw or {}), "contributions": s.contributions,
            "rank_30_days_ago": hist[-1][1] if hist else None,
            "rank_trend": "rising" if hist and hist[0][1] > hist[-1][1] + 5 else "falling" if hist and hist[0][1] < hist[-1][1] - 5 else "steady",
        }


@tool
def list_ranks(sector: Optional[str] = None, band: Optional[str] = None, limit: int = 10, lowest: bool = False) -> dict:
    """Top (or lowest) Strength Score stocks today, optionally filtered by sector or band
    (Strong/Good/Neutral/Weak). Use for 'which stocks look strongest in X', 'best ranked', etc."""
    limit = max(1, min(int(limit), 40))
    with SessionLocal() as db:
        d = db.execute(select(func.max(FactorScore.date))).scalar()
        if not d:
            return {"error": "No ranks computed yet."}
        q = select(FactorScore).where(FactorScore.date == d)
        if sector:
            q = q.where(FactorScore.sector.ilike(f"%{sector}%"))
        if band:
            q = q.where(FactorScore.band.ilike(band))
        q = q.order_by(FactorScore.buy_rank.asc() if lowest else FactorScore.buy_rank.desc(), FactorScore.topsis.desc()).limit(limit)
        rows = db.execute(q).scalars().all()
        return {"date": str(d), "count": len(rows), "stocks": [
            {"symbol": _short(r.ticker), "buy_rank": r.buy_rank, "band": r.band, "sector": r.sector, "price": r.close} for r in rows]}


@tool
def list_sectors() -> dict:
    """Sectors in the NIFTY 500 with stock counts and average Buy Rank today."""
    with SessionLocal() as db:
        d = db.execute(select(func.max(FactorScore.date))).scalar()
        rows = db.execute(select(FactorScore.sector, func.count(), func.avg(FactorScore.buy_rank))
                          .where(FactorScore.date == d).group_by(FactorScore.sector)
                          .order_by(func.avg(FactorScore.buy_rank).desc())).all()
        return {"date": str(d), "sectors": [{"sector": s, "stocks": n, "avg_rank": round(a, 1)} for s, n, a in rows]}


@tool
def explain_rank(symbol: str) -> dict:
    """Plain-English 'why this rank' bullets for a stock, generated from its factor table
    and audited so every number is real. Cached per day."""
    from llm.explain import explain_rank as _explain
    with SessionLocal() as db:
        out = _explain(db, _sym(symbol))
        return out or {"error": f"No Buy Rank for {symbol}"}


# ── Predictions ────────────────────────────────────────────────────────────

def _latest_run(db):
    return db.execute(select(ModelRun).order_by(ModelRun.as_of.desc(), ModelRun.id.desc()).limit(1)).scalar_one_or_none()


@tool
def get_prediction(symbol: str) -> dict:
    """Model odds that a stock beats the market over the next 3 months, its percentile among
    peers, and how accurate the model has been out of sample. Always present odds as odds."""
    with SessionLocal() as db:
        run = _latest_run(db)
        if not run:
            return {"error": "No prediction model has been trained yet."}
        p = db.execute(select(Prediction).where(Prediction.ticker == _sym(symbol), Prediction.date == run.as_of)).scalars().first()
        if not p:
            return {"error": f"No prediction for {symbol} on {run.as_of}."}
        return {"symbol": _short(p.ticker), "date": str(p.date), "horizon_trading_days": p.horizon,
                "odds_beat_market_pct": round(p.prob_up * 100, 1), "percentile_among_peers": p.pct_rank,
                "sector": p.sector, "model_out_of_sample": run.meta.get("oos"), "history_years": run.meta.get("history_years")}


@tool
def top_predictions(limit: int = 10, sector: Optional[str] = None) -> dict:
    """Stocks with the best model odds of beating the market over the next 3 months,
    plus the model's out-of-sample track record and today's 'what type of stock rises' profiles."""
    limit = max(1, min(int(limit), 40))
    with SessionLocal() as db:
        run = _latest_run(db)
        if not run:
            return {"error": "No prediction model has been trained yet."}
        q = select(Prediction).where(Prediction.date == run.as_of)
        if sector:
            q = q.where(Prediction.sector.ilike(f"%{sector}%"))
        rows = db.execute(q.order_by(Prediction.prob_up.desc()).limit(limit)).scalars().all()
        return {
            "date": str(run.as_of), "history_years": run.meta.get("history_years"), "out_of_sample": run.meta.get("oos"),
            "stocks": [{"symbol": _short(r.ticker), "odds_pct": round(r.prob_up * 100, 1), "sector": r.sector} for r in rows],
            "trait_profiles_today": run.meta.get("profiles", [])[:5],
            "sector_outlook_top5": run.meta.get("sectors", [])[:5],
            "band_base_rates": run.meta.get("band_base_rates", []),
        }


# ── Arena ──────────────────────────────────────────────────────────────────

@tool
def arena_today() -> dict:
    """The AI Arena's latest round: each AI manager's portfolio, holdings with reasoning,
    risk level and current return."""
    with SessionLocal() as db:
        d = db.execute(select(func.max(Portfolio.date))).scalar()
        if not d:
            return {"error": "No Arena round has been run yet."}
        ps = db.execute(select(Portfolio).where(Portfolio.date == d)).scalars().all()
        out = []
        for p in ps:
            v = db.execute(select(DailyValuation).where(DailyValuation.portfolio_id == p.id)
                           .order_by(DailyValuation.date.desc()).limit(1)).scalar_one_or_none()
            out.append({
                "manager": p.model, "risk_level": p.risk_level, "strategy": p.strategy_summary,
                "return_pct": v.return_pct if v else None, "value": v.portfolio_value if v else None,
                "holdings": [{"symbol": _short(h.ticker), "weight_pct": h.allocation_percent, "confidence": h.confidence,
                              "entry_price": h.entry_price, "why": h.reasoning} for h in p.holdings],
            })
        return {"date": str(d), "managers": out}


@tool
def arena_leaderboard() -> dict:
    """All-time AI Arena leaderboard: average return, win rate, best and worst day per manager."""
    with SessionLocal() as db:
        models = [r[0] for r in db.query(Portfolio.model).distinct().all()]
        out = []
        for m in models:
            vals = db.execute(select(DailyValuation.return_pct).join(Portfolio).where(Portfolio.model == m)).scalars().all()
            if not vals:
                continue
            out.append({"manager": m, "rounds": len(vals), "avg_return_pct": round(sum(vals) / len(vals), 3),
                        "win_rate_pct": round(100 * sum(1 for v in vals if v > 0) / len(vals), 1),
                        "best_pct": round(max(vals), 3), "worst_pct": round(min(vals), 3)})
        out.sort(key=lambda r: -r["avg_return_pct"])
        return {"leaderboard": out}


# ── Web ────────────────────────────────────────────────────────────────────

@tool
def web_search(query: str, recent_news: bool = False) -> dict:
    """Search the web with DuckDuckGo. Use for anything not in the app's data: company news,
    what a term means, macro events, results dates. Set recent_news=True for news. Cite the
    source title and URL when you use a result."""
    if not settings.CHAT_WEB_SEARCH:
        return {"error": "Web search is disabled."}
    try:
        from ddgs import DDGS
        with DDGS() as d:
            if recent_news:
                rows = d.news(query, region="in-en", max_results=6)
                return {"query": query, "results": [{"title": r.get("title"), "url": r.get("url"), "date": r.get("date"),
                                                      "source": r.get("source"), "snippet": (r.get("body") or "")[:300]} for r in rows]}
            rows = d.text(query, region="in-en", max_results=6)
            return {"query": query, "results": [{"title": r.get("title"), "url": r.get("href"),
                                                  "snippet": (r.get("body") or "")[:300]} for r in rows]}
    except Exception as exc:                            # noqa: BLE001
        logger.warning("web_search failed: %s", exc)
        return {"error": f"Search failed: {exc}"}


TOOLS = [get_rank_detail, list_ranks, list_sectors, explain_rank, get_prediction, top_predictions,
         arena_today, arena_leaderboard, web_search]
