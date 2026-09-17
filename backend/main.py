import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import Base, engine
from routes import leaderboard, portfolios, market, admin
from scheduler import setup_scheduler
from database import Portfolio, DailyValuation

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Ensure all tables exist
Base.metadata.create_all(bind=engine)


# ── Lifespan ───────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = setup_scheduler()
    scheduler.start()
    logger.info("✅ APScheduler started (IST timezone)")
    yield
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")


# ── App ────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Investment Arena",
    description="AI Hedge Fund Simulator — NSE/NIFTY200",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # lock this down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────
app.include_router(leaderboard.router)
app.include_router(portfolios.router)
app.include_router(market.router)
app.include_router(admin.router)


@app.get("/health")
def health():
    from database import SessionLocal, Portfolio
    from datetime import date
    db = SessionLocal()
    try:
        today_count = db.query(Portfolio).filter(Portfolio.date == date.today()).count()
    finally:
        db.close()
    return {
        "status":              "healthy",
        "version":             "2.0.0",
        "portfolios_today":    today_count,
    }