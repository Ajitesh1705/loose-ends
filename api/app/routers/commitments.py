import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_session
from app.models import Commitment
from app.schemas import CommitmentOut, ConfirmPayload, EvidenceOut, OkResponse
from app.services.contacts import get_or_create_contact

router = APIRouter(tags=["commitments"])


def _serialize(c: Commitment) -> CommitmentOut:
    return CommitmentOut(
        id=c.id,
        direction=c.direction,
        contact_id=c.contact_id,
        contact_name=c.contact.display_name if c.contact else None,
        what=c.what,
        due_at=c.due_at,
        due_precision=c.due_precision,
        status=c.status,
        confidence=c.confidence,
        state=c.state,
        ambiguity_note=c.ambiguity_note,
        created_at=c.created_at,
        updated_at=c.updated_at,
        last_touch_at=c.last_touch_at,
        possible_duplicate_of=c.possible_duplicate_of,
        evidence=[EvidenceOut.model_validate(e) for e in c.evidence],
    )


def _load(db: Session, commitment_id: uuid.UUID) -> Commitment:
    c = db.scalar(
        select(Commitment)
        .where(Commitment.id == commitment_id)
        .options(selectinload(Commitment.evidence), selectinload(Commitment.contact))
    )
    if c is None:
        raise HTTPException(status_code=404, detail="commitment not found")
    return c


@router.get("/review", response_model=list[CommitmentOut])
def review_queue(db: Session = Depends(get_session)) -> list[CommitmentOut]:
    """Open commitments awaiting a human decision, oldest first."""
    rows = db.scalars(
        select(Commitment)
        .where(Commitment.state == "needs_review", Commitment.status == "open")
        .options(selectinload(Commitment.evidence), selectinload(Commitment.contact))
        .order_by(Commitment.created_at)
    )
    return [_serialize(c) for c in rows]


@router.post("/commitments/{commitment_id}/confirm", response_model=CommitmentOut)
def confirm(
    commitment_id: uuid.UUID,
    body: ConfirmPayload,
    db: Session = Depends(get_session),
) -> CommitmentOut:
    """Accept a review item into the ledger, applying any operator edits."""
    c = _load(db, commitment_id)
    if body.what is not None:
        c.what = body.what.strip()
    if body.who is not None:
        c.contact_id = get_or_create_contact(db, body.who).id
    if body.due_at is not None:
        c.due_at = body.due_at
        # An operator-picked date is exact unless they said otherwise.
        c.due_precision = body.due_precision or "exact"
    elif body.due_precision is not None:
        c.due_precision = body.due_precision

    c.state = "active"
    c.ambiguity_note = None
    db.commit()
    return _serialize(_load(db, commitment_id))


@router.post("/commitments/{commitment_id}/reject", response_model=OkResponse)
def reject(
    commitment_id: uuid.UUID, db: Session = Depends(get_session)
) -> OkResponse:
    """Drop a review item — it was not a real commitment."""
    c = _load(db, commitment_id)
    c.status = "dropped"
    c.state = "active"  # leave the review queue
    db.commit()
    return OkResponse()
