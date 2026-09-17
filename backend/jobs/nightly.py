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
    lookback_days: int | None = None,
    full: bool = False,
    skip_rank: bool = False,
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
            from data.yahoo_daily import ingest_daily_yahoo
            written, failed = ingest_daily_yahoo(db, tickers, lookback_days=lookback_days, full=full)
        else:
            from data.upstox_daily import ingest_daily
            written, failed = ingest_daily(db, tickers, lookback_days=lookback_days)
        run.rows = written
        run.detail = f"{len(tickers)} tickers, {len(failed)} failed: {', '.join(failed[:20])}"
        summary.update(tickers=len(tickers), bars_written=written, failed=failed)

    if skip_rank:
        return summary

    with job_run("buyrank") as (db, run):
        run.rows = compute_and_store(db, backfill_days=backfill)
        summary["scores_written"] = run.rows

    # Predictor upkeep: score matured batches against real prices, retrain if stale.
    from quant.predict import retrain_if_due, score_matured
    with job_run("predictor_score") as (db, run):
        scored = score_matured(db)
        run.rows = len(scored)
        summary["batches_scored"] = len(scored)
    with job_run("predictor_retrain") as (db, run):
        status = retrain_if_due(db)
        run.rows = 1 if status.get("retrained") else 0
        run.detail = str(status)[:2000]
        summary["retrain"] = status

    logger.info("Nightly done: %s", {k: v for k, v in summary.items() if k != "failed"})
    return summary


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    p = argparse.ArgumentParser(description="Universe → daily bars → Buy Rank")
    p.add_argument("--source", choices=["upstox", "yahoo"], default="upstox")
    p.add_argument("--backfill", type=int, default=0, help="extra trading days of ranks to store")
    p.add_argument("--limit", type=int, default=None, help="only the first N tickers")
    p.add_argument("--no-universe", action="store_true", help="skip the NSE constituent refresh")
    p.add_argument("--lookback-days", type=int, default=None, help="history to fetch for new tickers (default HISTORY_DAYS)")
    p.add_argument("--full", action="store_true", help="re-fetch --lookback-days for every ticker (yahoo only)")
    p.add_argument("--skip-rank", action="store_true", help="ingest only")
    a = p.parse_args()
    run_nightly(source=a.source, backfill=a.backfill, limit=a.limit, refresh_universe_first=not a.no_universe,
                lookback_days=a.lookback_days, full=a.full, skip_rank=a.skip_rank)


if __name__ == "__main__":
    main()
