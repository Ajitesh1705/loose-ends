import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.models import Job, Source
from app.schemas import SourceCreate, SourceCreated, SourceDetail, SourceOut
from app.services.ratelimit import SlidingWindowLimiter

router = APIRouter(tags=["sources"])

# Public endpoint with a real OpenAI key behind it — throttle per client IP.
_ingest_limiter = SlidingWindowLimiter(get_settings().ingest_rate_limit_per_min)


@router.post("/sources", response_model=SourceCreated, status_code=status.HTTP_201_CREATED)
def create_source(
    body: SourceCreate, request: Request, db: Session = Depends(get_session)
) -> SourceCreated:
    """Create a source and enqueue an `extract` job for the worker to pick up."""
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    if not _ingest_limiter.allow(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"rate limit: max {settings.ingest_rate_limit_per_min} ingests/min",
        )
    if len(body.raw_text) > settings.max_input_chars:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"raw_text exceeds {settings.max_input_chars} chars",
        )
    source = Source(
        kind=body.kind,
        title=body.title,
        raw_text=body.raw_text,
        channel_ts=body.channel_ts,
        contact_hint=body.contact_hint,
    )
    db.add(source)
    db.flush()  # assign source.id before referencing it in the job payload
    job = Job(kind="extract", payload={"source_id": str(source.id)})
    db.add(job)
    db.commit()
    return SourceCreated(id=source.id, job_id=job.id)


@router.get("/sources", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_session)) -> list[Source]:
    return list(db.scalars(select(Source).order_by(Source.created_at.desc())))


@router.get("/sources/{source_id}", response_model=SourceDetail)
def get_source(source_id: uuid.UUID, db: Session = Depends(get_session)) -> Source:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="source not found")
    return source
