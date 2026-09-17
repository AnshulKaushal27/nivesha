# 🚀 AI Investment Arena — Deployment & Testing Package

## 📦 Package Contents

This package contains everything you need to test and deploy the new frontend alongside your existing backend.

### Documentation Files

1. **SETUP_AND_TESTING_GUIDE.md** ⭐ START HERE
   - Complete step-by-step setup instructions
   - Environment configuration guide
   - Troubleshooting section
   - Deployment checklist

2. **QUICK_REFERENCE.md**
   - Quick command reference
   - All important URLs and file locations
   - Common troubleshooting commands
   - Test scenarios

3. **TESTING_CHECKLIST.md**
   - Comprehensive testing checklist (11 phases)
   - Pre-deployment verification
   - Sign-off template

4. **API_REFERENCE.md**
   - Complete API endpoint documentation
   - Request/response examples
   - curl command examples
   - Common workflows

### Setup & Configuration Files

5. **.env.backend.example**
   - Backend environment variable template
   - Copy to `backend/.env` and fill in your values

6. **quick-start.sh**
   - Automated setup script for Linux/Mac
   - Installs dependencies and creates config files
   - Run with: `chmod +x quick-start.sh && ./quick-start.sh`

7. **quick-start.bat**
   - Automated setup script for Windows
   - Same functionality as shell script
   - Double-click to run

### Docker Files

8. **docker-compose.yml**
   - Complete Docker Compose configuration
   - Runs both backend and frontend in containers
   - Includes healthchecks and volume mounts

9. **backend.Dockerfile**
   - Docker image for FastAPI backend
   - Copy to `backend/Dockerfile`

10. **frontend.Dockerfile**
    - Docker image for Next.js frontend
    - Copy to `arena-frontend/Dockerfile`

---

## ⚡ Quick Start (5 Minutes)

### For Linux/Mac Users:
```bash
# 1. Extract all files to your project root
# 2. Run the setup script
chmod +x quick-start.sh
./quick-start.sh

# 3. Edit backend/.env with your API key
nano backend/.env
# Update AICREDITS_API_KEY=your_key_here

# 4. Start the servers (in separate terminals)
# Terminal 1:
cd backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2:
cd arena-frontend
npm run dev

# 5. Open http://localhost:3000 in your browser
```

### For Windows Users:
```bash
# 1. Extract all files to your project root
# 2. Run the setup script
quick-start.bat

# 3. Edit backend\.env with your API key
# Open in text editor and update: AICREDITS_API_KEY=your_key_here

# 4. Start the servers (in separate terminals)
# Terminal 1:
cd backend
venv\Scripts\activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2:
cd arena-frontend
npm run dev

# 5. Open http://localhost:3000 in your browser
```

### For Docker Users:
```bash
# 1. Ensure Docker Desktop is running
# 2. Create .env file with your API key
echo "AICREDITS_API_KEY=your_key_here" > .env

# 3. Build and run
docker-compose up

# 4. Open http://localhost:3000
# 5. API available at http://localhost:8000
```

---

## 📋 What You Get

### Backend (FastAPI)
- ✅ REST API with 8+ endpoints
- ✅ SQLite database (can upgrade to PostgreSQL)
- ✅ APScheduler for scheduled tasks (8:40 AM & 3:45 PM IST)
- ✅ CORS middleware configured
- ✅ Interactive API docs at `/docs`

### Frontend (Next.js 14)
- ✅ Beautiful dark/light theme UI
- ✅ 5 main sections: Dashboard, Leaderboard, Market Intel, Portfolios, History
- ✅ Real-time data fetching from backend
- ✅ Interactive charts with recharts
- ✅ Admin controls for simulation & valuations

### Integration
- ✅ Automatic API discovery
- ✅ Fallback to localhost:8000 if not configured
- ✅ Supports environment variable configuration
- ✅ Production-ready error handling

---

## 🎯 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AI Investment Arena 2.0                   │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────┐              ┌──────────────────────┐
│   Next.js Frontend   │              │   FastAPI Backend    │
│  (Port 3000)         │◄────────────►│  (Port 8000)         │
│                      │    HTTP      │                      │
│ • Dashboard          │              │ • /simulation/today  │
│ • Leaderboard        │              │ • /leaderboard       │
│ • Market Intel       │              │ • /portfolios        │
│ • Portfolios         │              │ • /market/candidates │
│ • History            │              │ • /analytics/history │
│ • Admin Controls     │              │ • /simulate-and-save │
└──────────────────────┘              └──────────────────────┘
                                               │
                                               ▼
                                      ┌──────────────────┐
                                      │   SQLite DB      │
                                      │  (arena.db)      │
                                      └──────────────────┘
```

---

## 📚 Documentation Guide

### For Quick Setup
→ Start with **QUICK_REFERENCE.md**

### For Complete Setup
→ Follow **SETUP_AND_TESTING_GUIDE.md** step-by-step

### For Testing Verification
→ Use **TESTING_CHECKLIST.md** before deployment

### For API Integration
→ Reference **API_REFERENCE.md** for all endpoints

---

## 🔒 Security Considerations

### Before Production Deployment

1. **CORS Configuration**
   - Current: `allow_origins=["*"]` (development only)
   - Update in `backend/main.py` line 44 to specific domains

2. **Environment Variables**
   - Never commit `.env` files to git
   - Use secret management for production keys
   - Rotate API keys regularly

3. **Database**
   - Migrate from SQLite to PostgreSQL for production
   - Enable encryption at rest
   - Regular backups

4. **API Authentication**
   - Consider adding API key authentication
   - Implement rate limiting
   - Add request logging

5. **HTTPS**
   - Use SSL/TLS certificates
   - Redirect HTTP to HTTPS

---

## 🚀 Deployment Steps

### Step 1: Local Testing
```bash
1. Follow Quick Start section above
2. Run through Testing Checklist
3. Verify all functionality works
```

### Step 2: Backend Deployment
```bash
1. Build production bundle
2. Deploy to your server/cloud
3. Update DATABASE_URL to PostgreSQL
4. Set all environment variables
5. Run migrations if needed
6. Update CORS to whitelist frontend domain
```

### Step 3: Frontend Deployment
```bash
1. Build production bundle: npm run build
2. Deploy .next directory to hosting (Vercel, AWS, etc.)
3. Update NEXT_PUBLIC_API_URL to production backend
4. Set any environment variables on hosting platform
```

### Step 4: Verification
```bash
1. Test all endpoints: curl http://api.yourdomain.com/health
2. Open frontend: https://yourdomain.com
3. Run simulations
4. Monitor logs for errors
5. Keep backups of working configuration
```

---

## 🔍 Monitoring & Debugging

### View Backend Logs
```bash
# If running locally
# Terminal shows all logs in real-time

# If running in production
# Check application logs in your hosting platform
# Look for: ERROR, WARNING, or any failed requests
```

### View Frontend Errors
```bash
# In browser
F12 → Console tab
# Check for red error messages
# Check Network tab for failed API calls
```

### Check API Health
```bash
curl http://localhost:8000/health
# Should return: {"status": "healthy", ...}
```

### Database Status
```bash
# SQLite (local)
sqlite3 backend/arena.db ".tables"

# PostgreSQL (production)
psql -d arena_db -c "SELECT COUNT(*) FROM portfolio;"
```

---

## ❓ Frequently Asked Questions

### Q: What if I don't have the AICREDITS_API_KEY?
A: The backend will start but simulations will fail. Get a free key from https://aicredits.in

### Q: Can I use a different database?
A: Yes! Change `DATABASE_URL` in `.env` to PostgreSQL, MySQL, etc.

### Q: How do I update the frontend?
A: Rebuild with `npm run build` and redeploy the `.next` folder

### Q: Why is the scheduler in IST timezone?
A: Market hours are IST (Indian Standard Time). Change `MORNING_HOUR`, `CLOSING_HOUR` in config if needed

### Q: Can I run this in production with SQLite?
A: Not recommended. Migrate to PostgreSQL for concurrent access

### Q: How do I backup the database?
A: 
```bash
# SQLite
cp backend/arena.db backend/arena.db.backup

# PostgreSQL
pg_dump arena_db > backup.sql
```

### Q: Can I change the stocks monitored?
A: Yes! Edit `NIFTY_200_TICKERS` in `backend/config.py`

---

## 📞 Support Resources

1. **API Documentation** → http://localhost:8000/docs (Swagger UI)
2. **Code Comments** → Read inline documentation in source files
3. **Configuration** → Check `backend/config.py` for all settings
4. **Database Models** → See `backend/database.py` for schema

---

## ✅ Final Checklist Before Deployment

- [ ] All documentation read and understood
- [ ] Setup script ran successfully
- [ ] Backend starts without errors
- [ ] Frontend starts without errors
- [ ] API health check passes
- [ ] Browser can access frontend
- [ ] Admin simulations work
- [ ] Leaderboard shows data
- [ ] Testing checklist completed
- [ ] Team approved deployment
- [ ] Backup of current deployment created
- [ ] Environment variables for production set
- [ ] CORS configured for production domain
- [ ] Database backed up
- [ ] Deployment completed successfully

---

## 📝 Version Information

**AI Investment Arena Version:** 2.0.0  
**Backend Framework:** FastAPI 0.115.5  
**Frontend Framework:** Next.js 14.2.5  
**Node Version Required:** 18+  
**Python Version Required:** 3.11+  
**Package Created:** May 23, 2026

---

## 🎉 You're All Set!

Everything you need to test and deploy is in this package. Start with:

1. Read **SETUP_AND_TESTING_GUIDE.md**
2. Run **quick-start.sh** (or .bat on Windows)
3. Follow **TESTING_CHECKLIST.md**
4. Deploy when ready!

Good luck! 🚀

---

## 📞 Need Help?

- **Setup issues?** → Check SETUP_AND_TESTING_GUIDE.md troubleshooting
- **Testing help?** → Follow TESTING_CHECKLIST.md step-by-step
- **API questions?** → See API_REFERENCE.md with examples
- **Command reference?** → Use QUICK_REFERENCE.md

**Happy deploying!** 🎊
