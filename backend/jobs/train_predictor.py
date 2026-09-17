"""
Train the beat-the-market predictor and store today's odds.

    python -m jobs.train_predictor

Needs long history in daily_bars first, e.g.
    python -m jobs.nightly --source yahoo --lookback-days 7300 --full --skip-rank
"""

from __future__ import annotations

import json
import logging

from data.db_utils import job_run
from quant.predict import train_and_store

logger = logging.getLogger(__name__)


def run() -> dict:
    with job_run("predictor") as (db, run):
        meta = train_and_store(db)
        run.rows = meta["n_tickers"]
        run.detail = json.dumps(meta["oos"])
    return meta


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    meta = run()
    print(json.dumps({k: meta[k] for k in ("as_of", "history_years", "n_train_rows", "oos")}, indent=2))
    print("folds:")
    for f in meta["folds"]:
        print(f"  {f['year']}: auc {f['auc']:.3f}  acc {f['accuracy']:.3f}  top-decile hit {f['top_decile_hit']:.3f}  excess {f['top_decile_excess_pct']:+.2f}%")


if __name__ == "__main__":
    main()
