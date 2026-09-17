"""
DEV-ONLY fallback: daily bars from Yahoo Finance via yfinance.

Exists so factor research and the UI can run on a laptop without a live
Upstox token (which expires every day at 03:30 IST). Never used on the server.
Tickers are already Yahoo-style ("RELIANCE.NS"), so no mapping is needed.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
from sqlalchemy.orm import Session

from config import settings
from data.bars import last_bar_dates
from data.db_utils import upsert_ignore
from database import DailyBar

logger = logging.getLogger(__name__)

_BATCH = 50


def ingest_daily_yahoo(db: Session, tickers: list[str], lookback_days: int | None = None) -> tuple[int, list[str]]:
    import yfinance as yf   # imported lazily: dev dependency

    lookback_days = lookback_days or settings.HISTORY_DAYS
    last = last_bar_dates(db, tickers)
    today = date.today()
    earliest_needed = min(
        [(last[t] + timedelta(days=1)) if t in last else (today - timedelta(days=lookback_days)) for t in tickers],
        default=today,
    )
    if earliest_needed > today:
        return 0, []

    written, failed = 0, []
    for start in range(0, len(tickers), _BATCH):
        batch = tickers[start:start + _BATCH]
        try:
            raw = yf.download(
                batch, start=earliest_needed, end=today + timedelta(days=1),
                group_by="ticker", auto_adjust=False, progress=False, threads=True,
            )
        except Exception as exc:                        # noqa: BLE001
            logger.warning("yahoo batch failed: %s", exc)
            failed.extend(batch)
            continue

        for t in batch:
            try:
                df = raw[t] if len(batch) > 1 else raw
            except KeyError:
                failed.append(t)
                continue
            df = df.dropna(subset=["Close"])
            if df.empty:
                failed.append(t)
                continue
            since = (last[t] + timedelta(days=1)) if t in last else None
            rows = []
            for ts, r in df.iterrows():
                d = ts.date()
                if since and d < since:
                    continue
                rows.append({
                    "ticker": t, "date": d,
                    "open": float(r["Open"]), "high": float(r["High"]), "low": float(r["Low"]),
                    "close": float(r["Close"]), "volume": float(r["Volume"] or 0.0), "source": "yahoo",
                })
            written += upsert_ignore(db, DailyBar.__table__, rows)
        db.commit()
        logger.info("  yahoo [%d/%d] %d rows so far", min(start + _BATCH, len(tickers)), len(tickers), written)

    logger.info("Yahoo daily ingest: %d rows, %d tickers failed", written, len(failed))
    return written, failed
