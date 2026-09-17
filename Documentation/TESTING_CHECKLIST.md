# AI Investment Arena — Testing Checklist

## Pre-Deployment Testing

Use this checklist to verify all functionality before deploying the new frontend to production.

---

## 🏗️ Phase 1: Infrastructure Setup

- [ ] **Python 3.11+ installed**
  ```bash
  python --version  # Should be 3.11 or higher
  ```

- [ ] **Node.js 18+ installed**
  ```bash
  node --version    # Should be 18 or higher
  ```

- [ ] **Backend directory exists and contains main.py**
  ```bash
  ls -la backend/main.py
  ```

- [ ] **Frontend directory exists and contains package.json**
  ```bash
  ls -la arena-frontend/package.json
  ```

---

## 🔧 Phase 2: Backend Setup

- [ ] **Virtual environment created/activated**
  ```bash
  cd backend
  source venv/bin/activate  # or venv\Scripts\activate on Windows
  ```

- [ ] **Python dependencies installed**
  ```bash
  pip list | grep -E "fastapi|sqlalchemy|uvicorn"
  ```

- [ ] **backend/.env file created with AICREDITS_API_KEY**
  ```bash
  cat backend/.env | grep AICREDITS_API_KEY
  # Should show: AICREDITS_API_KEY=xxx (not empty)
  ```

- [ ] **Database can be initialized**
  ```bash
  cd backend
  python -c "from database import Base, engine; Base.metadata.create_all(bind=engine); print('✅ DB OK')"
  ```

- [ ] **Backend starts without errors**
  ```bash
  cd backend
  source venv/bin/activate
  uvicorn main:app --reload --host 0.0.0.0 --port 8000
  # Should show: INFO: Uvicorn running on http://0.0.0.0:8000
  ```

---

## 🎨 Phase 3: Frontend Setup

- [ ] **Frontend dependencies installed**
  ```bash
  cd arena-frontend
  npm list next react 2>/dev/null | head -3
  # Should show: next@14.2.5 and react@18.x
  ```

- [ ] **.env.local created with correct API URL**
  ```bash
  cat arena-frontend/.env.local
  # Should show: NEXT_PUBLIC_API_URL=http://localhost:8000
  ```

- [ ] **Frontend development server starts**
  ```bash
  cd arena-frontend
  npm run dev
  # Should show: ▲ Next.js 14.2.5
  #              - Local: http://localhost:3000
  ```

---

## 🔌 Phase 4: Connection Testing

### Health Check
- [ ] **Backend health endpoint responds**
  ```bash
  curl http://localhost:8000/health
  # Expected: {"status": "healthy", "version": "2.0.0", ...}
  ```

- [ ] **Frontend loads without errors**
  - Open http://localhost:3000 in browser
  - Check browser console (F12) for errors
  - Should see "AI ARENA" header and navigation tabs

### API Response Tests
- [ ] **GET /simulation/today returns data**
  ```bash
  curl http://localhost:8000/simulation/today | jq .
  # May show empty arrays if no simulations run yet
  ```

- [ ] **GET /leaderboard returns data**
  ```bash
  curl http://localhost:8000/leaderboard | jq .
  # May show empty array if no data exists
  ```

- [ ] **GET /market/candidates returns stock data**
  ```bash
  curl http://localhost:8000/market/candidates | jq '.[] | .ticker' | head -5
  # Should list stock tickers like HDFCBANK.NS, INFY.NS, etc.
  ```

- [ ] **GET /portfolios returns data**
  ```bash
  curl http://localhost:8000/portfolios | jq .
  # May be empty initially
  ```

- [ ] **GET /analytics/history returns data**
  ```bash
  curl http://localhost:8000/analytics/history | jq .
  # May be empty initially
  ```

---

## 📊 Phase 5: Frontend UI Testing

### Navigation
- [ ] **All navigation tabs clickable and functional**
  - [ ] Dashboard tab loads
  - [ ] Leaderboard tab loads
  - [ ] Market Intel tab loads
  - [ ] Portfolios tab loads
  - [ ] History tab loads

### Dashboard Page
- [ ] **Admin banner visible at top**
- [ ] **"Run Simulation" button present and clickable**
- [ ] **"Update Valuations" button present and clickable**
- [ ] **Latest simulation date shows (if data exists)**
- [ ] **Status messages appear when buttons clicked**

### Leaderboard Page
- [ ] **Table loads without console errors**
- [ ] **Shows model names** (GPT-4o mini, Gemini 2.5 Flash, etc.)
- [ ] **Shows performance metrics** (avg return, best return, win rate, etc.)
- [ ] **Displays "No data" message if empty** (this is OK for first test)

### Market Intel Page
- [ ] **Stock candidates displayed in table**
- [ ] **Shows columns:** Ticker, Current Price, RSI, Volatility, etc.
- [ ] **Multiple stocks listed** (should see at least 5)
- [ ] **Data refreshes when clicked/reloaded**

### Portfolios Page
- [ ] **Portfolio listings appear**
- [ ] **Each portfolio shows** AI model name, holdings, allocation percentages
- [ ] **Holdings breakdown visible** with sector allocation
- [ ] **"No data" message shows if empty** (this is OK for first test)

### History Page
- [ ] **Charts render without errors**
- [ ] **Model toggle buttons appear**
- [ ] **Line chart loads with axes**
- [ ] **Win rate bar chart displays**
- [ ] **Toggle buttons enable/disable chart lines**

---

## ⚙️ Phase 6: Admin Functionality Testing

### Simulation Execution
- [ ] **"Run Simulation" button is clickable**
- [ ] **Status message changes to "Running simulation…"**
- [ ] **After ~10 seconds, shows success message**
  - Expected: "Simulation completed and saved to database"
  - Or similar confirmation message
- [ ] **Backend logs show successful execution**
  - Look for: `INFO: Simulation started`
  - Look for: `✅ Portfolio created for gpt`
  - Look for: `✅ Portfolio created for gemini`
  - etc.
- [ ] **No error messages in browser console**
- [ ] **Frontend refreshes to show new data** (optional but nice)

### Valuation Update
- [ ] **"Update Valuations" button is clickable**
- [ ] **Status message changes to "Updating valuations…"**
- [ ] **After ~5 seconds, shows success message**
- [ ] **No error messages appear**

---

## 🐛 Phase 7: Error Handling

### Network Errors
- [ ] **Stop backend, refresh frontend**
  - Should show loading spinner or error state
  - No ugly crashes or blank pages
  
- [ ] **Stop frontend, continue backend**
  - Backend should continue running without issues
  - API endpoints still respond: `curl http://localhost:8000/health`

### Invalid Data
- [ ] **Simulate bad API response**
  ```bash
  # Modify a backend route to return invalid data
  # Frontend should handle gracefully (not crash)
  ```

- [ ] **Check console for error traces**
  - Errors should be logged, not throw uncaught exceptions

---

## 📈 Phase 8: Data Flow Testing

### End-to-End Simulation Test
1. [ ] **Start both backend and frontend**
2. [ ] **Navigate to Dashboard**
3. [ ] **Click "Run Simulation"**
4. [ ] **Wait for success message**
5. [ ] **Check Dashboard — shows new data**
6. [ ] **Check Leaderboard — shows AI models with stats**
7. [ ] **Check Market Intel — shows candidate stocks**
8. [ ] **Check Portfolios — shows portfolio holdings**
9. [ ] **Check History — shows performance chart**

### Data Persistence Test
- [ ] **Run a simulation**
- [ ] **Refresh the frontend (F5)**
- [ ] **Data should still be visible** (not re-fetched on every load)
- [ ] **Stop and restart backend**
  - Database should persist data
  - Data loads on restart

---

## 🚀 Phase 9: Performance Testing

### Load Time
- [ ] **Dashboard loads within 3 seconds**
- [ ] **Leaderboard table renders within 2 seconds**
- [ ] **Market Intel table renders within 2 seconds**
- [ ] **History charts render within 3 seconds**

### Network Requests
- [ ] **Open DevTools Network tab**
- [ ] **Check that API requests complete successfully**
  - [ ] No 500 errors
  - [ ] No timeout errors
  - [ ] Response times < 2 seconds each

### Browser Console
- [ ] **No red errors in console** (F12 → Console)
- [ ] **Only info/debug messages** (if any)
- [ ] **No memory leaks** (leave page open for 5 minutes, memory stable)

---

## 🔐 Phase 10: API Security Check

- [ ] **CORS is properly configured**
  ```bash
  # Backend should only allow your domain
  # Check in main.py: allow_origins = ["*"] should be locked down
  ```

- [ ] **API endpoints don't leak sensitive data**
  - Check /health response — no credentials exposed
  - Check /portfolios response — no API keys exposed

- [ ] **POST endpoints (simulation, valuations) are protected**
  - Only admin should trigger these
  - Consider adding authentication before production

---

## 📋 Phase 11: Deployment Readiness

### Frontend Build
- [ ] **Production build succeeds**
  ```bash
  cd arena-frontend
  npm run build
  # Should complete without errors
  ```

- [ ] **Build output is valid**
  ```bash
  ls -la arena-frontend/.next/
  # Should show: app, cache, server, static, etc.
  ```

- [ ] **Production build can be tested**
  ```bash
  npm run start
  # Should start on http://localhost:3000
  ```

### Backend Production Readiness
- [ ] **Code is clean** (no debug print statements)
- [ ] **Error handling is comprehensive**
- [ ] **Logging is configured** (check config.py)
- [ ] **Environment variables are documented**

### Docker Testing (Optional but Recommended)
- [ ] **Docker is installed**
  ```bash
  docker --version
  ```

- [ ] **Docker Compose files are present**
  ```bash
  ls -la docker-compose.yml
  ```

- [ ] **Containers build successfully**
  ```bash
  docker-compose build
  ```

- [ ] **Containers start without errors**
  ```bash
  docker-compose up
  ```

- [ ] **Services are accessible**
  - Frontend: http://localhost:3000
  - Backend API: http://localhost:8000/health

---

## ✅ Final Checklist

- [ ] All tests in Phases 1-11 passed
- [ ] No critical errors in logs or console
- [ ] All UI elements render correctly
- [ ] Admin functionality works (simulate, update valuations)
- [ ] Data persists across restarts
- [ ] Production build created and tested
- [ ] Team reviewed the setup
- [ ] Deployment procedure documented
- [ ] Backup of current deployment created
- [ ] Deployment credentials/keys updated

---

## 🎯 Deployment Decision

### ✅ Ready to Deploy If:
- All checkboxes above are marked
- No critical issues found
- Performance is acceptable
- Team approval obtained

### ⏸️ Hold Deployment If:
- Any critical tests failed
- Unresolved errors in logs
- API response times > 5 seconds
- Memory usage growing excessively
- Team concerns exist

---

## 📝 Sign-Off

```
Tested By:        _________________________
Date:             _________________________
Status:           ☐ Ready for Production
                  ☐ Needs More Testing
Issues Found:     _________________________
                  _________________________
                  _________________________
```

---

## 🔗 Related Documents

- `SETUP_AND_TESTING_GUIDE.md` — Detailed setup instructions
- `quick-start.sh` — Automated setup script (Linux/Mac)
- `quick-start.bat` — Automated setup script (Windows)
- `docker-compose.yml` — Container-based testing setup
