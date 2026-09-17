from datetime import datetime, date as DateType
from sqlalchemy import (
    create_engine, Column, Integer, Float, String,
    Text, Date, DateTime, ForeignKey, UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from config import settings

# ── Engine ─────────────────────────────────────────────────────────────────
connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


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