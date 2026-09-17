from datetime import datetime, date as DateType
from sqlalchemy import (
    create_engine, Column, Integer, Float, String,
    Text, Date, DateTime, ForeignKey, UniqueConstraint, Index, JSON,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from config import settings

# ── Engine ─────────────────────────────────────────────────────────────────
connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# JSON on SQLite, JSONB on Postgres — same column definition everywhere.
JSONType = JSON().with_variant(JSONB(), "postgresql")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Models ─────────────────────────────────────────────────────────────────

class Portfolio(Base):
    """One portfolio per model per day."""
    __tablename__ = "portfolios"
    __table_args__ = (UniqueConstraint("model", "date", name="uq_model_date"),)

    id               = Column(Integer, primary_key=True, index=True)
    model            = Column(String(50), nullable=False, index=True)
    date             = Column(Date, nullable=False, index=True)
    starting_capital = Column(Float, default=100_000.0)
    total_invested   = Column(Float, default=0.0)
    remaining_cash   = Column(Float, default=0.0)
    strategy_summary = Column(Text)
    risk_level       = Column(String(20))
    created_at       = Column(DateTime, default=datetime.utcnow)

    holdings    = relationship("Holding",        back_populates="portfolio", cascade="all, delete-orphan")
    valuations  = relationship("DailyValuation", back_populates="portfolio", cascade="all, delete-orphan")


class Holding(Base):
    """Individual stock position inside a portfolio."""
    __tablename__ = "holdings"

    id                 = Column(Integer, primary_key=True, index=True)
    portfolio_id       = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    ticker             = Column(String(20), nullable=False)
    quantity           = Column(Float, default=0.0)
    entry_price        = Column(Float, default=0.0)
    invested_amount    = Column(Float, default=0.0)
    allocation_percent = Column(Float, default=0.0)
    confidence         = Column(Integer, default=70)
    reasoning          = Column(Text)
    sector             = Column(String(50))

    portfolio = relationship("Portfolio", back_populates="holdings")


class DailyValuation(Base):
    """End-of-day mark-to-market for each portfolio."""
    __tablename__ = "daily_valuations"
    __table_args__ = (UniqueConstraint("portfolio_id", "date", name="uq_portfolio_valdate"),)

    id              = Column(Integer, primary_key=True, index=True)
    portfolio_id    = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    date            = Column(Date, nullable=False, index=True)
    portfolio_value = Column(Float)
    return_pct      = Column(Float)
    unrealized_pnl  = Column(Float)

    portfolio = relationship("Portfolio", back_populates="valuations")


class MarketSnapshot(Base):
    """TOPSIS-ranked candidate list saved on each morning run."""
    __tablename__ = "market_snapshots"
    __table_args__ = (UniqueConstraint("date", "ticker", name="uq_snap_date_ticker"),)

    id              = Column(Integer, primary_key=True, index=True)
    date            = Column(Date, nullable=False, index=True)
    ticker          = Column(String(20), nullable=False)
    current_price   = Column(Float)
    rsi             = Column(Float)
    sma20           = Column(Float)
    sma50           = Column(Float)
    volatility      = Column(Float)
    volume_ratio    = Column(Float)
    one_month_return= Column(Float)
    sector          = Column(String(50))
    trend_score     = Column(Float)
    rsi_distance    = Column(Float)
    topsis_score    = Column(Float)


# ── v2: data spine ─────────────────────────────────────────────────────────

class UniverseMember(Base):
    """A constituent of an index on a given snapshot date (e.g. NIFTY 500)."""
    __tablename__ = "universe_members"
    __table_args__ = (UniqueConstraint("index_name", "ticker", "as_of", name="uq_universe_member"),)

    id         = Column(Integer, primary_key=True)
    index_name = Column(String(40), nullable=False, index=True)
    as_of      = Column(Date, nullable=False, index=True)
    ticker     = Column(String(24), nullable=False)      # "RELIANCE.NS" — the app-wide key
    symbol     = Column(String(20), nullable=False)      # "RELIANCE"
    isin       = Column(String(16))
    company    = Column(String(120))
    industry   = Column(String(60))


class DailyBar(Base):
    """One OHLCV bar per ticker per trading day. Source-agnostic."""
    __tablename__ = "daily_bars"
    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_daily_bar"),
        Index("ix_daily_bars_date", "date"),
    )

    id     = Column(Integer, primary_key=True)
    ticker = Column(String(24), nullable=False, index=True)
    date   = Column(Date, nullable=False)
    open   = Column(Float)
    high   = Column(Float)
    low    = Column(Float)
    close  = Column(Float, nullable=False)
    volume = Column(Float, default=0.0)
    source = Column(String(12), default="upstox")        # upstox | yahoo | nse


class FactorScore(Base):
    """Buy Rank output for one ticker on one date, with everything needed to explain it."""
    __tablename__ = "factor_scores"
    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_factor_score"),
        Index("ix_factor_scores_date_rank", "date", "buy_rank"),
    )

    id            = Column(Integer, primary_key=True)
    ticker        = Column(String(24), nullable=False, index=True)
    date          = Column(Date, nullable=False)
    buy_rank      = Column(Integer, nullable=False)      # 1–100 percentile
    topsis        = Column(Float, nullable=False)        # raw closeness coefficient
    band          = Column(String(12), nullable=False)   # Strong | Good | Neutral | Weak | Wait | Watch
    regime        = Column(String(12))                   # Sunny | Cloudy | Stormy | None until Weather ships
    sector        = Column(String(50))
    close         = Column(Float)
    raw           = Column(JSONType)                     # un-normalised factor values
    z             = Column(JSONType)                     # cross-sectional z-scores
    contributions = Column(JSONType)                     # z × weight, what the LLM explains
    eligible      = Column(Integer, default=1)           # 0 if filtered out (still stored for audit)
    created_at    = Column(DateTime, default=datetime.utcnow)


class RankExplanation(Base):
    """Cached 'Why this rank?' bullets. One LLM call per ticker per day, ever."""
    __tablename__ = "rank_explanations"
    __table_args__ = (UniqueConstraint("ticker", "date", name="uq_rank_explanation"),)

    id            = Column(Integer, primary_key=True)
    ticker        = Column(String(24), nullable=False, index=True)
    date          = Column(Date, nullable=False)
    bullets       = Column(JSONType, nullable=False)
    watch_out     = Column(Text)
    model         = Column(String(80))
    audit_dropped = Column(Integer, default=0)           # bullets removed by the number audit
    attempts      = Column(Integer, default=1)
    created_at    = Column(DateTime, default=datetime.utcnow)


class IngestRun(Base):
    """Audit trail for every batch job so a bad day can be traced."""
    __tablename__ = "ingest_runs"

    id          = Column(Integer, primary_key=True)
    job         = Column(String(40), nullable=False, index=True)
    started_at  = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime)
    status      = Column(String(12), default="running")  # running | ok | failed
    rows        = Column(Integer, default=0)
    detail      = Column(Text)