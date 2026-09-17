# Nivesha

**Institutional-grade stock signals for NSE, explained simply enough for a first-time investor.**

Nivesha scores every NIFTY 500 stock nightly, estimates each one's odds of beating the market over the next three months, lets four AI portfolio managers compete with paper money, and answers questions about all of it through **Voxa**, an assistant that sees what is on your screen. Every number on every page can be traced back to a measurement, and every model is graded on data it never saw.

> Educational simulation. Not investment advice. Past performance of simulated portfolios does not predict future results.

---

## What is inside

| Tab | Question it answers | How |
| --- | --- | --- |
| **Strength Rank** | Which stocks are strongest today? | Seven price-derived factors (12-month and 6-month momentum, trend quality, calmness, liquidity, volume confirmation, overheat penalty), combined with TOPSIS into a 1–100 percentile. Bands Strong / Good / Neutral / Weak. Validated with a rolling information coefficient before it shipped. |
| **3-Month Odds** | Which stocks have the best odds of beating the market? | A gradient-boosting model trained walk-forward on up to 20 years of history. Out-of-sample accuracy, calibration and the top-decile hit rate are printed on the page. Retrains itself weekly; every matured batch is scored against real prices. |
| **AI Managers** | Which AI picks stocks best? | Four LLMs (GPT-4o mini, Gemini 2.5 Flash, Mistral Voxtral, DeepSeek V3.2) get the same shortlist and ₹1,00,000 of paper money each trading morning. A leaderboard and race chart track them. |
| **Voxa** (every page) | Anything about the data on screen, a stock, or the markets | LangGraph agent: a light guard model screens each message, gpt-4o-mini answers with tools over the app's data and DuckDuckGo search. Threads are checkpointed in Postgres and compressed as they grow. |
| **System** | Is everything running? | Scheduled jobs, open alerts, data freshness, AI spend against a daily rupee budget, and the self-maintaining NSE trading calendar. |

Both signal pages carry a **prediction-versus-reality** chart: last month's bands followed to today, and the current odds batch tracked against the market.

## Architecture

```
Next.js 14 (React, recharts)  ──HTTPS──▶  Caddy  ──▶  FastAPI + APScheduler  ──▶  PostgreSQL
        pastel UI, glass tabs                   │            │
                                                │            ├── quant/      factors, TOPSIS, predictor (scikit-learn)
                                                │            ├── llm/        LangGraph graphs via one OpenAI-compatible gateway
                                                │            ├── ops/        calendar, alerts, LLM metering, health checks
                                                │            └── data/       NSE universe, Upstox / Yahoo daily bars
                                                └── /api/*  (streaming-safe reverse proxy, basic auth)
```

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, pandas, scikit-learn, LangChain / LangGraph 1.x, LangSmith tracing.
- **Frontend**: Next.js 14 app router, TypeScript, recharts, a colour system where colour always carries a word.
- **Data**: NSE constituent lists and holidays, Upstox Historical Candle V3 and LTP (Yahoo Finance as a dev fallback), 20 years of daily bars for the model.
- **LLM**: any OpenAI-compatible gateway (AICredits by default) with automatic failover to a second provider (Groq, OpenAI, …). Every call is metered; a ₹5/day cap pauses optional AI features.
- **Ops**: guarded scheduler jobs on every NSE trading day, alerts to Telegram / webhook, nightly Postgres backups, one-command deploy to a single EC2 instance on the AWS Free plan.

The full design, including the reasoning behind each feature and what was deliberately rejected, is in [docs/DESIGN.md](docs/DESIGN.md).

## Run it locally

```bash
# 1. Postgres
docker compose up -d postgres

# 2. Backend (Python 3.12)
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env                       # add AICREDITS_API_KEY; UPSTOX_ANALYTICS_TOKEN optional
.venv/bin/alembic upgrade head
.venv/bin/python -m jobs.nightly --source yahoo --lookback-days 7300 --full --skip-rank   # 20 y of bars, ~15 min
.venv/bin/python -m jobs.nightly --source yahoo --backfill 250                            # scores for the last year
.venv/bin/python -m jobs.train_predictor                                                  # the 3-month model, ~2 min
.venv/bin/uvicorn main:app --reload --port 8000

# 3. Frontend
cd ../arena-frontend
npm install && npm run dev                 # http://localhost:3000
```

Tests: `cd backend && .venv/bin/python -m pytest -q`.
Research: `.venv/bin/python -m research.factor_eval` writes the factor evaluation report to `backend/research/reports/`.

### Configuration worth knowing

| Variable | Purpose |
| --- | --- |
| `AICREDITS_BASE_URL`, `AICREDITS_API_KEY` | primary LLM gateway (`https://aicredits.in/v1`) |
| `LLM_FALLBACK_BASE_URL/API_KEY/MODEL` | second provider used automatically while the primary is down |
| `UPSTOX_ANALYTICS_TOKEN` | Upstox extended token for daily bars and quotes; Yahoo is used when absent |
| `LLM_DAILY_BUDGET_INR` | hard daily cap on estimated AI spend (default 5) |
| `LLM_CREDITS_INR`, `LLM_CREDITS_AS_OF` | your gateway balance once, for the run-out projection and low-credit alerts |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `ALERT_WEBHOOK_URL` | where alerts are pushed |
| `PREDICTOR_MAX_YEARS` | cap the model's training window (8 fits a 1 GB server) |
| `LANGSMITH_TRACING`, `LANGSMITH_API_KEY` | trace every LLM graph run |

## Deploy

One `t3.micro` runs everything for about $14/month of AWS Free-plan credits. Two commands from a laptop; the runbook with the console steps is [docs/DEPLOY_AWS.md](docs/DEPLOY_AWS.md).

```bash
FIRST=1 DOMAIN=<host> AUTH_USER=<you> AUTH_PASS='<strong>' infra/deploy.sh ubuntu@<ip> --with-data   # first time
infra/deploy.sh ubuntu@<ip>                                                                          # every later push
```

## Honesty notes

- The Strength Score describes today; it does not predict. Its validation (rolling IC ≈ 0.06, t ≈ 9 on the first run) is a research artefact in the repo, not a promise.
- The 3-month model is only a little better than a coin flip on single stocks (≈ 51 % out of sample). Its usable edge is in the top-odds group, which beat the market in 13 of 16 test years by about 1.4 % per quarter. The page says exactly this.
- History is that of today's NIFTY 500 members, so survivorship bias flatters absolute returns; comparisons between bands are less affected.
- Voxa never invents numbers: explanations are audited against the factor table, and answers cite the tool or web source they came from.

## Repository map

```
backend/        FastAPI app, quant, llm graphs, ops, jobs, tests, alembic migrations
arena-frontend/ Next.js app (Strength Rank, 3-Month Odds, AI Managers, System, Voxa dock)
infra/          deploy.sh, EC2 bootstrap/update/backup scripts, systemd units, Caddyfile
docs/           DESIGN.md (the why), DEPLOY_AWS.md (the how)
Documentation/  original v1 notes, kept for reference
```

## Lineage

Nivesha grew out of *AI Investment Arena*, a FastAPI + Next.js hedge-fund simulator; that project's four-manager competition lives on as the AI Managers tab, and its original interface is kept at `/legacy`.

## License

MIT.
