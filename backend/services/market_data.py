"""
market_data.py  —  Upstox Analytics Token edition
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Instrument key resolution priority:
  1. Local cache file  (instrument_cache.json)  — instant, used on every run after first
  2. Upstox CSV master — tried with auth token, then without
  3. Upstox SearchInstruments API — guaranteed to work, ~30 s one-time build

After step 3 succeeds once, the cache file means steps 2 and 3
are never needed again unless the cache expires (7 days).
"""

import gzip
import io
import json
import logging
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

import httpx
import numpy as np
import pandas as pd

from config import settings, SECTOR_MAP

logger = logging.getLogger(__name__)

UPSTOX_BASE      = "https://api.upstox.com"
CACHE_FILE       = Path("instrument_cache.json")
CACHE_MAX_DAYS   = 7                 # rebuild cache after 7 days
_HTTP            = httpx.Client(timeout=30.0)


# ── Auth ───────────────────────────────────────────────────────────────────

def _h() -> Dict[str, str]:
    tok = settings.UPSTOX_ANALYTICS_TOKEN
    if not tok:
        raise RuntimeError(
            "UPSTOX_ANALYTICS_TOKEN is empty — add it to .env and restart."
        )
    return {"Authorization": f"Bearer {tok}", "Accept": "application/json"}


# ── Instrument key cache ───────────────────────────────────────────────────

_IKEYS:  Dict[str, str] = {}   # { "RELIANCE": "NSE_EQ|INE002A01018" }
_LOADED: bool = False


def _read_cache() -> Dict[str, str]:
    """Return cached mapping if it exists and is younger than CACHE_MAX_DAYS."""
    if not CACHE_FILE.exists():
        return {}
    try:
        raw  = json.loads(CACHE_FILE.read_text())
        age  = (date.today() - date.fromisoformat(raw.get("_date", "2000-01-01"))).days
        if age > CACHE_MAX_DAYS:
            logger.info(f"Instrument cache is {age} days old — will refresh")
            return {}
        return {k: v for k, v in raw.items() if not k.startswith("_")}
    except Exception:
        return {}


def _write_cache(mapping: Dict[str, str]) -> None:
    try:
        CACHE_FILE.write_text(
            json.dumps({"_date": str(date.today()), **mapping}, indent=2)
        )
        logger.info(f"Instrument cache saved → {CACHE_FILE} ({len(mapping)} symbols)")
    except Exception as exc:
        logger.warning(f"Could not write instrument cache: {exc}")


def _try_csv_master() -> Optional[Dict[str, str]]:
    url = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
    try:
        resp = httpx.get(url, timeout=60)
        if resp.status_code != 200:
            logger.warning(f"Instrument JSON: HTTP {resp.status_code}")
            return None

        with gzip.open(io.BytesIO(resp.content)) as f:
            instruments = json.load(f)

        mapping = {}
        for item in instruments:
            if (
                item.get("segment") == "NSE_EQ"
                and item.get("instrument_type") == "EQ"
            ):
                sym = item.get("trading_symbol", "").strip().upper()
                key = item.get("instrument_key", "").strip()
                if sym and key:
                    mapping[sym] = key

        logger.info(f"Instrument JSON downloaded: {len(mapping)} NSE_EQ symbols")
        return mapping

    except Exception as exc:
        logger.warning(f"Instrument JSON download failed: {exc}")
        return None


def _search_one(symbol: str) -> Optional[str]:
    try:
        resp = _HTTP.get(
            f"{UPSTOX_BASE}/v2/instruments/search",   # ← was /market-quote/search
            params={"q": symbol, "exchange": "NSE"},
            headers=_h(),
            timeout=10,
        )
        if resp.status_code != 200:
            logger.debug(f"Search {symbol}: HTTP {resp.status_code}")
            return None

        for item in resp.json().get("data", []):
            if (
                item.get("trading_symbol", "").upper() == symbol.upper()
                and item.get("segment", "").upper() == "NSE_EQ"
            ):
                return item["instrument_key"]

    except Exception as exc:
        logger.debug(f"Search {symbol}: {exc}")

    return None


def _ensure_instruments(tickers: List[str]) -> None:
    """
    Guarantee _IKEYS is populated for every ticker we care about.

    Resolution order:
      1. Local cache file  (sub-second)
      2. Upstox CSV master (a few seconds)
      3. SearchInstruments API  (one symbol at a time, ~30 s, cached after)
    """
    global _IKEYS, _LOADED
    if _LOADED:
        return

    needed = {t.replace(".NS", "").upper() for t in tickers}

    # ── Step 1: cache file ─────────────────────────────────────────────────
    cached = _read_cache()
    if needed.issubset(cached.keys()):
        _IKEYS  = cached
        _LOADED = True
        logger.info(f"Instrument master: {len(_IKEYS)} symbols loaded from cache")
        return

    # ── Step 2: CSV master ─────────────────────────────────────────────────
    logger.info("Attempting Upstox instrument master CSV download...")
    csv_map = _try_csv_master()

    if csv_map and needed.issubset(csv_map.keys()):
        _IKEYS  = {**cached, **csv_map}
        _write_cache(_IKEYS)
        _LOADED = True
        logger.info(f"Instrument master: {len(_IKEYS)} symbols from CSV")
        return

    # ── Step 3: SearchInstruments API ──────────────────────────────────────
    partial = {**cached, **(csv_map or {})}
    missing = needed - set(partial.keys())

    logger.warning(
        f"CSV master incomplete — using SearchInstruments API "
        f"for {len(missing)} remaining symbols (one-time, ~{len(missing) // 4}s)..."
    )

    found = 0
    for i, sym in enumerate(sorted(missing), 1):
        ikey = _search_one(sym)
        if ikey:
            partial[sym] = ikey
            found += 1
            logger.debug(f"  [{i:>3}/{len(missing)}] ✓ {sym:<20} → {ikey}")
        else:
            logger.warning(f"  [{i:>3}/{len(missing)}] ✗ {sym} — not found in Upstox")

        time.sleep(0.25)   # polite pacing

    _IKEYS  = partial
    _write_cache(_IKEYS)
    _LOADED = True
    logger.info(
        f"Instrument master ready — "
        f"{found}/{len(missing)} new symbols found via search, "
        f"{len(_IKEYS)} total"
    )


def _ikey(yahoo_ticker: str) -> Optional[str]:
    """'RELIANCE.NS'  →  'NSE_EQ|INE002A01018'  (requires _ensure_instruments first)"""
    sym = yahoo_ticker.replace(".NS", "").upper().strip()
    return _IKEYS.get(sym)


# ── Historical Candle V3 ───────────────────────────────────────────────────

def _fetch_candles(
    ticker:    str,
    from_date: date,
    to_date:   date,
) -> Optional[pd.DataFrame]:
    """
    Fetch daily OHLCV from Upstox Historical Candle Data V3.
    Returns DataFrame[Close, Volume] oldest→newest, or None.
    """
    key = _ikey(ticker)
    if not key:
        logger.debug(f"{ticker}: no instrument key")
        return None

    encoded = quote(key, safe="")

    url = (
        f"{UPSTOX_BASE}/v3/historical-candle/{encoded}/days/1/"
        f"{to_date.strftime('%Y-%m-%d')}/{from_date.strftime('%Y-%m-%d')}"
    )

    for attempt in range(1, 4):
        try:
            resp = _HTTP.get(url, headers=_h())

            if resp.status_code == 401:
                raise RuntimeError(
                    "Upstox 401 — token rejected. "
                    "Check UPSTOX_ANALYTICS_TOKEN in .env."
                )
            if resp.status_code == 429:
                wait = 3 * attempt
                logger.warning(f"{ticker}: rate-limited — sleeping {wait}s")
                time.sleep(wait)
                continue

            resp.raise_for_status()

            candles = resp.json().get("data", {}).get("candles", [])
            if not candles:
                return None

            # schema: [timestamp, open, high, low, close, volume, oi]
            df = pd.DataFrame(
                candles,
                columns=["ts", "Open", "High", "Low", "Close", "Volume", "OI"],
            )
            df.index   = pd.to_datetime(df["ts"]).dt.normalize()
            df         = df.sort_index()
            df["Close"]  = pd.to_numeric(df["Close"],  errors="coerce")
            df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce").fillna(0)

            return df[["Close", "Volume"]].dropna(subset=["Close"])

        except RuntimeError:
            raise
        except Exception as exc:
            logger.warning(f"{ticker} attempt {attempt}: {exc}")
            if attempt < 3:
                time.sleep(1)

    return None


# ── LTP V3 ────────────────────────────────────────────────────────────────

"""
FIXED get_latest_prices() — Add this to your market_data.py
"""
def get_latest_prices(tickers: List[str]) -> Dict[str, float]:
    """
    Fetch latest prices from Upstox LTP V3.

    FIXED:
    - Uses payload["instrument_token"]
    - Correctly maps prices back to Yahoo tickers
    - Handles Upstox response structure properly
    """

    if not tickers:
        return {}

    _ensure_instruments(tickers)

    # instrument_token -> yahoo ticker
    ikey_map: Dict[str, str] = {}

    for ticker in tickers:
        key = _ikey(ticker)

        if key:
            ikey_map[key] = ticker
        else:
            logger.warning(
                f"{ticker}: no instrument key — entry price fallback"
            )

    if not ikey_map:
        logger.error("❌ No instrument keys resolved")
        return {}

    try:

        instrument_keys = ",".join(ikey_map.keys())

        resp = _HTTP.get(
            f"{UPSTOX_BASE}/v3/market-quote/ltp",
            params={"instrument_key": instrument_keys},
            headers=_h(),
        )

        if resp.status_code == 401:
            raise RuntimeError(
                "Upstox Analytics Token rejected (401)"
            )

        resp.raise_for_status()

        body = resp.json()
        data = body.get("data", {})

        if not isinstance(data, dict):
            logger.error(
                f"❌ Invalid response format: {type(data)}"
            )
            return {}

        prices: Dict[str, float] = {}

        for _, payload in data.items():

            instrument_token = payload.get("instrument_token")
            last_price = payload.get("last_price")

            if not instrument_token:
                logger.warning(
                    f"Missing instrument_token in payload: {payload}"
                )
                continue

            yahoo_ticker = ikey_map.get(instrument_token)

            if not yahoo_ticker:
                logger.warning(
                    f"⚠️ Instrument token not found in map: "
                    f"{instrument_token}"
                )
                continue

            if last_price is not None:
                prices[yahoo_ticker] = float(last_price)

                logger.info(
                    f"✓ {yahoo_ticker:<20} "
                    f"₹{float(last_price):,.2f}"
                )

        logger.info(
            f"✅ LTP fetched: "
            f"{len(prices)}/{len(tickers)} prices"
        )

        if not prices:
            logger.critical(
                "❌ ZERO PRICES FETCHED!"
            )

        return prices

    except RuntimeError:
        raise

    except Exception as exc:
        logger.error(
            f"❌ LTP fetch failed: {exc}",
            exc_info=True,
        )
        return {}

# def get_latest_prices(tickers: List[str]) -> Dict[str, float]:
#     """
#     Fetch last traded price for all tickers via Upstox LTP V3.
#     Single API call regardless of ticker count.
    
#     FIXED: Added extensive logging to debug response parsing.
#     """
#     if not tickers:
#         return {}

#     _ensure_instruments(tickers)

#     ikey_map: Dict[str, str] = {}
#     for t in tickers:
#         k = _ikey(t)
#         if k:
#             ikey_map[k] = t
#         else:
#             logger.warning(f"{t}: no instrument key — entry price will be used")

#     if not ikey_map:
#         logger.error("❌ No instrument keys resolved! ikey_map is empty")
#         return {}

#     try:
#         instrument_keys_str = ",".join(ikey_map)
#         url = f"{UPSTOX_BASE}/v3/market-quote/ltp"
        
#         logger.info(f"📡 LTP Request:")
#         logger.info(f"   URL: {url}")
#         logger.info(f"   Params: instrument_key={instrument_keys_str}")
#         logger.info(f"   ikey_map: {ikey_map}")
        
#         resp = _HTTP.get(
#             url,
#             params={"instrument_key": instrument_keys_str},
#             headers=_h(),
#         )
        
#         # ⚠️  CAPTURE RESPONSE
#         logger.info(f"✅ Response Status: {resp.status_code}")
#         logger.info(f"📝 Response Headers: {dict(resp.headers)}")
        
#         if resp.status_code == 401:
#             raise RuntimeError("Upstox Analytics Token rejected (401)")

#         resp.raise_for_status()

#         # ⚠️  LOG RAW RESPONSE
#         raw_text = resp.text[:3000]  # First 3000 chars
#         logger.info(f"📄 Raw Response Body:\n{raw_text}")
        
#         # ⚠️  PARSE AND INSPECT
#         json_data = resp.json()
#         logger.info(f"✅ Parsed as JSON successfully")
#         logger.info(f"🔑 Top-level keys in response: {list(json_data.keys())}")
#         logger.info(f"📊 Full response object: {json_data}")
        
#         # ⚠️  LOOK FOR DATA KEY
#         data_obj = json_data.get("data", {})
#         logger.info(f"🔍 data object type: {type(data_obj)}")
#         logger.info(f"🔍 data object: {data_obj}")
#         logger.info(f"🔍 data object keys: {list(data_obj.keys()) if isinstance(data_obj, dict) else 'N/A'}")
#         logger.info(f"🔍 data object length: {len(data_obj) if hasattr(data_obj, '__len__') else 'N/A'}")
        
#         # ⚠️  PARSE PRICES
#         prices: Dict[str, float] = {}
        
#         if not isinstance(data_obj, dict):
#             logger.error(f"❌ data is not a dict! Type: {type(data_obj)}, value: {data_obj}")
#             return {}
        
#         if not data_obj:
#             logger.error(f"❌ data dict is empty! Response may have no prices.")
#             return {}
        
#         for key_colon, payload in data_obj.items():
#             logger.debug(f"  Processing key: {key_colon}")
#             logger.debug(f"    Payload: {payload}")
            
#             # Try both formats: with colon and with pipe
#             key_with_pipe = key_colon.replace(":", "|")
#             logger.debug(f"    Looking up (after replace): {key_with_pipe}")
            
#             yahoo = ikey_map.get(key_with_pipe)
            
#             if not yahoo:
#                 logger.warning(f"    ⚠️  Key {key_colon} not in ikey_map")
#                 logger.warning(f"       ikey_map keys: {list(ikey_map.keys())}")
#                 continue
            
#             last_price = payload.get("last_price")
#             logger.debug(f"    ✓ {yahoo} = {last_price}")
            
#             if last_price is not None:
#                 prices[yahoo] = float(last_price)
        
#         logger.info(f"📈 Final prices extracted: {prices}")
#         logger.info(f"✅ LTP: {len(prices)}/{len(tickers)} prices fetched")
        
#         if len(prices) == 0:
#             logger.critical("❌ ZERO PRICES FETCHED! Check response structure above ↑")
        
#         return prices

#     except RuntimeError:
#         raise
#     except Exception as exc:
#         logger.error(f"❌ LTP fetch failed: {exc}", exc_info=True)
#         return {}


# ── Indicators ─────────────────────────────────────────────────────────────

def _rsi(close: pd.Series, period: int = 14) -> float:
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(period).mean()
    loss  = (-delta.clip(upper=0)).rolling(period).mean()
    val   = (100 - (100 / (1 + gain / loss.replace(0, np.nan)))).iloc[-1]
    return round(float(val), 2) if pd.notna(val) else 50.0

def _volatility(close: pd.Series) -> float:
    rets = close.pct_change().dropna()
    return round(float(rets.std() * np.sqrt(252) * 100), 2) if len(rets) >= 5 else 30.0

def _volume_ratio(vol: pd.Series, period: int = 20) -> float:
    avg = vol.rolling(period).mean().iloc[-1]
    return round(float(vol.iloc[-1] / avg), 2) if avg and avg > 0 else 1.0

def _indicators(ticker: str, df: pd.DataFrame) -> Optional[Dict]:
    try:
        close  = df["Close"].astype(float)
        volume = df["Volume"].astype(float)

        price_now = float(close.iloc[-1])
        price_21d = float(close.iloc[-21] if len(close) >= 21 else close.iloc[0])
        sma20     = float(close.rolling(20).mean().iloc[-1])
        sma50     = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else sma20
        rsi       = _rsi(close)
        vol       = _volatility(close)
        vr        = _volume_ratio(volume)
        ret1m     = round(((price_now - price_21d) / price_21d) * 100, 2)

        trend = 0.0
        if price_now > sma20: trend += 5
        if price_now > sma50: trend += 5
        trend += round(max(0.0, min(10.0, ret1m / 3)), 3)

        return {
            "ticker":           ticker,
            "current_price":    round(price_now, 2),
            "rsi":              rsi,
            "rsi_distance":     round(abs(rsi - 50), 2),
            "sma20":            round(sma20, 2),
            "sma50":            round(sma50, 2),
            "volatility":       vol,
            "volume_ratio":     vr,
            "one_month_return": ret1m,
            "sector":           SECTOR_MAP.get(ticker, "Unknown"),
            "trend_score":      trend,
        }
    except Exception as exc:
        logger.warning(f"{ticker}: indicator error — {exc}")
        return None


# ── Public API ─────────────────────────────────────────────────────────────

def fetch_stock_data(tickers: List[str]) -> List[Dict]:
    """
    Fetch 3-month OHLCV + compute indicators for all tickers.
    Instrument master is resolved and cached automatically.
    """
    _ensure_instruments(tickers)      # ← resolves + caches instrument keys

    to_date   = date.today()
    from_date = to_date - timedelta(days=95)

    logger.info(f"Fetching candles for {len(tickers)} tickers ({from_date} → {to_date})")

    results: List[Dict] = []
    failed:  List[str]  = []

    for i, ticker in enumerate(tickers, 1):
        df = _fetch_candles(ticker, from_date, to_date)

        if df is not None and len(df) >= 20:
            ind = _indicators(ticker, df)
            if ind:
                results.append(ind)
                logger.info(
                    f"  [{i:>3}/{len(tickers)}] ✓ {ticker:<22} "
                    f"₹{ind['current_price']:>9,.2f}  "
                    f"RSI={ind['rsi']:>5.1f}  "
                    f"1M={ind['one_month_return']:>+6.1f}%"
                )
                time.sleep(0.2)
                continue

        failed.append(ticker)
        logger.debug(f"  [{i:>3}/{len(tickers)}] ✗ {ticker}")
        time.sleep(0.2)

    logger.info(
        f"Done — {len(results)} succeeded, {len(failed)} failed  "
        f"({len(failed)} tickers had no data)"
    )
    return results


# ── TOPSIS ─────────────────────────────────────────────────────────────────

def apply_topsis(stocks: List[Dict], n_candidates: int = 15) -> List[Dict]:
    if not stocks:
        return []

    df = pd.DataFrame(stocks).copy()
    df["rsi_score"] = (100 - 2 * abs(df["rsi"] - 55)).clip(lower=0)

    criteria = ["one_month_return", "volume_ratio", "trend_score", "rsi_score", "volatility"]
    benefit  = [True, True, True, True, False]
    weights  = np.array([0.30, 0.20, 0.20, 0.15, 0.15])

    matrix = df[criteria].values.astype(float)
    for col in range(matrix.shape[1]):
        m = np.nanmean(matrix[:, col])
        matrix[np.isnan(matrix[:, col]), col] = m if not np.isnan(m) else 0

    norms       = np.sqrt((matrix ** 2).sum(axis=0))
    norms[norms == 0] = 1
    nm          = (matrix / norms) * weights
    ideal_best  = np.where(benefit, nm.max(0), nm.min(0))
    ideal_worst = np.where(benefit, nm.min(0), nm.max(0))
    d_best      = np.sqrt(((nm - ideal_best)  ** 2).sum(axis=1))
    d_worst     = np.sqrt(((nm - ideal_worst) ** 2).sum(axis=1))

    df["topsis_score"] = np.round(d_worst / (d_best + d_worst + 1e-10), 6)

    return (
        df.drop(columns=["rsi_score"])
          .sort_values("topsis_score", ascending=False)
          .head(n_candidates)
          .to_dict("records")
    )