# System Architecture & Connection Guide

## 🏗️ Complete System Architecture

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                   AI INVESTMENT ARENA v2.0 - COMPLETE SYSTEM             ║
╚═══════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────┐
│                          CLIENT BROWSER (localhost:3000)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              NEXT.JS FRONTEND (React Components)                     │   │
│  │  ┌──────────────┐  ┌────────────────┐  ┌─────────────────────┐    │   │
│  │  │  Dashboard   │  │ Leaderboard    │  │ Market Intelligence │    │   │
│  │  │  - Admin Btn │  │ - Model Stats  │  │ - Stock Candidates  │    │   │
│  │  │  - Sim Stats │  │ - Performance  │  │ - TOPSIS Scores    │    │   │
│  │  │  - Latest    │  │                │  │ - Sector Analysis   │    │   │
│  │  └──────────────┘  └────────────────┘  └─────────────────────┘    │   │
│  │  ┌──────────────────────────┐  ┌──────────────────────────────┐   │   │
│  │  │ Portfolios Tab           │  │ History/Analytics Tab         │   │   │
│  │  │ - Holdings by Model      │  │ - Performance Charts          │   │   │
│  │  │ - Allocation %           │  │ - Model Comparison            │   │   │
│  │  │ - Entry Price/Quantity   │  │ - Win Rate Analysis           │   │   │
│  │  └──────────────────────────┘  └──────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│                                    │ HTTP REST API Calls                     │
│                                    │ JSON Requests/Responses                 │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │              ENVIRONMENT: NEXT_PUBLIC_API_URL                       │   │
│  │              Default: http://localhost:8000                         │   │
│  │              Production: https://api.yourdomain.com                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ══════════════════╬══════════════════════
                    ║  HTTP PORT 8000  ║  (Configurable)    ║
                    ══════════════════╩══════════════════════
                                      │
┌─────────────────────────────────────▼──────────────────────────────────────┐
│                        FASTAPI BACKEND (localhost:8000)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      MAIN APPLICATION (FastAPI)                      │   │
│  │  - CORS Middleware (allow_origins=["*"] or specific domains)       │   │
│  │  - Request Logging                                                  │   │
│  │  - Error Handling                                                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│  ┌──────────────────────┬──────────┴───────────┬──────────────────────┐    │
│  │                      │                      │                      │    │
│  ▼                      ▼                      ▼                      ▼    │
│                                                                               │
│ ┌────────────────┐  ┌────────────────┐  ┌──────────────┐  ┌────────────┐  │
│ │ routes/        │  │ services/      │  │ database.py  │  │ config.py  │  │
│ │ leaderboard.py │  │ ai_engine.py   │  │              │  │            │  │
│ │ portfolios.py  │  │ market_data.py │  │ - Models     │  │ - Settings │  │
│ │ market.py      │  │ valuation.py   │  │ - SessionLocal   │ - Tickers  │  │
│ │ admin.py       │  │                │  │ - Base       │  │ - Sectors  │  │
│ │                │  │ - Calls AI     │  │ - engine     │  │ - Timezone │  │
│ │ - GET /...     │  │   Models       │  │              │  │            │  │
│ │ - POST /...    │  │ - Fetches      │  └──────────────┘  └────────────┘  │
│ │                │  │   Market Data  │                                     │
│ └────────────────┘  │ - Calculates   │                                     │
│                     │   Valuations   │                                     │
│                     │ - Runs         │                                     │
│                     │   Scheduler    │                                     │
│                     └────────────────┘                                     │
│                                                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    APScheduler (Background Tasks)                    │   │
│  │  - Runs at 8:40 AM IST (MORNING_HOUR/MINUTE)                       │   │
│  │  - Runs at 3:45 PM IST (CLOSING_HOUR/MINUTE)                       │   │
│  │  - Triggers: /simulate-and-save automatically                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                               │
└─────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                    ═══════════════════╩════════════════════════
                    ║ SQLite/PostgreSQL ║ (Configurable)  ║
                    ═══════════════════╩════════════════════════
                                       │
┌─────────────────────────────────────▼──────────────────────────────────────┐
│                           DATABASE LAYER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  Development: SQLite (arena.db)                                             │
│  ┌─────────────────────────────────┐                                       │
│  │ Tables:                         │                                       │
│  │ - portfolio (Portfolios)        │  Stores:                             │
│  │ - holding (Portfolio Holdings)  │  - Simulation results               │
│  │ - candidate (Market Candidates) │  - Performance metrics              │
│  │ - market_data (Stock Data)      │  - Historical data                  │
│  │ - valuation (Stock Valuations)  │  - AI model recommendations         │
│  └─────────────────────────────────┘                                       │
│                                                                               │
│  Production: PostgreSQL (Recommended)                                       │
│  ┌─────────────────────────────────┐                                       │
│  │ DATABASE_URL=                   │  Better for:                         │
│  │ postgresql://user:pass@         │  - Concurrent users                 │
│  │ host:5432/arena_db              │  - High availability                │
│  │                                 │  - Data integrity                   │
│  │ Same table structure             │  - Backup/recovery                  │
│  └─────────────────────────────────┘                                       │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL SERVICES (via API)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌────────────────┐   │
│  │  AI Credits API      │  │  Market Data APIs    │  │  (Optional)    │   │
│  │  - Endpoint:         │  │  - Upstox Analytics  │  │  NSE/NIFTY     │   │
│  │    aicredits.in/v1   │  │  - Twelve Data       │  │  Market Data   │   │
│  │  - Purpose:          │  │  - Purpose:          │  │  - Purpose:    │   │
│  │    AI Model Calls    │  │    Stock Prices      │  │    Price Feeds │   │
│  │    GPT, Gemini,      │  │    RSI, Volatility   │  │                │   │
│  │    Mistral, DeepSeek │  │    Volume Data       │  │                │   │
│  │  - Requires:         │  │  - Requires:         │  │  - Requires:   │   │
│  │    AICREDITS_API_KEY │  │    Optional API Keys │  │    Optional    │   │
│  └──────────────────────┘  └──────────────────────┘  └────────────────┘   │
│                                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow Sequence

### Scenario: User Clicks "Run Simulation" Button

```
1. USER INTERACTION
   ├─ User clicks "▶ Run Simulation" button in browser
   └─ Frontend shows: "Running simulation…"

2. HTTP REQUEST
   ├─ Frontend sends: POST /simulate-and-save
   ├─ URL: http://localhost:8000/simulate-and-save
   └─ Headers: Content-Type: application/json

3. BACKEND PROCESSING
   ├─ FastAPI receives request in admin.py
   ├─ Calls services/market_data.py:
   │  └─ Fetches current prices for NIFTY 200 stocks
   │
   ├─ Calls services/ai_engine.py (for each AI model):
   │  ├─ Sends stocks to AI Credits API
   │  ├─ Model (GPT/Gemini/Mistral/DeepSeek) recommends portfolio
   │  ├─ Receives: holdings, allocations, reasoning
   │  └─ Repeats for all 4 AI models
   │
   ├─ Calls services/valuation.py:
   │  └─ Calculates current portfolio value
   │
   └─ Saves to Database:
      ├─ Portfolio records (1 per model = 4 total)
      ├─ Holding records (multiple per portfolio)
      └─ Market candidate records

4. HTTP RESPONSE
   ├─ Backend returns: 200 OK
   └─ Message: "Simulation completed and saved"

5. FRONTEND UPDATE
   ├─ Frontend receives response
   ├─ Shows success message
   ├─ Auto-refreshes data from /simulation/today
   └─ Dashboard, Leaderboard, Portfolios update with new data

6. USER SEES
   ├─ New simulation data on dashboard
   ├─ Updated leaderboard scores
   ├─ New portfolio holdings
   └─ Performance metrics
```

---

## 🔌 API Endpoint Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                   AVAILABLE API ENDPOINTS                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│ Health & Status:                                                │
│ GET  /health                      ← Check if backend is alive   │
│                                                                   │
│ Simulation Data:                                                │
│ GET  /simulation/today            ← Get today's sim & portfolios│
│ POST /simulate-and-save           ← Run new simulation (admin)  │
│                                                                   │
│ Models & Performance:                                           │
│ GET  /leaderboard                 ← AI model rankings          │
│ GET  /analytics/history           ← Performance over time       │
│                                                                   │
│ Portfolios & Holdings:                                          │
│ GET  /portfolios                  ← Get all portfolios         │
│ GET  /portfolios?date=2024-05-23  ← Filter by date            │
│ GET  /portfolios?model=gpt        ← Filter by AI model        │
│                                                                   │
│ Market Data:                                                    │
│ GET  /market/candidates           ← Stock candidates for today │
│ GET  /market/candidates?date=... ← Stock data for specific day│
│                                                                   │
│ Administration:                                                 │
│ POST /update-valuations           ← Update current stock prices│
│                                                                   │
│ Documentation:                                                  │
│ GET  /docs                        ← Swagger UI (interactive)   │
│ GET  /redoc                       ← ReDoc (alternative)        │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔐 Environment Variables Configuration

### Frontend Configuration (.env.local)

```
NEXT_PUBLIC_API_URL=http://localhost:8000
                    ↓
        Set API endpoint for all backend calls
        - Must start with NEXT_PUBLIC_ to be accessible in browser
        - Default fallback: http://localhost:8000
```

### Backend Configuration (.env)

```
AICREDITS_API_KEY=xxxxx              ← Required for AI model calls
AICREDITS_BASE_URL=https://api.aicredits.in/v1

DATABASE_URL=sqlite:///./arena.db    ← SQLite (dev)
                    OR
DATABASE_URL=postgresql://...        ← PostgreSQL (production)

DEFAULT_CAPITAL=100000.0             ← Starting portfolio amount
TOP_CANDIDATES=15                    ← Stocks to consider

MORNING_HOUR=8                       ← Scheduler timing (IST)
MORNING_MINUTE=40
CLOSING_HOUR=15
CLOSING_MINUTE=45

UPSTOX_ANALYTICS_TOKEN=optional      ← Market data APIs
TWELVE_DATA_API_KEY=optional
```

---

## 🔀 Request-Response Flow Example

### Example: Fetch Today's Simulation

```
1. BROWSER REQUEST
   ┌─────────────────────────────────────────────────┐
   │ fetch('http://localhost:8000/simulation/today')  │
   │ Headers: {Accept: 'application/json'}            │
   └─────────────────────────────────────────────────┘
                            │
                            ▼
2. BACKEND PROCESSES
   ┌─────────────────────────────────────────────────┐
   │ 1. Receives GET request                         │
   │ 2. Queries Portfolio table for today's date     │
   │ 3. Queries MarketCandidate table for today      │
   │ 4. Formats response as JSON                     │
   └─────────────────────────────────────────────────┘
                            │
                            ▼
3. HTTP RESPONSE (200 OK)
   ┌─────────────────────────────────────────────────┐
   │ {                                               │
   │   "date": "2024-05-23",                        │
   │   "market_candidates": [...],                  │
   │   "model_results": [...]                       │
   │ }                                              │
   └─────────────────────────────────────────────────┘
                            │
                            ▼
4. FRONTEND PROCESSES
   ┌─────────────────────────────────────────────────┐
   │ 1. Receives JSON response                      │
   │ 2. Parses into JavaScript objects              │
   │ 3. Updates React component state               │
   │ 4. Re-renders UI with new data                 │
   └─────────────────────────────────────────────────┘
                            │
                            ▼
5. USER SEES
   ┌─────────────────────────────────────────────────┐
   │ Dashboard updates with:                        │
   │ - Latest simulation date                       │
   │ - Portfolio values                             │
   │ - Model performance metrics                    │
   │ - Stock recommendations                        │
   └─────────────────────────────────────────────────┘
```

---

## 🗂️ File Organization

```
project/
│
├── backend/                          ← FastAPI Application
│   ├── main.py                       ← Entry point, FastAPI app
│   ├── config.py                     ← Settings & configuration
│   ├── database.py                   ← SQLAlchemy models & session
│   ├── scheduler.py                  ← APScheduler setup
│   ├── requirements.txt               ← Python dependencies
│   ├── .env                          ← Environment variables (CREATE)
│   ├── arena.db                      ← SQLite database (auto-created)
│   │
│   ├── routes/                       ← API endpoints
│   │   ├── __init__.py
│   │   ├── leaderboard.py            ← Leaderboard endpoints
│   │   ├── portfolios.py             ← Portfolio endpoints
│   │   ├── market.py                 ← Market data endpoints
│   │   └── admin.py                  ← Admin endpoints
│   │
│   ├── services/                     ← Business logic
│   │   ├── __init__.py
│   │   ├── ai_engine.py              ← AI model calls
│   │   ├── market_data.py            ← Stock data fetching
│   │   └── valuation.py              ← Portfolio valuation
│   │
│   ├── venv/                         ← Python virtual environment
│   └── __pycache__/                  ← Compiled Python files
│
├── arena-frontend/                   ← Next.js Application
│   ├── package.json                  ← npm dependencies
│   ├── next.config.js                ← Next.js configuration
│   ├── tsconfig.json                 ← TypeScript configuration
│   ├── eslint.config.mjs             ← ESLint configuration
│   ├── .env.local                    ← Environment variables (CREATE)
│   │
│   ├── src/
│   │   └── app/
│   │       ├── page.tsx              ← Main dashboard (all components)
│   │       └── layout.tsx            ← Root layout & styling
│   │
│   ├── node_modules/                 ← npm packages
│   ├── .next/                        ← Build output (auto-generated)
│   └── public/                       ← Static assets
│
├── docker-compose.yml                ← Docker setup (optional)
├── backend.Dockerfile                ← Backend Docker image
├── frontend.Dockerfile               ← Frontend Docker image
└── Documentation/
    ├── README.md                     ← Overview (this file)
    ├── SETUP_AND_TESTING_GUIDE.md   ← Detailed setup guide
    ├── QUICK_REFERENCE.md            ← Command reference
    ├── TESTING_CHECKLIST.md          ← Testing verification
    ├── API_REFERENCE.md              ← API documentation
    └── .env.backend.example          ← Environment template
```

---

## ✅ Verification Checklist

To verify everything is connected correctly:

```
1. BACKEND RUNNING
   curl http://localhost:8000/health
   Expected: {"status": "healthy", ...}

2. FRONTEND RUNNING
   curl http://localhost:3000 | grep "Next"
   Expected: HTML content including Next.js mentions

3. FRONTEND CAN REACH BACKEND
   Open browser console (F12)
   Check Network tab
   Make any request
   Should see: GET http://localhost:8000/...  200 OK

4. ENVIRONMENT VARIABLES
   Backend: AICREDITS_API_KEY is set (non-empty)
   Frontend: NEXT_PUBLIC_API_URL exists in .env.local

5. DATABASE
   File exists: backend/arena.db
   Tables created: portfolio, holding, market_data, etc.
```

---

## 🚀 Running Different Configurations

### Configuration 1: Local Development
```
Frontend: npm run dev          (port 3000)
Backend:  uvicorn main:app     (port 8000)
Database: SQLite (arena.db)
API Calls: http://localhost:8000
```

### Configuration 2: Docker Development
```
Frontend: npm start            (port 3000)
Backend:  uvicorn main:app     (port 8000)
Database: SQLite (in container)
API Calls: http://backend:8000 (internal Docker network)
```

### Configuration 3: Production
```
Frontend: npm start            (port 3000 or behind reverse proxy)
Backend:  gunicorn -k uvicorn  (port 8000 or behind reverse proxy)
Database: PostgreSQL (remote host)
API Calls: https://api.yourdomain.com
```

---

**For detailed instructions, see SETUP_AND_TESTING_GUIDE.md**
