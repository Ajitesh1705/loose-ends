"""Demo-management endpoints. `POST /demo/reset` restores the seeded demo state so a
public link stays reproducible for the next visitor."""

from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Job, Source
from app.schemas import OkResponse
from app.seed import seed

router = APIRouter(tags=["admin"])


@router.post("/demo/reset", response_model=OkResponse)
def reset_demo(db: Session = Depends(get_session)) -> OkResponse:
    """Wipe extracted data, re-seed the fixture sources, and re-enqueue extraction."""
    db.execute(
        text(
            "TRUNCATE sources, contacts, commitments, evidence, merges, jobs "
            "RESTART IDENTITY CASCADE"
        )
    )
    db.commit()
    seed()  # idempotent re-seed of the fixture sources (opens its own session)
    for source_id in db.scalars(select(Source.id)):
        db.add(Job(kind="extract", payload={"source_id": str(source_id)}))
    db.commit()
    return OkResponse()
