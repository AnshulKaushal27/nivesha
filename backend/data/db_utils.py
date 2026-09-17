"""
Small persistence helpers shared by ingestion and ranking jobs.

`upsert_ignore` is dialect-aware: ON CONFLICT DO NOTHING on both SQLite and
Postgres, batched so a 500-stock × 2-year load stays in a handful of statements.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime
from typing import Iterable, Iterator

from sqlalchemy import Table
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from database import IngestRun, SessionLocal, engine

logger = logging.getLogger(__name__)

_BATCH = 2_000


def upsert_ignore(db: Session, table: Table, rows: Iterable[dict]) -> int:
    """Insert rows, silently skipping ones that violate a unique constraint."""
    rows = list(rows)
    if not rows:
        return 0
    dialect = engine.dialect.name
    insert = postgresql.insert if dialect == "postgresql" else sqlite.insert
    pk = list(table.primary_key.columns)[0]
    written = 0
    for start in range(0, len(rows), _BATCH):
        chunk = rows[start:start + _BATCH]
        # RETURNING gives an exact count of rows actually inserted on both
        # dialects; rowcount is unreliable for multi-row ON CONFLICT inserts.
        stmt = insert(table).values(chunk).on_conflict_do_nothing().returning(pk)
        written += len(db.execute(stmt).fetchall())
    return written


def upsert_replace(db: Session, table: Table, rows: Iterable[dict], conflict_cols: list[str]) -> int:
    """Insert or overwrite on conflict. Used for recomputed rows such as factor scores."""
    rows = list(rows)
    if not rows:
        return 0
    dialect = engine.dialect.name
    insert = postgresql.insert if dialect == "postgresql" else sqlite.insert
    written = 0
    for start in range(0, len(rows), _BATCH):
        chunk = rows[start:start + _BATCH]
        stmt = insert(table).values(chunk)
        update_cols = {c: getattr(stmt.excluded, c) for c in chunk[0].keys() if c not in conflict_cols}
        stmt = stmt.on_conflict_do_update(index_elements=conflict_cols, set_=update_cols)
        db.execute(stmt)
        written += len(chunk)
    return written


@contextmanager
def job_run(job: str) -> Iterator[tuple[Session, IngestRun]]:
    """
    Wrap a batch job: opens a session, records an IngestRun row, marks it
    ok/failed on exit. The job updates `run.rows` and `run.detail` itself.
    """
    db = SessionLocal()
    run = IngestRun(job=job)
    db.add(run)
    db.commit()
    try:
        yield db, run
        run.status = "ok"
    except Exception as exc:                      # noqa: BLE001 — recorded, then re-raised
        db.rollback()
        run.status = "failed"
        run.detail = f"{type(exc).__name__}: {exc}"[:2000]
        logger.exception("job %s failed", job)
        raise
    finally:
        run.finished_at = datetime.utcnow()
        db.add(run)
        db.commit()
        db.close()
