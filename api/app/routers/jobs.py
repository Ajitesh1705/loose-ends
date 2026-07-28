"""Drain the job queue over HTTP — the worker loop without an always-on process.

Serverless hosting (Vercel) has nowhere to run `app.worker.main()`, so the queue is
drained on demand instead: the web app calls this right after an ingest, and a daily
cron sweeps anything left behind. Under docker compose the polling worker is still
running and simply wins the race for the job — `run_once` claims with SKIP LOCKED, so
both paths are safe together.
"""

import time

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Job
from app.schemas import DrainResult
from app.worker import run_once

router = APIRouter(tags=["jobs"])

# One extraction is ~2s; stay well inside the 300s function ceiling and leave the
# rest of a large backlog to the next call (the response reports what's left).
MAX_JOBS_PER_CALL = 10
TIME_BUDGET_SECONDS = 240


@router.api_route("/jobs/drain", methods=["POST", "GET"], response_model=DrainResult)
def drain_jobs(db: Session = Depends(get_session)) -> DrainResult:
    started = time.monotonic()
    processed = 0
    while processed < MAX_JOBS_PER_CALL:
        if time.monotonic() - started > TIME_BUDGET_SECONDS:
            break
        if not run_once():  # no pending jobs left
            break
        processed += 1
    pending = db.scalar(
        select(func.count()).select_from(Job).where(Job.status == "pending")
    )
    return DrainResult(processed=processed, pending=pending or 0)
