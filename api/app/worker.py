"""Postgres-backed job worker — one polling process. No Redis, no Celery.

`run_once()` claims and runs a single job; it has two drivers. Locally, `main()`
polls it forever (the compose `worker` service). On serverless there is no
always-on process, so `routers/jobs.py` drives the same function over HTTP.
Claiming uses SKIP LOCKED, so both drivers can run at once without double work.
"""

import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update

from app.db import SessionLocal
from app.llm.client import get_llm_client
from app.llm.extract import extract_commitments
from app.models import Job, Source
from app.services.ingest import persist_extraction
from app.services.resolve import resolve_commitment

POLL_SECONDS = 2


def handle_extract(db, job: Job) -> None:
    """Extract commitments, persist them (with provenance), then dedupe/resolve."""
    source_id = job.payload.get("source_id")
    source = db.get(Source, uuid.UUID(source_id)) if source_id else None
    if source is None:
        raise ValueError(f"source {source_id!r} not found")
    result = extract_commitments(source)
    ingest = persist_extraction(db, source, result.commitments)

    client = get_llm_client()
    merged = dup_review = 0
    for commitment in list(ingest.created):
        outcome = resolve_commitment(db, commitment, embed=client.embed)
        if outcome.action == "merged":
            merged += 1
        elif outcome.action == "review_possible_duplicate":
            dup_review += 1

    print(
        f"[worker] extracted source {source_id}: "
        f"{ingest.created_count} kept, {ingest.dropped_count} dropped (hallucinated), "
        f"{ingest.review_count} to review; dedupe: {merged} merged, "
        f"{dup_review} possible-duplicate"
    )


# kind -> handler(session, job).
HANDLERS: dict = {"extract": handle_extract}


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


def run_once() -> bool:
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
            worked = run_once()
        except Exception as exc:  # keep the loop alive through transient DB errors
            print(f"[worker] loop error: {exc}")
            worked = False
        if not worked:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
