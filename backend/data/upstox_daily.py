"""
Daily OHLCV from Upstox Historical Candle V3 into `daily_bars`, incrementally.

Reuses the instrument-key resolution and cache from services/market_data.py.
Requests are chunked per calendar year to stay inside the API's range limits
and paced under the 50 req/s ceiling with a wide margin.
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from urllib.parse import quote

import httpx
import pandas as pd
from sqlalchemy.orm import Session

from config import settings
from data.bars import last_bar_dates
from data.db_utils import upsert_ignore
from database import DailyBar
from services.market_data import UPSTOX_BASE, _ensure_instruments, _h, _ikey

logger = logging.getLogger(__name__)

_HTTP = httpx.Client(timeout=30.0)
_PACE_S = 0.08          # ≈ 12 req/s; polite and far under the limit
_CHUNK_DAYS = 360


def fetch_daily_ohlcv(ticker: str, start: date, end: date) -> pd.DataFrame:
    """One ticker, [start, end], as a DataFrame with ticker/date/open/high/low/close/volume."""
    key = _ikey(ticker)
    if not key:
        logger.debug("%s: no instrument key", ticker)
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []
    chunk_end = end
    while chunk_end >= start:
        chunk_start = max(start, chunk_end - timedelta(days=_CHUNK_DAYS))
        url = (f"{UPSTOX_BASE}/v3/historical-candle/{quote(key, safe='')}/days/1/"
               f"{chunk_end:%Y-%m-%d}/{chunk_start:%Y-%m-%d}")
        for attempt in range(1, 4):
            try:
                resp = _HTTP.get(url, headers=_h())
                if resp.status_code == 401:
                    raise RuntimeError("Upstox 401 — token expired or invalid. Re-login and update UPSTOX_ANALYTICS_TOKEN.")
                if resp.status_code == 429:
                    time.sleep(3 * attempt)
                    continue
                resp.raise_for_status()
                candles = resp.json().get("data", {}).get("candles", [])
                if candles:
                    df = pd.DataFrame(candles, columns=["ts", "open", "high", "low", "close", "volume", "oi"])
                    df["date"] = pd.to_datetime(df["ts"]).dt.tz_localize(None).dt.normalize()
                    frames.append(df[["date", "open", "high", "low", "close", "volume"]])
                break
            except RuntimeError:
                raise
            except Exception as exc:                    # noqa: BLE001
                logger.warning("%s chunk %s→%s attempt %d: %s", ticker, chunk_start, chunk_end, attempt, exc)
                time.sleep(1)
        chunk_end = chunk_start - timedelta(days=1)
        time.sleep(_PACE_S)

    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames).drop_duplicates("date").sort_values("date")
    out.insert(0, "ticker", ticker)
    out["source"] = "upstox"
    return out


def ingest_daily(db: Session, tickers: list[str], lookback_days: int | None = None) -> tuple[int, list[str]]:
    """
    Bring every ticker up to date. New tickers get `lookback_days` of history;
    known tickers get everything after their last stored bar.
    Returns (rows_written, failed_tickers).
    """
    lookback_days = lookback_days or settings.HISTORY_DAYS
    _ensure_instruments(tickers)
    last = last_bar_dates(db, tickers)
    today = date.today()

    written, failed = 0, []
    for i, t in enumerate(tickers, 1):
        start = (last[t] + timedelta(days=1)) if t in last else (today - timedelta(days=lookback_days))
        if start > today:
            continue
        try:
            df = fetch_daily_ohlcv(t, start, today)
        except RuntimeError:
            raise                                       # auth problems stop the whole run
        except Exception as exc:                        # noqa: BLE001
            logger.warning("%s: %s", t, exc)
            failed.append(t)
            continue
        if df.empty:
            if t not in last:
                failed.append(t)
            continue
        rows = [
            {"ticker": t, "date": r.date.date(), "open": r.open, "high": r.high,
             "low": r.low, "close": r.close, "volume": r.volume, "source": "upstox"}
            for r in df.itertuples(index=False)
        ]
        written += upsert_ignore(db, DailyBar.__table__, rows)
        if i % 50 == 0:
            db.commit()
            logger.info("  [%d/%d] %d rows so far", i, len(tickers), written)
    db.commit()
    logger.info("Upstox daily ingest: %d rows, %d tickers failed", written, len(failed))
    return written, failed
