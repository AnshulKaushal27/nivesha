"""Read daily bars out of Postgres/SQLite into a long DataFrame."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from config import settings
from database import DailyBar


def load_bars(
    db: Session,
    tickers: list[str] | None = None,
    start: date | None = None,
    end: date | None = None,
) -> pd.DataFrame:
    """Columns: ticker, date, open, high, low, close, volume. Sorted by ticker, date."""
    if start is None:
        start = date.today() - timedelta(days=settings.HISTORY_DAYS + 30)
    stmt = select(
        DailyBar.ticker, DailyBar.date, DailyBar.open, DailyBar.high,
        DailyBar.low, DailyBar.close, DailyBar.volume,
    ).where(DailyBar.date >= start)
    if end is not None:
        stmt = stmt.where(DailyBar.date <= end)
    if tickers:
        stmt = stmt.where(DailyBar.ticker.in_(tickers))
    stmt = stmt.order_by(DailyBar.ticker, DailyBar.date)
    rows = db.execute(stmt).all()
    df = pd.DataFrame(rows, columns=["ticker", "date", "open", "high", "low", "close", "volume"])
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def last_bar_dates(db: Session, tickers: list[str] | None = None) -> dict[str, date]:
    """Most recent bar date per ticker — drives incremental ingestion."""
    from sqlalchemy import func
    stmt = select(DailyBar.ticker, func.max(DailyBar.date)).group_by(DailyBar.ticker)
    if tickers:
        stmt = stmt.where(DailyBar.ticker.in_(tickers))
    return {t: d for t, d in db.execute(stmt).all()}
