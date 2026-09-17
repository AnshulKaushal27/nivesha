"""
Nightly data spine: universe → daily bars → Buy Rank.

    python -m jobs.nightly                      # Upstox, latest day only
    python -m jobs.nightly --source yahoo       # dev fallback, no token needed
    python -m jobs.nightly --backfill 250       # also store 250 earlier days of ranks
    python -m jobs.nightly --limit 60           # first 60 tickers only (quick smoke run)

Each stage is recorded in `ingest_runs`, and a failing stage stops the chain
(no point ranking on stale bars).
"""

from __future__ import annotations

import argparse
import logging

from config import settings
from data.db_utils import job_run
from data.universe import refresh_universe, universe_tickers
from quant.buyrank import compute_and_store

logger = logging.getLogger(__name__)


def run_nightly(
    source: str = "upstox",
    backfill: int = 0,
    limit: int | None = None,
    refresh_universe_first: bool = True,
) -> dict:
    summary: dict = {"source": source}

    if refresh_universe_first:
        try:
            with job_run("universe") as (db, run):
                run.rows = refresh_universe(db)
                run.detail = settings.UNIVERSE_INDEX
        except Exception as exc:                        # noqa: BLE001 — keep going on last snapshot
            logger.warning("Universe refresh failed (%s); using the last stored snapshot", exc)
            summary["universe_error"] = str(exc)

    with job_run(f"ingest_{source}") as (db, run):
        tickers = universe_tickers(db)
        if limit:
            tickers = tickers[:limit]
        if source == "yahoo":
            from data.yahoo_daily import ingest_daily_yahoo as ingest
        else:
            from data.upstox_daily import ingest_daily as ingest
        written, failed = ingest(db, tickers)
        run.rows = written
        run.detail = f"{len(tickers)} tickers, {len(failed)} failed: {', '.join(failed[:20])}"
        summary.update(tickers=len(tickers), bars_written=written, failed=failed)

    with job_run("buyrank") as (db, run):
        run.rows = compute_and_store(db, backfill_days=backfill)
        summary["scores_written"] = run.rows

    logger.info("Nightly done: %s", {k: v for k, v in summary.items() if k != "failed"})
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    p = argparse.ArgumentParser(description="Universe → daily bars → Buy Rank")
    p.add_argument("--source", choices=["upstox", "yahoo"], default="upstox")
    p.add_argument("--backfill", type=int, default=0, help="extra trading days of ranks to store")
    p.add_argument("--limit", type=int, default=None, help="only the first N tickers")
    p.add_argument("--no-universe", action="store_true", help="skip the NSE constituent refresh")
    a = p.parse_args()
    run_nightly(source=a.source, backfill=a.backfill, limit=a.limit, refresh_universe_first=not a.no_universe)


if __name__ == "__main__":
    main()
