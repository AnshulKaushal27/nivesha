"""
Trading calendar that keeps itself current for years ahead.

Sources, in order of trust:
  1. NSE's published trading-holiday list (refreshed monthly; NSE publishes the
     next year in December)
  2. the static table below (known lists at the time of writing)
  3. fixed-date national holidays for any year — Republic Day, Ambedkar
     Jayanti, Maharashtra Day, Independence Day, Gandhi Jayanti, Christmas —
     so a year nobody has loaded yet still skips the certain closures
Weekends are never trading days.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import MarketHoliday, SessionLocal

logger = logging.getLogger(__name__)

STATIC_HOLIDAYS: dict[date, str] = {
    # 2026
    date(2026, 1, 15): "Municipal Corporation Election - Maharashtra", date(2026, 1, 26): "Republic Day",
    date(2026, 3, 3): "Holi", date(2026, 3, 26): "Shri Ram Navami", date(2026, 3, 31): "Shri Mahavir Jayanti",
    date(2026, 4, 3): "Good Friday", date(2026, 4, 14): "Dr. Baba Saheb Ambedkar Jayanti", date(2026, 5, 1): "Maharashtra Day",
    date(2026, 5, 28): "Bakri Id", date(2026, 6, 26): "Muharram", date(2026, 9, 14): "Ganesh Chaturthi",
    date(2026, 10, 2): "Gandhi Jayanti", date(2026, 10, 20): "Dussehra", date(2026, 11, 10): "Diwali-Balipratipada",
    date(2026, 11, 24): "Guru Nanak Jayanti", date(2026, 12, 25): "Christmas",
    # 2027
    date(2027, 1, 26): "Republic Day", date(2027, 3, 1): "Mahashivratri", date(2027, 3, 22): "Holi",
    date(2027, 3, 30): "Good Friday", date(2027, 4, 11): "Id-Ul-Fitr (tentative)", date(2027, 4, 14): "Dr. Baba Saheb Ambedkar Jayanti",
    date(2027, 4, 21): "Ram Navami", date(2027, 5, 1): "Maharashtra Day", date(2027, 6, 17): "Bakri Id (tentative)",
    date(2027, 8, 15): "Independence Day", date(2027, 9, 5): "Ganesh Chaturthi", date(2027, 10, 2): "Gandhi Jayanti",
    date(2027, 10, 9): "Dussehra", date(2027, 11, 1): "Diwali Laxmi Pujan", date(2027, 11, 2): "Diwali Balipratipada",
    date(2027, 11, 15): "Guru Nanak Jayanti", date(2027, 12, 25): "Christmas",
}

FIXED_NATIONAL = {(1, 26): "Republic Day", (4, 14): "Dr. Baba Saheb Ambedkar Jayanti", (5, 1): "Maharashtra Day",
                  (8, 15): "Independence Day", (10, 2): "Gandhi Jayanti", (12, 25): "Christmas"}

NSE_HOLIDAY_URL = "https://www.nseindia.com/api/holiday-master?type=trading"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*", "Accept-Language": "en-IN,en;q=0.9", "Referer": "https://www.nseindia.com/",
}

_cache: dict[date, str] = {}
_cache_loaded_on: date | None = None


def fixed_holidays(year: int) -> dict[date, str]:
    return {date(year, m, d): n for (m, d), n in FIXED_NATIONAL.items()}


def seed_static(db: Session) -> int:
    """Insert the static list and fixed national days for the next 3 years (no overwrite of NSE rows)."""
    known = {r.date for r in db.execute(select(MarketHoliday)).scalars().all()}
    rows = []
    for d, n in STATIC_HOLIDAYS.items():
        if d not in known:
            rows.append(MarketHoliday(date=d, name=n, source="static"))
    for y in range(date.today().year, date.today().year + 4):
        for d, n in fixed_holidays(y).items():
            if d not in known and d not in STATIC_HOLIDAYS:
                rows.append(MarketHoliday(date=d, name=n, source="fixed"))
    db.add_all(rows)
    db.commit()
    return len(rows)


def fetch_nse_holidays() -> dict[date, str]:
    """NSE's list for the current year (and the next when published). Needs a cookie warm-up."""
    with httpx.Client(headers=_HEADERS, timeout=20, follow_redirects=True) as c:
        c.get("https://www.nseindia.com/")                        # sets the cookies the API expects
        r = c.get(NSE_HOLIDAY_URL)
        r.raise_for_status()
        data = r.json()
    out: dict[date, str] = {}
    for seg in ("CM", "FO", "CD"):
        for item in data.get(seg, []) or []:
            raw = item.get("tradingDate") or item.get("date")
            if not raw:
                continue
            for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y"):
                try:
                    out[datetime.strptime(raw.strip(), fmt).date()] = (item.get("description") or "NSE holiday").strip()
                    break
                except ValueError:
                    continue
        if out:
            break                                                  # CM (cash market) is what we trade
    return out


def refresh_from_nse(db: Session) -> dict:
    """Merge NSE's list into the table. Returns counts; raises on network failure."""
    fetched = fetch_nse_holidays()
    if not fetched:
        raise RuntimeError("NSE returned an empty holiday list")
    existing = {r.date: r for r in db.execute(select(MarketHoliday)).scalars().all()}
    added = updated = 0
    for d, n in fetched.items():
        if d in existing:
            if existing[d].source != "nse":
                existing[d].source, existing[d].name = "nse", n
                updated += 1
        else:
            db.add(MarketHoliday(date=d, name=n, source="nse"))
            added += 1
    db.commit()
    _invalidate()
    years = sorted({d.year for d in fetched})
    logger.info("NSE holidays refreshed: %d fetched (%s), %d added, %d confirmed", len(fetched), years, added, updated)
    return {"fetched": len(fetched), "years": years, "added": added, "updated": updated}


def _invalidate() -> None:
    global _cache_loaded_on
    _cache_loaded_on = None


def _load() -> dict[date, str]:
    global _cache, _cache_loaded_on
    if _cache_loaded_on == date.today():
        return _cache
    merged: dict[date, str] = {}
    for y in range(date.today().year - 1, date.today().year + 5):
        merged.update(fixed_holidays(y))
    merged.update(STATIC_HOLIDAYS)
    try:
        with SessionLocal() as db:
            for r in db.execute(select(MarketHoliday)).scalars().all():
                merged[r.date] = r.name
    except Exception as exc:                        # noqa: BLE001 — table missing before migration, etc.
        logger.warning("holiday table unavailable (%s); using static + fixed lists", exc)
    _cache, _cache_loaded_on = merged, date.today()
    return _cache


def holiday_name(d: date) -> str | None:
    return _load().get(d)


def is_trading_day(d: date | None = None) -> bool:
    d = d or date.today()
    if d.weekday() >= 5:
        return False
    return d not in _load()


def next_trading_day(d: date | None = None) -> date:
    d = (d or date.today()) + timedelta(days=1)
    while not is_trading_day(d):
        d += timedelta(days=1)
    return d


def upcoming(n: int = 5) -> list[dict]:
    today = date.today()
    return [{"date": str(d), "name": name} for d, name in sorted(_load().items()) if d >= today][:n]


def coverage() -> dict:
    h = _load()
    years = sorted({d.year for d in h})
    by_source: dict[str, int] = {}
    try:
        with SessionLocal() as db:
            for r in db.execute(select(MarketHoliday)).scalars().all():
                by_source[r.source] = by_source.get(r.source, 0) + 1
    except Exception:                               # noqa: BLE001
        pass
    return {"years_covered": years, "total": len(h), "by_source": by_source, "next": upcoming(5)}
