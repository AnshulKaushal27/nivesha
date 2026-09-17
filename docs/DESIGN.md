# AI Investment Arena v2 — Design

> Quant-to-Newbie engine for NSE. Local first, AWS Free Tier second.
> Written 2026-09-17 against the v1 codebase in this repo.

This document decides three things: which institutional features are worth
building for a beginner, how the multi-LLM Arena works, and how the system runs
locally and then on AWS without a bill.

The standard applied throughout: **a feature earns its place only if it is
measurable out of sample, explainable in one sentence, and buildable on the data
Upstox and NSE actually give you.** Several of the original ideas fail the
third test, and the fixes are more useful than the originals.

---

## Part 1 — Master feature selection

### 1.0 Verdict on the four raw ideas

| Idea | Verdict | Why |
| --- | --- | --- |
| Ultimate Buy Rank (TOPSIS, 1–100) | **Keep, re-found** | TOPSIS is a fine combiner but the current inputs (1M return, volume ratio, RSI distance) are momentum-chasing noise. Replace the inputs with a proper cross-sectional factor set, add a market-regime gate, and report the score as a *percentile* so "72" means the same thing every day. Validate with an information coefficient before shipping. |
| Whale Footprints (U-Net / 1D-CNN segmentation) | **Discard the model, keep the promise** | There are no ground-truth labels for "institutional accumulation". A CNN trained on labels you invented learns your heuristic plus noise. Meanwhile NSE *publishes* real institutional footprints daily: bulk deals, block deals, FII/DII flows, and per-stock delivery percentage. Build on those, plus order-flow imbalance from the tick feed. |
| Radioactive List (GAN / autoencoder on Depth-30 for spoofing) | **Discard as stated, rebuild as "Danger Zone"** | Spoofing detection needs order-level data (order IDs, cancels). Upstox gives aggregated levels only, so a "spoofing" label is unverifiable, and Depth-30 is available for a small set of large caps where retail is not the victim anyway. The real radioactive risk for a beginner is ASM/GSM-listed stocks, operator-driven small caps and pump-and-dump signatures. NSE publishes surveillance lists daily. Combine those hard rules with an Isolation Forest on daily features. An autoencoder on Depth-30 stays as a v2 "unusual order book" flag, never a spoofing claim. |
| Weather Forecast (DuckDuckGo + LLM macro sentiment) | **Keep, make it a regime engine** | Free-text "sentiment" drifts and cannot be backtested. Make the quant half primary (India VIX percentile, breadth, trend, FII flows, options skew) and have the LLM do *structured event extraction* with an explicit decay half-life. Regime output gates every other feature. |

The selected set, in build order:

1. **Buy Rank** — factor composite, regime-gated, percentile score.
2. **Market Weather** — regime engine + structured news events with decay.
3. **Danger Zone** — surveillance lists + manipulation signature + anomaly score.
4. **Whale Footprints** — real institutional flow + intraday order-flow imbalance.

Weather and Danger come before Whale because they need no WebSocket, and
because the Arena (Part 2) consumes them as inputs.

---

### 1.1 Buy Rank

**Universe and hygiene**

- Nifty 500 constituents, refreshed monthly from the NSE index file.
- Exclude: median 20-day turnover below ₹5 Cr, price below ₹20, any ASM/GSM
  stage, less than 250 trading days of history.
- Data: daily OHLCV from Upstox Historical Candle V3, 2 years, refreshed nightly
  (500 calls, well under the 50 req/s limit).

**Factors** (all computed cross-sectionally each day, winsorised at ±3σ,
z-scored across the universe)

| Factor | Formula | Sign | Weight |
| --- | --- | --- | --- |
| Momentum 12-1 | `ln(P[t-21] / P[t-252])` | + | 0.25 |
| Momentum 6-1 | `ln(P[t-21] / P[t-126])` | + | 0.10 |
| Trend quality | share of last 60 days closing above 50-DMA, plus normalised 50-DMA slope | + | 0.20 |
| Low volatility | 60-day realised vol, annualised | − | 0.15 |
| Liquidity | `ln(median 20-day turnover)` | + | 0.10 |
| Volume confirmation | `mean(vol, 20) / mean(vol, 60)`, capped at 3 | + | 0.10 |
| Overheat guard | 5-day return z-score, and RSI(14) above 80 | − | 0.10 |

Momentum skips the most recent month deliberately: one-month returns mean-revert
in Indian mid-caps, and the current v1 score rewards exactly that.

**Combiner**

Keep TOPSIS, since it is already implemented, but feed it the z-scored factor
matrix above with the signed weights. The closeness coefficient
`C* = d⁻ / (d⁺ + d⁻)` is then converted to a **percentile rank across the
universe**, mapped to 1–100. Raw `C*` moves with the universe composition day
to day; percentile does not, so the number has a stable meaning for the user.

**Regime gate**

`Buy Rank` is shown regardless of regime, but the *label band* is shifted by
Market Weather:

| Weather | Band boundaries (Strong / Good / Neutral / Weak) |
| --- | --- |
| Sunny | 80 / 60 / 40 |
| Cloudy | 85 / 70 / 50 |
| Stormy | all bands read "Wait" except ≥ 90, which reads "Watch" |

**Validation before shipping** (`research/factor_eval.py`)

- Rolling Spearman information coefficient between today's score and the next
  21-day return. Target: rolling 12-month mean IC ≥ 0.03 with t-stat ≥ 2.
- Decile portfolios, monthly rebalance, 2019-present: top-decile minus
  bottom-decile spread must be positive after 0.3% round-trip cost.
- If a factor's marginal IC is negative over the sample, its weight goes to
  zero. Weights are a config table, not code.

**LLM in the loop**

- Input: the factor contribution table for one stock (`factor, z, weight,
  contribution`) plus the band label. Nothing else.
- Output schema: `{ bullets: [str, str, str], watch_out: str }`, with a
  constraint that every number quoted must appear in the input table.
  Run a number audit in code; drop bullets that fail it.
- Cached per `(ticker, date)`. 500 stocks × 1 call/day ≈ 500 short calls,
  a few rupees.

**UI translation**

- A single ring with the number and the band word. Never the word "Buy" in the
  UI; the feature is *Rank*.
- Three pill badges derived from the factor signs: "Trend up", "Calm mover",
  "Crowd rushing in — careful". A "Why this rank?" drawer shows the three LLM
  bullets, then the raw factor table for the curious.
- On the list view: sort by rank, filter by sector, a toggle "Hide risky" that
  removes anything in Danger Zone.

---

### 1.2 Market Weather

**Quant regime score** (daily, plus an intraday refresh at 11:00 and 14:00)

| Input | Source | Transform |
| --- | --- | --- |
| India VIX | Upstox quote | 1-year percentile |
| Nifty 50 vs 200-DMA and 50-DMA | daily candles | ±1 each |
| Breadth | % of Nifty 500 above 50-DMA; 10-day advance/decline ratio | percentile |
| FII net cash flow, 5-day sum | NSE daily report | z-score over 1 year |
| USD/INR 20-day change | Upstox (CDS) or DDG | z-score |
| Nifty options: put/call OI ratio, 25-delta IV skew | Upstox option chain | percentile |

Composite `R = Σ wᵢ · sᵢ` in [−1, +1]. States with **hysteresis** so the icon
does not flicker: Sunny if `R > 0.25`, Stormy if `R < −0.25`, Cloudy between;
a state change needs two consecutive readings.

**News layer** (DuckDuckGo MCP → LLM extraction)

- Scheduled queries every 30 minutes during market hours, hourly otherwise:
  `RBI policy`, `India CPI inflation`, `FII selling India`, `crude oil price`,
  `rupee dollar`, `US Fed rates`, `Nifty today`, plus one query per sector
  showing a >1.5% move.
- Triggered queries: any held or ranked-top-50 stock moving more than 2σ of
  its 20-day daily range in 15 minutes.
- Each result is deduplicated by URL and by title similarity, then passed
  to the LLM with this schema:

```json
{
  "event_type": "policy | macro_data | flows | commodity | fx | earnings | regulatory | geopolitical | other",
  "scope": "macro | sector | stock",
  "entities": ["NIFTY", "BANKNIFTY", "HDFCBANK.NS"],
  "direction": -2,
  "confidence": 0.0,
  "expected_half_life_hours": 24,
  "one_line_why_it_matters": "…",
  "is_duplicate_of": null
}
```

  `direction ∈ {−2..+2}`, `half_life` clamped to [2, 240] hours.

- Impact at time `t`: `I(t) = Σ_e direction_e · confidence_e · 2^(−Δt_e / h_e)`.
  **Sentiment decay** is simply `dI/dt`, reported as "pressure building /
  fading". News can move the displayed *pressure* freely but can flip the
  *state* only if a single event has `confidence ≥ 0.9` and `|direction| = 2`;
  otherwise the state waits for the next quant reading.

**UI translation**

- One weather icon, one sentence ("Cloudy: markets are choppy, big investors
  were net sellers this week"), one line on what changed since yesterday.
- Three headlines, each with the LLM's "why it matters" line.
- A "This week" strip of known scheduled events (RBI, CPI, Fed, expiry) pulled
  from a static calendar plus DDG confirmation.

---

### 1.3 Danger Zone

**Hard rules (red regardless of model)**

- Stock in NSE ASM (any stage) or GSM list — fetched nightly.
- Upper or lower circuit hit on 3 of the last 5 sessions.
- Promoter pledge above 50% (quarterly shareholding pattern; scraped, cached).
- Unexplained spike: 5-day return above 3σ *and* the triggered DDG search
  returns no stock-specific news.

**Statistical layer**

Daily feature vector per stock:
`[ret_5d_z, vol_ratio_20_60, delivery_pct_z_vs_own_60d, spread_bps_z,
amihud_illiquidity_z, gap_frequency_20d, days_since_circuit]`.

Isolation Forest (scikit-learn, 200 trees, contamination 0.03) trained on the
last 2 years of the universe, retrained weekly. Anomaly score → percentile.

**Pump signature** (explicit, because it is the one beginners fall for):
price up > 15% in 5 days, volume > 3× 60-day average, delivery % *below* the
stock's own median, market cap below ₹5,000 Cr. Any three of four → amber, all
four → red.

**Depth-30 anomaly (v2, only where D30 is available)**

Autoencoder on the normalised depth profile (30 levels × 2 sides, each size
as a fraction of total displayed size, plus level spacing in ticks). Trained on
30 days of snapshots per instrument. Reconstruction error above the 99th
percentile → "Unusual order book right now". The UI never says spoofing.

**Traffic light**

`Red` if any hard rule fires or anomaly percentile ≥ 97.
`Amber` if pump signature ≥ 3/4 or anomaly percentile ≥ 90.
`Green` otherwise.

**LLM in the loop**

- Per red/amber stock, one call: inputs are the fired rules and the anomaly
  features; output is `{ plain_reason: str, what_to_check: [str] }`.
- The unexplained-spike check *is* an LLM call: given the DDG results, answer
  `{ has_specific_news: bool, summary: str }`.

**UI translation**

- Traffic light beside every ticker, everywhere in the app.
- A "Danger Zone" page listing red and amber stocks with the plain reason.
- Any attempt to copy-trade a red stock from the Arena hits an interstitial
  with the reason and a required "I understand" tap.

---

### 1.4 Whale Footprints

**Data that is actually institutional**

| Source | Cadence | What it tells you |
| --- | --- | --- |
| NSE bulk deals + block deals CSV | nightly | who bought/sold ≥ 0.5% of equity, at what price |
| NSE FII/DII cash activity | nightly | market-level foreign and domestic flow |
| NSE `sec_bhavdata_full` | nightly | per-stock delivery quantity and % |
| Upstox WebSocket `full` mode (top-5 depth + trades) | tick, watchlist only | intraday order-flow imbalance, large prints |

**Quiet accumulation score** (daily, all 500)

Over a rolling 10-day window:
`A = z(delivery_pct vs own 60d) + z(volume vs 20d) − |z(10-day price change)|`.
High delivery and above-average volume with a *small* price change is the
classic signature of a large buyer working an order without moving the market.
The mirror (falling delivery, volume, small change) is distribution.
Bands: Accumulating ≥ +1.5, Distributing ≤ −1.5, Neutral between.

**Intraday order-flow imbalance** (watchlist of ≤ 100 instruments)

Cont–Kukanov–Stoikov OFI per level update:
`e_t = 1{b_t ≥ b_{t-1}}·q^b_t − 1{b_t ≤ b_{t-1}}·q^b_{t-1} − 1{a_t ≤ a_{t-1}}·q^a_t + 1{a_t ≥ a_{t-1}}·q^a_{t-1}`
summed over the top 5 levels, then over 1-minute bars, normalised by average
displayed depth. Alongside it, tick-rule signed volume gives cumulative volume
delta (CVD).

**Large-print zones** (the honest version of the U-Net idea)

A trade is a "big print" if its size exceeds the 99th percentile of that
instrument's trade sizes over the last 20 sessions. Kernel-density estimate of
big-print volume by price over the last 20 sessions; peaks above 2× the median
density become horizontal bands on the chart. No neural network, no invented
labels, and the output is directly explainable ("large trades cluster at
₹1,420–1,435").

**LLM in the loop**

- Classify bulk-deal counterparty names into `{ FII, MF, insurer, promoter,
  HNI, prop_desk, unknown }`. Names repeat, so the cache hit rate is high.
- One-line "who is buying" per stock per day, constrained to the deal rows
  supplied.
- On a block deal above ₹100 Cr, a triggered DDG search for the reason, run
  through the same event extractor as Market Weather.

**UI translation**

- Paw-print markers on the price chart, sized by deal value, coloured by
  buyer type; hover gives the plain sentence ("A mutual fund bought ₹42 Cr on
  Tuesday").
- A three-state badge: Accumulating / Neutral / Distributing, with one reason.
- "Big money this week" strip on the home page: the five largest net
  institutional buys in the universe.
- Large-print bands drawn on the chart with the label "Where big trades
  happened".

---

### 1.4b Predictions (added 2026-09-17, shipped with Phase 0)

The user asked for a tab that says which *type* of stock tends to rise, from
long history. The honest version is a probability model with its test results
printed next to its output.

- **Data**: up to 20 years of daily bars for today's NIFTY 500 members (Yahoo
  in dev, Upstox in prod). Survivorship bias is real and is stated on the page.
- **Target**: `P(stock beats the universe median over the next 63 trading days)`.
- **Features**: the seven Buy Rank factor z-scores, sector, median 12-1
  momentum of the universe, breadth above the 50-DMA.
- **Model**: `HistGradientBoostingClassifier`, walk-forward by calendar year,
  training labels ending 63 days before each test year. Weekly retrain
  (Saturday 09:00 IST) plus an admin trigger.
- **Outputs**: per-stock odds and percentile; "type of stock" profiles (odds for
  the top vs bottom quintile of each trait today); sector outlook with a
  historical top-3 continuation rate; 20-year base rates per Buy Rank band at
  1/3/6 months; per-year OOS accuracy, AUC, top-decile hit rate and excess
  return; a calibration table.
- **First run** (18.9 years, 207k training rows): OOS accuracy 51%, AUC 0.51,
  top-decile beat the median in 13 of 16 test years by +1.4% per quarter. That
  is the true size of a price-only edge at three months, and the UI says so
  rather than dressing it up.

### 1.5 What is deliberately left out

- **Options trading UI.** Options data feeds Weather (PCR, skew) and nothing
  else. A beginner product must not surface a strike ladder.
- **Tick-by-tick charts.** One-minute bars are the finest resolution shown.
- **Any deep-learning price predictor.** The edge here is disciplined factor
  exposure, risk avoidance, and behavioural guardrails, not forecasting.

### 1.6 Regulatory note

Displaying stock-specific rankings and AI "signals" to the public in India can
fall under SEBI's Research Analyst or Investment Adviser regulations. For a
personal or academic build this is a disclaimer problem; for a public launch it
is a registration problem. Every page carries: *"Educational simulation. Not
investment advice. Past performance of simulated portfolios does not predict
future results."*

---

## Part 2 — The AI Trading Arena

The v1 arena has a real design flaw that must be fixed first: portfolios reset
every day, so "monthly" and "all-time" returns are averages of one-day returns.
v2 uses **persistent paper accounts** that carry positions across days.

### 2.1 Participants

| Persona | Mandate (system prompt core) | Model slot |
| --- | --- | --- |
| **The Value Bull** | long-only, 8–12 names, favours Accumulating + low vol, hates paying up | slot A |
| **The Momentum Trader** | 4–6 names, highest Buy Rank + volume confirmation, tight stops, high turnover allowed | slot B |
| **The Risk Officer** | never buys; reviews every proposed position and files objections; proposes gross exposure for the day | slot C |
| **The Contrarian** | looks for Distributing → oversold reversals, Weather-aware, max 5 names | slot D |
| **Quant-Only** (control) | no LLM; top-10 Buy Rank, inverse-vol weights, regime-scaled exposure | code |
| **Nifty 50** (benchmark) | buy and hold | code |

Model slots are configuration: one gateway model ID per slot. Two experiment
modes are supported by config alone: *persona diversity* (different mandates,
one strong model each) and *model diversity* (same mandate on four models).
Run persona diversity as the product; run model diversity as a weekend
experiment. Never mix both in one leaderboard or the results are confounded.

The **Quant-Only control is non-negotiable**. If the LLM personas cannot beat
it after costs, the honest product is the control with LLM explanations.

### 2.2 The Market Packet — one input, byte-identical for everyone

Built once per cycle by `arena/packet.py`, stored in Postgres with a SHA-256
`packet_id`. Every persona receives the same rendered string.

```json
{
  "packet_id": "sha256…",
  "as_of": "2026-09-17T08:50:00+05:30",
  "weather": { "state": "Cloudy", "score": -0.12, "pressure": "fading", "one_line": "…" },
  "candidates": [
    { "ticker": "…", "price": 0, "buy_rank": 0, "band": "Good", "sector": "…",
      "vol_60d": 0, "whale": "Accumulating", "danger": "Green",
      "factors": { "mom_12_1": 0, "trend": 0, "low_vol": 0, "vol_conf": 0, "overheat": 0 } }
  ],
  "events": [
    { "id": "ev_…", "scope": "macro", "direction": -1, "confidence": 0.8, "why": "…", "age_h": 3 }
  ],
  "flows": { "fii_5d_cr": 0, "dii_5d_cr": 0 },
  "portfolio": { "cash": 0, "positions": [ { "ticker": "…", "qty": 0, "avg": 0, "pnl_pct": 0, "days_held": 0 } ] },
  "constraints": { "max_names": 12, "max_weight": 0.20, "max_sector": 0.35, "gross_cap": 0.70, "banned": ["…"] }
}
```

Sizing rules that keep the context window identical and small:

- Candidates: top 25 by Buy Rank plus every current holding, deduplicated.
  Rendered as a fixed-width table (as v1 does), not JSON, to save tokens.
- Events: top 10 by current impact `|I(t)|`, each ≤ 160 characters.
- Total budget ≈ 4–6k tokens. The system prompt (persona + schema + rules)
  is static per persona, so provider-side prompt caching applies.

### 2.3 Output schema (strict, validated by Pydantic)

```json
{
  "signals": [
    { "ticker": "…", "action": "buy | add | hold | trim | exit | avoid",
      "conviction": 0, "horizon_days": 0, "target_weight": 0.0,
      "stop_loss_pct": 0.0, "thesis": "≤ 2 sentences",
      "evidence": ["ev_…", "buy_rank", "whale"], "risks": ["…"] }
  ],
  "gross_exposure": 0.0,
  "one_line_stance": "…",
  "changed_mind_because": null
}
```

Grounding checks in code, not prompt:

- Every `ticker` must be in the packet. Every `evidence` id must exist.
- Every number in `thesis` must appear in the packet (reuse a number audit).
- `target_weight` and `gross_exposure` are clipped to the constraints.
- Anything failing is dropped and logged; a persona with zero valid signals
  is recorded as "abstained", not retried more than once.

Provider handling: request structured output where the gateway supports it
(`response_format: json_schema`), otherwise JSON mode plus validation plus one
repair prompt containing the validation error. Fix `temperature = 0.3` and pass
a `seed` where supported. Store `(packet_id, persona, model, prompt_hash,
raw_response)` for every call so any day can be replayed.

### 2.4 Debate protocol (two rounds, then arithmetic)

**Round 1 — blind.** All personas answer the packet independently and
concurrently (`asyncio.gather`).

**Round 2 — anonymised cross-examination.** Each persona receives the other
personas' `one_line_stance` and their top-3 signals, labelled *Analyst 1..n*
with no model or persona names, to avoid deference to a brand. The prompt
requires two things: state the strongest argument *against* your own top
pick, then submit a final answer. The `changed_mind_because` field must be
filled if anything moved. Two rounds is the cap; more rounds converge to
mush and cost money.

**Risk Officer.** Runs in both rounds but its output is `objections[]` keyed
by ticker plus a recommended `gross_exposure`. Its objections are shown to the
user; its exposure recommendation is *advisory*. The binding limits come from
code (Weather-based gross cap, Danger Zone ban, position and sector caps).
An LLM never has the last word on risk.

**Ensemble.** For each ticker:

`consensus = Σᵢ wᵢ · dirᵢ · (convictionᵢ / 100)` with `dir ∈ {+1 buy/add, 0 hold, −1 trim/exit/avoid}`.

Weights `wᵢ ∝ exp(κ · IR₆₀,ᵢ)`, floored at 0.10, where `IR₆₀` is the persona's
trailing 60-session information ratio versus Nifty 50; start equal. Also
track each persona's **Brier score**, treating `conviction/100` as the stated
probability of a positive return over `horizon_days`. Persistently
over-confident personas are shrunk toward 0.5 before weighting.

**Consensus portfolio construction (long-only):**

1. Candidates with `consensus ≥ 0.35` and Danger Zone ≠ Red.
2. Weights ∝ `consensus / vol_60d`, capped at 20% per name and 35% per sector.
3. Gross exposure = min(Risk Officer suggestion, Weather cap: Sunny 100%,
   Cloudy 70%, Stormy 40%). Remainder in cash.
4. Turnover limit 30% of NAV per day; smallest-conviction changes are deferred.

### 2.5 Paper execution and scoring

- Decisions at 08:50 IST; fills at the 09:20–09:25 one-minute VWAP from the
  feed (or the 09:25 LTP if the feed is down), plus 5 bps slippage, plus real
  Indian costs (STT 0.1% delivery, exchange and GST, ₹20 brokerage cap).
- Six paper accounts: four personas, consensus, Quant-Only; Nifty 50 is a
  price series, not an account.
- Mark to market every 5 minutes during the session from LTP; end-of-day
  valuation row persisted as in v1.
- Metrics per account: cumulative return, annualised vol, max drawdown, hit
  rate per closed trade, Brier score, turnover, cost drag.

### 2.6 Copy-trading

- Default and recommended: **"Follow"** creates the user's own paper portfolio
  that mirrors consensus from that day forward, with the user's chosen capital.
- Live orders via Upstox are behind three gates: a global feature flag off by
  default, a per-order confirmation sheet showing cost and stop, and a rule
  that live following is unavailable until the consensus account has a
  60-session track record. Danger Zone Red is never orderable.

### 2.7 Orchestration: LangGraph everywhere, LangSmith for monitoring

Every LLM feature is a **LangGraph `StateGraph`**, and every model call goes
through `backend/llm/gateway.py` (LangChain `ChatOpenAI` against the gateway,
`with_structured_output` for schemas). No feature imports a provider SDK.
This is a deliberate choice for three reasons:

1. **The chatbot is coming.** A LangGraph agent with tools over the internal
   services (`get_rank`, `get_weather`, `get_arena_consensus`, `search_news`)
   and a Postgres checkpointer for conversation threads slots in as one more
   graph, sharing the gateway, the audit and the tracing.
2. **Grounding loops are graphs.** "Generate → audit numbers → repair or
   strip" is a conditional edge, not an if-statement buried in a service.
3. **Monitoring is free.** With `LANGSMITH_TRACING=true`, every graph run is a
   trace with the packet id, persona, model and cost attached. That is the
   monitoring layer for the product and for the chatbot.

Graph inventory:

| Graph | Nodes | Shipped in |
| --- | --- | --- |
| `buyrank.explain` | generate → audit → {end, retry, strip} | Phase 0 |
| `intel.extract` | search → dedupe → extract (structured) → score decay → persist | Phase 1 |
| `danger.spike_check` | search news → classify has_specific_news | Phase 1 |
| `arena.cycle` | build_packet → fan-out round 1 (`Send` per persona) → collect → fan-out round 2 → risk_officer → ensemble (pure code) → construct_portfolio → persist | Phase 2 |
| `chat.assistant` | guard (light model, structured verdict) → agent (gpt-4o-mini + tools) ⇄ tools; Postgres checkpointer per thread | Phase 0 (shipped 2026-09-17) |

**Chat assistant details.** `backend/llm/chat.py`. The guard runs on
`CHAT_GUARD_MODEL` (`openai/gpt-4.1-nano`) and returns a category; only
`screen_data`, `market_general` and `app_usage` reach the main model, the rest
get a one-line redirect and are never sent on. The agent's system prompt
carries a compact JSON of *what is on the user's screen* (`lib/screen.ts` on
the frontend; each page publishes route, a plain summary and the visible rows),
so "why is this one ranked 78" resolves without a lookup. Tools:
`get_rank_detail`, `list_ranks`, `list_sectors`, `explain_rank`,
`get_prediction`, `top_predictions`, `arena_today`, `arena_leaderboard`,
`web_search` (DuckDuckGo via `ddgs`, text or news). Threads are checkpointed
with `PostgresSaver` (SQLite saver when `DATABASE_URL` is SQLite); the browser
keeps its thread id in localStorage and "New chat" deletes the thread.
Streaming is SSE (`status` / `delta` / `done` / `error` frames). Rate limit
12 messages/min/IP. Every run is a LangSmith trace named `chat.assistant`
tagged with the thread id; the guard call carries the `guard` tag so it can be
filtered.

Conventions: state is a `TypedDict`; every node is a pure function of state;
anything that must be enforced (position caps, bans, number audit) is a code
node, never a prompt instruction; `graph.invoke(..., config=run_config(...))`
tags the trace with `ai-arena` plus the feature name.

### 2.8 Frontend: the Boardroom

- **Boardroom view** for any stock: five avatars in a row, each with a
  stance chip (Buy / Hold / Avoid), a conviction bar, and its thesis on tap.
  A consensus dial in the centre. Below it, a "Where they disagree" card that
  quotes the two most opposed theses side by side, and the Risk Officer's
  objection if any.
- **Debate transcript** collapsed by default: Round 1 stances, what changed
  in Round 2 and why. Beginners can ignore it; curious users learn from it.
- **Race chart**: equity curves for the six accounts plus Nifty 50, with a
  plain-words scoreboard: "Best day", "Worst losing streak" (max drawdown),
  "How often right" (hit rate), "When 80% sure, right X% of the time"
  (calibration).
- **Today's consensus portfolio** as a card list with weights as simple bars
  and a single "Follow" button.
- Every model-generated sentence carries a small "AI" mark, and every screen
  carries the disclaimer footer.

---

## Part 3 — Local architecture, then AWS Free Tier

### 3.1 Local architecture

Processes (each its own `systemd` unit later, each a terminal now):

```
┌──────────────┐   protobuf WS    ┌─────────────────────┐
│ Upstox WS V3 │ ───────────────► │ feed  (feed/main.py)│──► 1-min bars, OFI, big prints ──► Postgres
└──────────────┘                  │  asyncio, ring bufs │──► NOTIFY 'ticks' (LTP fan-out)
                                  └─────────────────────┘
┌──────────────┐   REST           ┌─────────────────────┐
│ Upstox REST  │ ◄──────────────► │ api   (uvicorn)     │◄── Next.js (REST + SSE /stream)
│ NSE archives │ ───────────────► │  FastAPI + APSched  │──► Postgres
└──────────────┘                  └─────────────────────┘
┌──────────────┐   MCP (stdio)    ┌─────────────────────┐
│ DuckDuckGo   │ ◄──────────────► │ intel (intel/main)  │──► events table
│ MCP server   │                  │  LLM extract        │
└──────────────┘                  └─────────────────────┘
┌──────────────┐   HTTPS          ┌─────────────────────┐
│ LLM gateway  │ ◄──────────────► │ arena (jobs)        │──► signals, paper fills
└──────────────┘                  └─────────────────────┘
```

Data flow, one trading day:

| IST | Who | What |
| --- | --- | --- |
| 03:30 | — | Upstox access token expires. |
| 07:45 | api | Telegram push with the Upstox login link; the OAuth callback route stores the new token in `.env`/SSM and signals the feed. |
| 08:00 | api job | Nightly NSE files if not already in: bhavcopy, bulk/block deals, FII/DII, ASM/GSM, index constituents. Recompute Buy Rank, Whale, Danger, Weather. |
| 08:50 | arena job | Build packet → Round 1 → Round 2 → ensemble → target portfolios. |
| 09:15 | feed | WebSocket up: `ltpc` for the Nifty 500, `full` for the watchlist (holdings + top-50 ranked), `full_d30` for the few D30 instruments if enabled. |
| 09:20–09:25 | arena | Paper fills at 1-minute VWAP. |
| 09:15–15:30 | feed / intel | Bars, OFI, big prints; shock detector triggers intel; intel scheduled scans every 30 min; LTP fan-out to SSE. |
| 11:00, 14:00 | api job | Intraday Weather refresh. |
| 15:35 | api job | Close valuations; persona metrics; ensemble weights for tomorrow. |
| 15:40 | feed | Disconnect; flush bars; archive tick aggregates. |
| 20:00 | api job | Pull NSE end-of-day files (they publish in the evening). |

Notes on the pieces:

- **Feed.** Upstox Market Data Feed V3 is protobuf; compile `MarketDataFeedV3.proto`
  once into `feed/pb/`. Subscription limits differ by mode (roughly thousands
  for `ltpc`, far fewer for `full`, a few dozen for `full_d30`); verify the
  current limits in the Upstox docs before sizing the watchlist. Never write
  raw ticks to Postgres. Aggregate in memory and write 1-minute rows.
- **Fan-out.** Postgres `NOTIFY` on a `ticks` channel carries `{ticker, ltp,
  ts}`; the API's `/stream` SSE endpoint listens and forwards. This avoids a
  Redis dependency; swap in Redis pub/sub later if fan-out grows.
- **Intel.** Use the Python `mcp` client over stdio to the DuckDuckGo MCP
  server, wrapped as `search(query, n)` and `fetch(url)`. Cache query results
  for 15 minutes in Postgres. Rate-limit to a few requests per minute; DDG
  will block otherwise.
- **LLM gateway** (`llm/gateway.py`): one adapter interface
  `complete(model, system, user, schema) -> dict`, implemented over the
  OpenAI-compatible gateway you already use, with structured-output mode
  detection per model, a Pydantic validation step, one repair retry, and an
  audit log row per call. Every feature calls this, never a provider SDK
  directly.
- **ML.** PyTorch and scikit-learn are *research* dependencies. Train and
  evaluate locally in `research/`; export the Isolation Forest with joblib and
  any neural model to ONNX. The runtime installs `onnxruntime` and
  `scikit-learn` only. This matters on a 1 GB instance.
- **Frontend.** Keep Next.js. Split the v1 single page into routes
  (`/`, `/rank`, `/weather`, `/danger`, `/whales`, `/arena`, `/stock/[ticker]`)
  and components. Live prices via `EventSource('/stream')`; everything else
  via REST with SWR or React Query.

**Proposed layout** (evolving the existing repo, not replacing it):

```
backend/
  app/            FastAPI app, routers, response schemas, SSE
  feed/           Upstox WS client, protobuf, bars, OFI, big prints
  data/           NSE ingestion, Upstox REST, universe
  quant/          factors, buyrank, weather, danger, whale, regime
  intel/          DDG MCP client, event extraction, decay
  arena/          packet, personas, debate, ensemble, paper, metrics
  llm/            gateway, schemas, cache, audit, number audit
  jobs/           scheduler wiring (extends scheduler.py)
  research/       backtests, factor_eval, model training, notebooks
  models/         exported artefacts (joblib / onnx), git-ignored
  alembic/        migrations (add now; create_all does not scale)
arena-frontend/   Next.js, split into routes and components
infra/
  systemd/        arena-feed, arena-api, arena-intel units and timers
  nginx/          reverse proxy, TLS
  lambda/         handlers for scheduled and event-driven jobs
  scripts/        bootstrap-ec2.sh, backup-to-s3.sh
docs/
```

**Local run:** `docker compose` brings up Postgres 16; the three Python
processes run from one venv; Next.js runs `next dev`. The compose file in the
repo already exists and needs the Postgres service added.

### 3.2 Postgres schema additions (beyond v1)

| Table | Grain | Retention |
| --- | --- | --- |
| `daily_bars` | ticker × day | forever (≈ 125k rows/yr for 500 stocks) |
| `minute_bars` | ticker × minute, watchlist only | 30 days hot, then Parquet to S3 |
| `factor_scores` | ticker × day | forever |
| `regime_readings` | timestamp | forever |
| `events` | one per extracted news event | 180 days |
| `institutional_deals` | one per bulk/block row | forever |
| `surveillance` | ticker × day × list | 1 year |
| `danger_flags` | ticker × day | 1 year |
| `packets` | one per arena cycle, JSONB | forever (small) |
| `llm_calls` | one per call, raw response in S3 after 30 days | 30 days in DB |
| `accounts`, `positions`, `fills`, `account_valuations` | paper trading | forever |

Partition `minute_bars` by month. A nightly job copies partitions older than
30 days to S3 as Parquet and drops them. At this design the database stays
well under 5 GB for years; ticks are what would break it, and ticks never
land in it.

### 3.3 AWS Free Tier mapping

**This account is on the credit-based Free plan: $100 of credits, 173 days
remaining as of 2026-09-17 (expires around 2027-03-09).** The plan cannot be
charged; when credits or days run out, access stops. Always-free services
(Lambda 1M requests, S3 and CloudFront allowances, SSM, EventBridge, Budgets)
do not consume credits. Everything else does, so the budget is the credits,
and the constraint is making $100 last six months.

Rough monthly burn of the recommended footprint in `ap-south-1`:

| Item | ≈ $/month | 6 months |
| --- | --- | --- |
| EC2 `t3.micro` on-demand, 24×7 | 8.5 | 51 |
| EBS 30 GB gp3 | 2.4 | 14 |
| Public IPv4, one address | 3.6 | 22 |
| S3, CloudFront, Lambda, SSM within always-free | 0 | 0 |
| **Total** | **≈ 14.5** | **≈ 87** |

That fits, barely. Two levers if it does not: a `t4g.micro` (ARM, about 25%
cheaper; the Python stack runs fine on it), or stopping the instance outside
06:00–21:00 IST with an EventBridge schedule, which cuts EC2 cost by a third.
RDS `db.t3.micro` would add ≈ $15/month and exhaust the credits by month four,
so **Postgres runs on the EC2 instance**, with a nightly `pg_dump` to S3. Check
the Free Tier usage page after the first week; if `t3.micro` hours show as
covered rather than billed against credits, the budget is comfortable.

The 173-day horizon is also a product deadline: by early March 2027 the
account must be upgraded to paid, or the system moved to another host.

| Component | Where | Why |
| --- | --- | --- |
| `feed` (persistent WebSocket) | EC2 `t3.micro`, systemd, started by a timer at 09:10 and stopped at 15:40 | Long-lived sockets do not fit Lambda; running only in market hours saves CPU credits |
| `api` + scheduler | same EC2, uvicorn behind nginx with Let's Encrypt (free DNS via DuckDNS or a cheap domain) | Single 1 GB box handles this comfortably with 1 worker |
| Postgres | **On the EC2 instance** (Postgres 16 from the distro, data on the root volume, `shared_buffers` 128 MB), nightly `pg_dump` to S3, bound to `localhost` only | RDS would consume the credits by month four; a local instance costs nothing extra and is never reachable from the internet |
| News scans, event extraction, arena LLM rounds, nightly NSE ingestion | **Lambda** (Python 3.12, 512 MB, ≤ 5 min) triggered by **EventBridge** schedules | Bursty, stateless, 1M requests/month always free |
| Shock-triggered news check | EC2 feed invokes the intel Lambda asynchronously via `boto3` | No queue service needed at this volume |
| Raw NSE files, Parquet archives, LLM transcripts, `pg_dump`s | **S3** with lifecycle rules (Standard → Glacier Instant after 90 days) | Keeps Postgres small |
| Frontend | Static `next export` to S3 + **CloudFront** (always-free 1 TB/month), or Vercel Hobby | No server-side rendering is needed for this app |
| Secrets, daily Upstox token | **SSM Parameter Store** standard parameters (free); avoid Secrets Manager | Secrets Manager bills per secret |
| Alerts | Telegram bot from the API; CloudWatch alarms only for instance status and budget | CloudWatch log ingestion beyond the free 5 GB costs money |

**The pattern that makes Lambda safe:** Lambda never opens a database
connection. It calls the EC2 API's `/internal/*` routes with a shared bearer
token in SSM, and the API does the reads and writes. Putting Lambda inside the
VPC to reach a private RDS would require a NAT Gateway, which is the single
most common surprise bill (≈ $32/month plus data).

**EC2 sizing on 1 GB RAM:** set the instance credit specification to
`standard`, not `unlimited`; add a 2 GB swap file; run one uvicorn worker; do
not install PyTorch on the box; run the feed only in market hours; use
`journald` with a 200 MB cap and `logrotate` rather than shipping logs to
CloudWatch. The v1 code logs one line per ticker per fetch; turn that down to
a summary line before deploying.

**Upstox daily token on a server:** the token dies at 03:30 IST and needs a
human login each morning unless you hold an extended token. Design around it:
the API exposes `/auth/upstox/login` and `/auth/upstox/callback`, the 07:45
Telegram message carries the login link, the callback writes the token to SSM,
and the feed refuses to start without a token minted today. Read-only
endpoints keep serving yesterday's data meanwhile.

### 3.4 Avoiding an accidental bill

Do these on day one, before any resource exists:

1. **AWS Budgets**: a zero-spend budget and a $5 budget, both emailing you.
   Enable billing alerts in the Billing preferences so CloudWatch can alarm on
   `EstimatedCharges`.
2. **No NAT Gateway, no load balancer, no Route 53 hosted zone** (that one is
   $0.50/month, not free). nginx on the instance plus free DNS is enough.
3. **Elastic IP** only while attached to a running instance; an idle one is
   charged. Better: no EIP, use the instance's public IP and update DuckDNS
   from a cron job.
4. **Public IPv4 is billed** since 2024. The legacy tier covers 750 hours for
   EC2 only. Keep RDS private. One public address total.
5. **t3 credit mode `standard`.** `unlimited` silently bills CPU surplus, and a
   Python process spinning on a WebSocket will use it.
6. **No RDS.** If you ever add it, single-AZ, no storage autoscaling, backup
   retention 1 day, no Performance Insights. On this plan it is simply the
   fastest way to spend the credits.
7. **EBS**: one 30 GB gp3 root volume, nothing else; delete-on-termination on.
8. **CloudWatch**: no detailed monitoring, no custom metrics, no log groups
   from the app. Alarms: 10 are free.
9. **Data transfer out**: 100 GB/month free; a JSON API for a handful of users
   will not approach it, but never serve Parquet or images from EC2. That is
   what S3 and CloudFront are for.
10. **Lambda**: set reserved concurrency to 2 on every function so a bug in a
    trigger cannot fan out; set timeouts to 5 minutes.
11. **Tag everything** `project=arena` and review Cost Explorer weekly for the
    first month. Free-tier usage has its own page in Billing; check it.
12. On this plan the account is suspended rather than billed when credits run
    out, so the risk is downtime, not money. Still do all of the above so the
    credits last the full 173 days, and set a Budgets alert at $50 of credit
    usage as the halfway checkpoint.

### 3.5 Build order

| Phase | Weeks | Deliverable | Needs WebSocket? |
| --- | --- | --- | --- |
| 0 | 1–2 | Alembic schema, nightly NSE + Upstox daily ingestion, `daily_bars`, Buy Rank v2 with `factor_eval` report | No |
| 1 | 3–4 | Market Weather (quant regime + DDG MCP + event extraction), Danger Zone (rules + Isolation Forest), LLM gateway with audit and number audit | No |
| 2 | 5–7 | Arena v2: persistent paper accounts, packet, two-round debate, ensemble, Quant-Only control, Boardroom UI, race chart | No (LTP via REST) |
| 3 | 8–9 | Feed: WS V3 protobuf, 1-min bars, OFI, big prints, SSE stream; Whale Footprints intraday layer | Yes |
| 4 | 10 | AWS: EC2 bootstrap script, systemd units, Lambda handlers, S3 lifecycle, budgets, CloudFront frontend | — |

The WebSocket comes late on purpose: it is the most operationally fragile
component and the least valuable to a beginner. Three of the four features and
the whole Arena work on end-of-day data and REST quotes.

---

## Appendix — What changes in the existing v1 code

- `database.py`: portfolios become persistent `accounts` with `positions`
  and `fills`; `DailyValuation` becomes `account_valuations`. Add Alembic.
- `services/market_data.py`: keep the Upstox client and instrument cache;
  move indicators into `quant/factors.py`; `apply_topsis` stays as the
  combiner but consumes the new factor matrix and emits percentiles.
- `services/ai_engine.py`: becomes `arena/personas.py` + `llm/gateway.py`;
  the JSON-regex parser is replaced by structured output + Pydantic.
- `scheduler.py`: the holiday table and `is_trading_day` stay; jobs move to
  `jobs/` and gain the new schedule above.
- `routes/`: keep the response shapes the frontend already reads while the
  page is split, then add `/rank`, `/weather`, `/danger`, `/whales`,
  `/arena/*`, `/stream`.
- `.env.example` currently contains a real-looking key. Replace it with a
  placeholder and rotate the key.
