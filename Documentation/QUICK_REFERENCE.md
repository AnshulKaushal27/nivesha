# AI Investment Arena — Quick Reference Card

## 🚀 Quick Start Commands

### Setup (First Time Only)
```bash
# Linux/Mac
chmod +x quick-start.sh
./quick-start.sh

# Windows
quick-start.bat
```

---

## 📍 Running the Servers

### Backend (Terminal 1)
```bash
cd backend

# Activate virtual environment
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Start server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# ✅ You should see:
# INFO:     Uvicorn running on http://0.0.0.0:8000
# INFO:     Scheduler started (IST timezone)
```

### Frontend (Terminal 2)
```bash
cd arena-frontend

# Start dev server
npm run dev

# ✅ You should see:
# ▲ Next.js 14.2.5
# - Local: http://localhost:3000
```

---

## 🔍 Health Checks

### Quick Verification
```bash
# Check backend is running
curl http://localhost:8000/health

# Check frontend is running
curl http://localhost:3000 | head -20
```

### API Testing
```bash
# Get leaderboard
curl http://localhost:8000/leaderboard | jq

# Get today's simulation
curl http://localhost:8000/simulation/today | jq

# Get market candidates
curl http://localhost:8000/market/candidates | jq '.[0:3]'

# Get portfolio history
curl http://localhost:8000/analytics/history | jq
```

### Manual API Calls
```bash
# Run simulation
curl -X POST http://localhost:8000/simulate-and-save

# Update valuations
curl -X POST http://localhost:8000/update-valuations
```

---

## 🌐 Access Points

| Service | URL | Purpose |
|---------|-----|---------|
| **Frontend** | http://localhost:3000 | Main dashboard UI |
| **API Docs** | http://localhost:8000/docs | Swagger UI - all API endpoints |
| **API ReDoc** | http://localhost:8000/redoc | Alternative API documentation |
| **Health Check** | http://localhost:8000/health | Backend status |

---

## 📂 File Locations

```
project-root/
├── backend/
│   ├── main.py              ← FastAPI app entry point
│   ├── config.py            ← Configuration & settings
│   ├── database.py          ← Database models
│   ├── requirements.txt      ← Python dependencies
│   ├── .env                 ← Environment variables (CREATE THIS)
│   ├── venv/                ← Python virtual environment
│   ├── routes/              ← API route handlers
│   │   ├── leaderboard.py
│   │   ├── portfolios.py
│   │   ├── market.py
│   │   └── admin.py
│   └── services/            ← Business logic
│       ├── ai_engine.py
│       ├── market_data.py
│       └── valuation.py
│
└── arena-frontend/
    ├── package.json         ← npm dependencies
    ├── next.config.js       ← Next.js configuration
    ├── .env.local           ← Frontend env vars (CREATE THIS)
    ├── node_modules/        ← npm dependencies
    ├── src/
    │   └── app/
    │       ├── page.tsx     ← Main dashboard component
    │       └── layout.tsx   ← Root layout & styling
    └── .next/               ← Build output (generated)
```

---

## 📝 Environment Variables Checklist

### backend/.env (REQUIRED)
```
AICREDITS_API_KEY=your_key_here  ⚠️ MUST fill this in
DATABASE_URL=sqlite:///./arena.db
DEFAULT_CAPITAL=100000.0
TOP_CANDIDATES=15
MORNING_HOUR=8
MORNING_MINUTE=40
CLOSING_HOUR=15
CLOSING_MINUTE=45
```

### arena-frontend/.env.local (REQUIRED)
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 🔧 Troubleshooting Commands

### Backend Issues

**Problem:** ModuleNotFoundError
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
```

**Problem:** Port 8000 already in use
```bash
# Find process using port 8000
lsof -i :8000        # Mac/Linux
netstat -ano | findstr :8000  # Windows

# Kill the process or use different port
uvicorn main:app --port 8001
```

**Problem:** Database locked
```bash
cd backend
rm arena.db          # Delete old database (test only!)
# Backend will create new one on startup
```

### Frontend Issues

**Problem:** Port 3000 already in use
```bash
cd arena-frontend
npm run dev -- -p 3001  # Use different port
```

**Problem:** .env.local not being used
```bash
# Restart the dev server:
# 1. Ctrl+C to stop
# 2. npm run dev to restart
```

**Problem:** node_modules issues
```bash
cd arena-frontend
rm -rf node_modules package-lock.json
npm install
```

---

## 🧪 Common Test Scenarios

### Scenario 1: Fresh Start
```bash
# Terminal 1
cd backend && source venv/bin/activate && uvicorn main:app --reload

# Terminal 2
cd arena-frontend && npm run dev

# In browser: http://localhost:3000
# Click "Run Simulation" in Admin banner
# Check leaderboard/portfolios populate
```

### Scenario 2: Test API Directly
```bash
# In a new terminal
curl -X POST http://localhost:8000/simulate-and-save
curl http://localhost:8000/leaderboard | jq
curl http://localhost:8000/simulation/today | jq
```

### Scenario 3: Test Database Persistence
```bash
# 1. Run simulation
curl -X POST http://localhost:8000/simulate-and-save

# 2. Verify data saved
curl http://localhost:8000/simulation/today | jq '.model_results | length'

# 3. Stop backend (Ctrl+C)
# 4. Wait 5 seconds
# 5. Restart backend with: uvicorn main:app --reload
# 6. Check data still exists
curl http://localhost:8000/simulation/today | jq '.model_results | length'
# Should show same count
```

---

## 🐳 Docker Commands

### Build and Run with Docker
```bash
# Build images
docker-compose build

# Start containers
docker-compose up

# Start in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop containers
docker-compose down

# Remove everything (careful!)
docker-compose down -v
```

### Access Docker Services
```bash
# Backend inside Docker
curl http://localhost:8000/health

# Frontend inside Docker
curl http://localhost:3000 | head -20
```

---

## 📊 Monitoring

### Backend Logs
```bash
# See real-time logs
# (Already visible if running in foreground)

# Look for these success messages:
# ✅ APScheduler started
# ✅ Portfolio created for gpt
# ✅ Portfolio created for gemini
# ✅ Portfolios saved

# Look for these error messages:
# ❌ Error in simulation
# ❌ Database connection failed
```

### Frontend Console (Browser)
```
F12 → Console tab

Look for:
✅ GET /simulation/today 200
✅ GET /leaderboard 200
✅ GET /market/candidates 200

Avoid:
❌ CORS error
❌ Failed to fetch
❌ 500 Internal Server Error
```

---

## 🚀 Before Deployment

1. **Backend Production Build**
   ```bash
   cd backend
   # Ensure all requirements installed
   pip install -r requirements.txt
   # Test with: gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app
   ```

2. **Frontend Production Build**
   ```bash
   cd arena-frontend
   npm run build
   npm run start  # Test production build
   ```

3. **Environment Variables**
   - Update `.env` for production database (PostgreSQL recommended)
   - Update `.env.local` with production API URL
   - Store sensitive keys in secret management (not in git!)

4. **CORS Configuration**
   - Edit `backend/main.py` line 44
   - Change `allow_origins=["*"]` to `allow_origins=["https://yourdomain.com"]`

5. **Database Migration**
   - Consider migrating from SQLite to PostgreSQL
   - Update `DATABASE_URL` in `.env`

---

## 📞 Need Help?

1. **Check the full guide:** `SETUP_AND_TESTING_GUIDE.md`
2. **Run the testing checklist:** `TESTING_CHECKLIST.md`
3. **Review API documentation:** http://localhost:8000/docs
4. **Check backend logs** for error messages
5. **Check browser console** (F12) for frontend errors

---

**Last Updated:** May 23, 2026  
**Version:** 2.0.0
