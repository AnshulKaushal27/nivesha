# AI Investment Arena — Setup & Testing Guide

## 🏗️ Architecture Overview

**Backend:** FastAPI (Python) running on port `8000`  
**Frontend:** Next.js (React/TypeScript) running on port `3000`  
**Database:** SQLite (`arena.db`)  

The frontend queries the backend API at `http://localhost:8000` (configurable via `NEXT_PUBLIC_API_URL`)

---

## 📋 Prerequisites

Before you start, ensure you have:

- **Python 3.11+** (for backend)
- **Node.js 18+** (for frontend)
- **npm or yarn** (for frontend dependency management)

Verify installations:
```bash
python --version
node --version
npm --version
```

---

## 🚀 Step 1: Setup Backend

### 1.1 Navigate to Backend Directory
```bash
cd backend
```

### 1.2 Create `.env` File
Create a `.env` file in the backend root with the following:

```
# AI Credits API (for AI model integration)
AICREDITS_API_KEY=your_api_key_here
AICREDITS_BASE_URL=https://api.aicredits.in/v1

# Database (SQLite — change if using PostgreSQL)
DATABASE_URL=sqlite:///./arena.db

# Portfolio Configuration
DEFAULT_CAPITAL=100000.0
TOP_CANDIDATES=15

# Scheduler Timing (IST timezone)
MORNING_HOUR=8
MORNING_MINUTE=40
CLOSING_HOUR=15
CLOSING_MINUTE=45

# Optional: Market Data APIs
UPSTOX_ANALYTICS_TOKEN=your_token
TWELVE_DATA_API_KEY=your_api_key
```

**Note:** The `AICREDITS_API_KEY` is required for the AI models to generate portfolio recommendations.

### 1.3 Install Python Dependencies

The backend already has a virtual environment (`venv`), but if you need to reinstall:

```bash
# Create fresh venv (optional)
python -m venv venv

# Activate venv
# On Linux/Mac:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 1.4 Initialize Database
The database will auto-initialize on first run, but you can test the connection:

```bash
python -c "from database import SessionLocal; db = SessionLocal(); print('✅ Database connection OK')"
```

### 1.5 Start Backend Server
```bash
# With venv activated:
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Scheduler started (IST timezone)
```

✅ **Backend is ready!** Visit `http://localhost:8000/docs` to see the API documentation (Swagger UI)

---

## 🎨 Step 2: Setup Frontend

### 2.1 Navigate to Frontend Directory
```bash
cd arena-frontend
```

### 2.2 Create `.env.local` File
Create a `.env.local` file in the frontend root:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

This tells the frontend where to find the backend API. For production, change this to your deployed backend URL.

### 2.3 Verify Dependencies
Dependencies are already installed (`node_modules` exists), but if needed:

```bash
npm install
```

### 2.4 Start Frontend Development Server
```bash
npm run dev
```

You should see:
```
  ▲ Next.js 14.2.5
  - Local:        http://localhost:3000
  - Environments: .env.local
```

✅ **Frontend is ready!** Open `http://localhost:3000` in your browser

---

## 🔗 Connection Checklist

Before testing, verify both servers are running and configured correctly:

### Backend Health Check
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "portfolios_today": 0
}
```

### Frontend API Connection
1. Open `http://localhost:3000` in your browser
2. Open **Developer Console** (F12 → Console tab)
3. Look for any red errors about failed API calls
4. You should **not** see CORS errors

If you see CORS errors, the backend CORS middleware may need adjustment (see Troubleshooting below).

---

## 🧪 Testing Workflow

### Test 1: View Dashboard
1. Navigate to http://localhost:3000
2. You should see the "AI ARENA" dashboard with navigation tabs
3. Check that the spinner doesn't show indefinitely
4. You may see "No simulation data yet" if no simulations have run

### Test 2: Run Simulation
1. On the dashboard, find the **Admin** banner at the top
2. Click **▶ Run Simulation**
3. Wait for the status message to appear
4. Check the console for any errors

Expected behavior:
- Status changes to "Running simulation…"
- After a few seconds, you'll see a success message
- The dashboard refreshes to show new data

### Test 3: Check Leaderboard
1. Click the **LEADERBOARD** tab
2. You should see AI model performance metrics
3. If data exists, you'll see models like "GPT-4o mini", "Gemini 2.5 Flash", etc.

### Test 4: Check Market Intel
1. Click the **MARKET INTEL** tab
2. You should see candidate stocks with indicators (RSI, volatility, etc.)
3. Data is fetched from `/market/candidates` endpoint

### Test 5: View Portfolios
1. Click the **PORTFOLIOS** tab
2. See individual portfolio holdings for each AI model
3. Each holding shows allocation %, entry price, sector, etc.

### Test 6: View History
1. Click the **HISTORY** tab
2. See performance charts for all models over time
3. Toggle models on/off to compare performance

---

## 🔌 API Endpoints Reference

All endpoints are prefixed with `http://localhost:8000`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Check backend status |
| `/simulation/today` | GET | Get today's simulation data & portfolios |
| `/leaderboard` | GET | Get AI model leaderboard stats |
| `/market/candidates` | GET | Get market candidates (stocks) |
| `/portfolios` | GET | Get all portfolios (filtered by date) |
| `/analytics/history` | GET | Get historical performance data |
| `/simulate-and-save` | POST | Trigger a new simulation (admin) |
| `/update-valuations` | POST | Update stock valuations (admin) |

Test an endpoint directly:
```bash
curl http://localhost:8000/leaderboard | jq
```

---

## 🚨 Troubleshooting

### Issue: "Cannot reach backend" / CORS errors

**Symptom:** Frontend shows network errors in console, pages are blank  
**Cause:** Backend not running or CORS misconfigured

**Fix:**
1. Verify backend is running: `curl http://localhost:8000/health`
2. Check that `.env.local` has correct `NEXT_PUBLIC_API_URL`
3. If running on different machine, use the actual IP: `NEXT_PUBLIC_API_URL=http://192.168.x.x:8000`

### Issue: Backend won't start / ImportError

**Symptom:** `ModuleNotFoundError: No module named 'fastapi'`

**Fix:**
```bash
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Issue: Database locked / SQLite errors

**Symptom:** `database is locked` errors in backend logs

**Fix:**
1. Stop both backend and frontend
2. Delete `backend/arena.db` (if safe to do so for testing)
3. Restart backend — it will create a fresh database

### Issue: Frontend stuck in loading spinner

**Symptom:** Dashboard shows spinner indefinitely

**Cause:** Backend is not responding or returning error  
**Fix:**
1. Open DevTools (F12)
2. Go to Network tab
3. Check the request to `/simulation/today`
4. Look at the response — you should see JSON data
5. If 500 error, check backend logs for details

### Issue: Environment variables not loaded

**Frontend (.env.local not being used):**
- Restart the `npm run dev` server after creating/editing `.env.local`
- Variable names **must** start with `NEXT_PUBLIC_` to be accessible in browser

**Backend (.env not being loaded):**
- Ensure `.env` is in the `backend/` directory (not root)
- Backend uses `python-dotenv` which loads `.env` on import

---

## 📦 Deployment Checklist

When you're ready to deploy the new frontend, use this checklist:

### Frontend Build & Deployment
```bash
# 1. Build the production bundle
npm run build

# 2. Test the production build locally (optional)
npm run start

# 3. Deploy the `.next` directory to your hosting (Vercel, AWS, etc.)
```

### Backend Deployment
```bash
# 1. Set environment variables on your server
export AICREDITS_API_KEY=xxx
export DATABASE_URL=postgresql://...  # switch to PostgreSQL for production

# 2. Run backend with a production ASGI server (gunicorn/uvicorn)
gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000
```

### Environment Configuration for Production
Update `.env.local` (frontend) and `.env` (backend) with production URLs:

**Frontend (.env.local):**
```
NEXT_PUBLIC_API_URL=https://api.yourdomain.com
```

**Backend (.env):**
```
DATABASE_URL=postgresql://user:pass@prod-db:5432/arena
AICREDITS_API_KEY=your_production_key
# Update CORS in main.py to whitelist your domain:
# allow_origins=["https://yourdomain.com"]
```

---

## 📝 Key Files Reference

```
backend/
├── main.py              # FastAPI app & routing
├── config.py            # Settings & configuration
├── database.py          # SQLAlchemy ORM & models
├── requirements.txt     # Python dependencies
├── scheduler.py         # APScheduler for background jobs
├── routes/              # API route handlers
│   ├── leaderboard.py
│   ├── portfolios.py
│   ├── market.py
│   └── admin.py
└── services/            # Business logic
    ├── ai_engine.py     # LLM integration
    ├── market_data.py   # Stock data fetching
    └── valuation.py     # Portfolio valuation

arena-frontend/
├── package.json         # Dependencies & scripts
├── next.config.js       # Next.js configuration
├── tsconfig.json        # TypeScript config
└── src/
    └── app/
        ├── page.tsx     # Main dashboard (all pages/components)
        └── layout.tsx   # Root layout & styling
```

---

## 🎯 Next Steps After Testing

1. **Verify all admin functions work** (Run Simulation, Update Valuations)
2. **Test with different market data** (modify stock universe in `config.py` if needed)
3. **Check scheduler jobs** are running at the configured IST times
4. **Validate AI model integration** by checking if portfolio recommendations are generated
5. **Load test** with realistic simulation schedules
6. **Deploy** the new frontend to replace the corrupted one

---

## 📞 Support

For backend-specific issues, check:
- Backend logs: Look for `ERROR` or `WARNING` lines
- API docs: Visit `http://localhost:8000/docs`
- Database schema: Inspect `arena.db` with `sqlite3 arena.db` or a GUI tool

For frontend-specific issues, check:
- Browser console: F12 → Console tab
- Network tab: Check API responses
- Next.js build output: Look for TypeScript or build errors

---

**Happy testing! 🚀**
