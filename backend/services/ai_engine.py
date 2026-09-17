import json
import logging
import re
from typing import Dict, List, Optional

from openai import AsyncOpenAI

from config import settings

logger = logging.getLogger(__name__)

# ── Client ─────────────────────────────────────────────────────────────────
_client: Optional[AsyncOpenAI] = None

def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url=settings.AICREDITS_BASE_URL,
            api_key=settings.AICREDITS_API_KEY,
        )
    return _client


# ── Model registry ─────────────────────────────────────────────────────────
SUPPORTED_MODELS: Dict[str, str] = {
    "gpt":      "gpt-4o-mini",
    "gemini":   "gemini-2.5-flash-lite-preview-09-2025",
    "mistral":  "mistralai/voxtral-small-24b-2507",
    "deepseek": "deepseek/deepseek-v4-flash",
}

# Each model gets a distinct investment philosophy in its system prompt
MODEL_PERSONALITIES: Dict[str, str] = {
    "gpt": (
        "You are a disciplined quantitative portfolio manager at a top hedge fund. "
        "Your philosophy: risk-adjusted returns through diversification. "
        "Balance momentum with stability. Equal-weight across 4-5 stocks. "
        "Avoid highly overbought stocks (RSI > 75)."
    ),
    "gemini": (
        "You are an aggressive growth fund manager. "
        "Chase the strongest momentum stocks. Concentrate 60-70% in your top 2-3 picks. "
        "Prioritise the highest TOPSIS scores and volume surges. "
        "Accept higher volatility in exchange for higher returns."
    ),
    "mistral": (
        "You are a conservative value-oriented fund manager. "
        "Capital preservation is priority one. Prefer RSI 40-60 (not overbought). "
        "Spread across 5-7 stocks. Favour Healthcare, Consumer Staples, Utilities. "
        "Avoid extreme volatility (> 40%)."
    ),
    "deepseek": (
        "You are a systematic quantitative analyst. "
        "Follow TOPSIS scores strictly: higher score → higher allocation. "
        "Minimum 3, maximum 5 holdings. Allocation weights proportional to TOPSIS rank. "
        "Pure data-driven selection, no narrative bias."
    ),
}


# ── Prompt builder ─────────────────────────────────────────────────────────

def _format_candidates(candidates: List[Dict]) -> str:
    header = (
        f"{'#':<3} {'Ticker':<15} {'Price':>8} {'TOPSIS':>8} "
        f"{'RSI':>6} {'1M%':>7} {'VolRatio':>9} {'Vol%':>7} {'Sector'}"
    )
    sep = "─" * 90
    rows = [header, sep]
    for i, c in enumerate(candidates, 1):
        rows.append(
            f"{i:<3} {c['ticker']:<15} {c['current_price']:>8.1f} "
            f"{c['topsis_score']:>8.4f} {c['rsi']:>6.1f} "
            f"{c['one_month_return']:>6.1f}% "
            f"{c['volume_ratio']:>9.2f}x "
            f"{c['volatility']:>6.1f}% "
            f"{c.get('sector', 'Unknown')}"
        )
    return "\n".join(rows)


def _format_prev_context(prev: Optional[Dict]) -> str:
    if not prev:
        return "No prior portfolio (Day 1)."
    lines = [
        f"Last portfolio return : {prev.get('last_return', 0):+.2f}%",
        f"Avg return so far     : {prev.get('avg_return', 0):+.2f}%",
    ]
    if prev.get("last_holdings"):
        tickers = ", ".join(
            h["ticker"].replace(".NS", "") for h in prev["last_holdings"][:6]
        )
        lines.append(f"Previous holdings     : {tickers}")
    return "\n".join(lines)


def build_prompt(
    model_name: str,
    candidates: List[Dict],
    starting_capital: float,
    prev_context: Optional[Dict] = None,
) -> str:
    personality  = MODEL_PERSONALITIES.get(model_name, MODEL_PERSONALITIES["gpt"])
    cand_table   = _format_candidates(candidates)
    prev_section = _format_prev_context(prev_context)

    return f"""You are managing a simulated Indian equity portfolio for an AI Hedge Fund Arena.

INVESTMENT PHILOSOPHY:
{personality}

STARTING CAPITAL: ₹{starting_capital:,.0f} INR
PRIOR PERFORMANCE:
{prev_section}

NIFTY200 TOPSIS-RANKED CANDIDATES (today's shortlist):
{cand_table}

TASK:
Select 3–7 stocks from the table ONLY.
Allocate the FULL ₹{starting_capital:,.0f} across your picks.

STRICT OUTPUT FORMAT — respond with ONLY valid JSON, no text before or after:
{{
  "portfolio": [
    {{
      "ticker": "TICKER.NS",
      "allocation_percent": 30,
      "confidence": 85,
      "reasoning": "1-2 sentence rationale"
    }}
  ],
  "strategy_summary": "One sentence on your overall strategy today.",
  "risk_level": "conservative"
}}

Rules:
- allocation_percent integers, must sum to 100
- Only tickers from the candidate table
- confidence: integer 50–100
- risk_level: one of conservative | moderate | aggressive
"""


# ── Response parser ────────────────────────────────────────────────────────

def _parse_response(raw: str) -> Dict:
    # Strip markdown fences
    raw = re.sub(r"```(?:json)?|```", "", raw).strip()

    # Extract first JSON object
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        raw = m.group()

    data = json.loads(raw)

    portfolio = data.get("portfolio")
    if not portfolio or len(portfolio) < 3:
        raise ValueError(f"Too few holdings: {len(portfolio) if portfolio else 0}")
    if len(portfolio) > 7:
        portfolio = portfolio[:7]
        data["portfolio"] = portfolio

    # Normalise allocation to exactly 100
    total = sum(h["allocation_percent"] for h in portfolio)
    if total <= 0:
        raise ValueError("Allocations sum to zero")
    if abs(total - 100) > 0.5:
        for h in portfolio:
            h["allocation_percent"] = round(h["allocation_percent"] / total * 100, 2)
        # Fix rounding drift on last item
        diff = 100 - sum(h["allocation_percent"] for h in portfolio)
        portfolio[-1]["allocation_percent"] = round(portfolio[-1]["allocation_percent"] + diff, 2)

    return data


# ── Main entry point ───────────────────────────────────────────────────────

async def generate_portfolio(
    model_name: str,
    candidates: List[Dict],
    starting_capital: float,
    prev_context: Optional[Dict] = None,
) -> Dict:
    """
    Call the LLM and return an enriched portfolio dict ready for DB insertion.
    Retries up to 3 times on parse failure.
    """
    prompt     = build_prompt(model_name, candidates, starting_capital, prev_context)
    model_id   = SUPPORTED_MODELS[model_name]
    client     = get_client()
    last_error = None

    for attempt in range(1, 4):
        try:
            logger.info(f"[{model_name}] LLM call attempt {attempt}...")
            resp = await client.chat.completions.create(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.65,
                max_tokens=1800,
            )
            raw    = resp.choices[0].message.content or ""
            parsed = _parse_response(raw)

            # Build candidate price lookup
            price_map = {c["ticker"]: c for c in candidates}

            total_invested = 0.0
            for h in parsed["portfolio"]:
                alloc       = h["allocation_percent"] / 100
                invested    = round(starting_capital * alloc, 2)
                stock_info  = price_map.get(h["ticker"], {})
                entry_price = stock_info.get("current_price", 0.0)
                quantity    = round(invested / entry_price, 4) if entry_price > 0 else 0.0

                h["invested_amount"]    = invested
                h["entry_price"]        = entry_price
                h["quantity"]           = quantity
                h["sector"]             = stock_info.get("sector", "Unknown")
                total_invested         += invested

            return {
                "model":            model_name,
                "starting_capital": starting_capital,
                "remaining_cash":   round(starting_capital - total_invested, 2),
                "total_invested":   round(total_invested, 2),
                "portfolio":        parsed["portfolio"],
                "strategy_summary": parsed.get("strategy_summary", ""),
                "risk_level":       parsed.get("risk_level", "moderate"),
            }

        except Exception as exc:
            last_error = exc
            logger.warning(f"[{model_name}] Attempt {attempt} failed: {exc}")

    raise RuntimeError(f"[{model_name}] All LLM attempts failed. Last error: {last_error}")