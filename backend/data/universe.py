"""
Index universe (NIFTY 500 by default) from NSE's published constituent CSV.

NSE's archive host serves the file to a browser-like client. If the download
fails, the previous snapshot in the database is used, and if there is none,
the static NIFTY_200_TICKERS list in config.py is the last resort.
"""

from __future__ import annotations

import io
import logging
from datetime import date

import httpx
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config import SECTOR_MAP, settings
from data.db_utils import upsert_ignore
from database import UniverseMember

logger = logging.getLogger(__name__)

INDEX_FILES = {
    "NIFTY 500": "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv",
    "NIFTY 200": "https://nsearchives.nseindia.com/content/indices/ind_nifty200list.csv",
    "NIFTY 50":  "https://nsearchives.nseindia.com/content/indices/ind_nifty50list.csv",
}

_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept": "text/csv,*/*;q=0.8",
    "Referer": "https://www.nseindia.com/",
}


def fetch_index_constituents(index_name: str | None = None) -> pd.DataFrame:
    """Download the constituent list. Columns: symbol, ticker, isin, company, industry."""
    index_name = index_name or settings.UNIVERSE_INDEX
    url = INDEX_FILES[index_name]
    resp = httpx.get(url, headers=_HEADERS, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    df.columns = [c.strip().lower() for c in df.columns]
    out = pd.DataFrame({
        "symbol":   df["symbol"].str.strip().str.upper(),
        "isin":     df.get("isin code", pd.Series([None] * len(df))),
        "company":  df.get("company name", pd.Series([None] * len(df))),
        "industry": df.get("industry", pd.Series([None] * len(df))),
    })
    out = out[df.get("series", pd.Series(["EQ"] * len(df))).str.strip().eq("EQ")]
    out["ticker"] = out["symbol"] + ".NS"
    return out.drop_duplicates("ticker").reset_index(drop=True)


def refresh_universe(db: Session, index_name: str | None = None, as_of: date | None = None) -> int:
    """Download and store today's snapshot. Returns rows written (0 if unchanged)."""
    index_name = index_name or settings.UNIVERSE_INDEX
    as_of = as_of or date.today()
    df = fetch_index_constituents(index_name)
    rows = [
        {
            "index_name": index_name, "as_of": as_of, "ticker": r.ticker, "symbol": r.symbol,
            "isin": r.isin if isinstance(r.isin, str) else None,
            "company": r.company if isinstance(r.company, str) else None,
            "industry": r.industry if isinstance(r.industry, str) else None,
        }
        for r in df.itertuples(index=False)
    ]
    written = upsert_ignore(db, UniverseMember.__table__, rows)
    db.commit()
    logger.info("Universe %s @ %s: %d constituents (%d new rows)", index_name, as_of, len(rows), written)
    return written


def latest_snapshot_date(db: Session, index_name: str | None = None) -> date | None:
    index_name = index_name or settings.UNIVERSE_INDEX
    return db.execute(
        select(func.max(UniverseMember.as_of)).where(UniverseMember.index_name == index_name)
    ).scalar()


def universe_tickers(db: Session, index_name: str | None = None) -> list[str]:
    """Tickers in the latest stored snapshot, or the static list if none exists."""
    index_name = index_name or settings.UNIVERSE_INDEX
    snap = latest_snapshot_date(db, index_name)
    if snap is None:
        logger.warning("No universe snapshot for %s — falling back to static NIFTY_200_TICKERS", index_name)
        return sorted(set(settings.NIFTY_200_TICKERS))
    rows = db.execute(
        select(UniverseMember.ticker)
        .where(UniverseMember.index_name == index_name, UniverseMember.as_of == snap)
    ).scalars().all()
    return sorted(rows)


def sector_lookup(db: Session, index_name: str | None = None) -> dict[str, str]:
    """ticker → industry from the latest snapshot, with SECTOR_MAP as fallback."""
    index_name = index_name or settings.UNIVERSE_INDEX
    snap = latest_snapshot_date(db, index_name)
    out = dict(SECTOR_MAP)
    if snap is None:
        return out
    rows = db.execute(
        select(UniverseMember.ticker, UniverseMember.industry)
        .where(UniverseMember.index_name == index_name, UniverseMember.as_of == snap)
    ).all()
    out.update({t: i for t, i in rows if i})
    return out
