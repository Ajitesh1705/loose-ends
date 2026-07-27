"""Postgres-backed job worker — one polling process. No Redis, no Celery.

Phase 1: the loop exists and claims jobs, but no handlers are registered yet, so it
just marks unknown jobs failed with a clear error. Phase 2 registers the `extract`
handler.
"""

import time
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.db import SessionLocal
from app.models import Job

POLL_SECONDS = 2

# kind -> handler(session, job). Populated by later phases.
HANDLERS: dict = {}


def _claim_one(db) -> Job | None:
    """Atomically claim the oldest pending job (SKIP LOCKED = safe for N workers)."""
    row = db.execute(
        select(Job.id)
        .where(Job.status == "pending")
        .order_by(Job.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).first()
    if row is None:
        return None
    job_id = row[0]
    db.execute(
        update(Job)
        .where(Job.id == job_id)
        .values(status="running", attempts=Job.attempts + 1)
    )
    db.commit()
    return db.get(Job, job_id)


def _run_once() -> bool:
    with SessionLocal() as db:
        job = _claim_one(db)
        if job is None:
            return False
        handler = HANDLERS.get(job.kind)
        try:
            if handler is None:
                raise ValueError(f"no handler for job kind {job.kind!r}")
            handler(db, job)
            job.status = "done"
            job.error = None
        except Exception as exc:  # noqa: BLE001 — worker must not crash on one job
            db.rollback()
            job = db.get(Job, job.id)
            job.status = "failed"
            job.error = str(exc)
            print(f"[worker] job {job.id} ({job.kind}) failed: {exc}")
        job.finished_at = datetime.now(timezone.utc)
        db.commit()
        return True


def main() -> None:
    print("[worker] started, polling every", POLL_SECONDS, "s")
    while True:
        try:
            worked = _run_once()
        except Exception as exc:  # keep the loop alive through transient DB errors
            print(f"[worker] loop error: {exc}")
            worked = False
        if not worked:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
