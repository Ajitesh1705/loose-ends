import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_session
from app.llm.draft import generate_draft
from app.models import Commitment, Merge
from app.schemas import (
    CommitmentOut,
    ConfirmPayload,
    DecayOut,
    DuplicateInfo,
    EvidenceOut,
    LedgerItem,
    MergeOut,
    OkResponse,
    ReviewItem,
)
from app.schemas.draft import DraftRequest, DraftResponse
from app.services.contacts import get_or_create_contact
from app.services.decay import decay_score

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


def _decay_for(c: Commitment, now: datetime) -> DecayOut:
    result = decay_score(
        now=now,
        due_at=c.due_at,
        due_precision=c.due_precision,
        last_touch_at=c.last_touch_at,
        direction=c.direction,
        status=c.status,
    )
    return DecayOut(score=result.score, band=result.band, explanation=result.explanation)


def _load(db: Session, commitment_id: uuid.UUID) -> Commitment:
    c = db.scalar(
        select(Commitment)
        .where(Commitment.id == commitment_id)
        .options(selectinload(Commitment.evidence), selectinload(Commitment.contact))
    )
    if c is None:
        raise HTTPException(status_code=404, detail="commitment not found")
    return c


@router.get("/commitments", response_model=list[LedgerItem])
def ledger(db: Session = Depends(get_session)) -> list[LedgerItem]:
    """The ledger: active, open commitments with decay band + merge trail, most
    attention-needing first."""
    now = datetime.now(timezone.utc)
    rows = db.scalars(
        select(Commitment)
        .where(Commitment.state == "active", Commitment.status == "open")
        .options(selectinload(Commitment.evidence), selectinload(Commitment.contact))
    ).all()

    items: list[LedgerItem] = []
    for c in rows:
        merges = db.scalars(
            select(Merge).where(Merge.canonical_commitment_id == c.id)
        ).all()
        base = _serialize(c).model_dump()
        items.append(
            LedgerItem(
                **base,
                decay=_decay_for(c, now),
                merges=[MergeOut.model_validate(m) for m in merges],
            )
        )
    items.sort(key=lambda i: i.decay.score, reverse=True)
    return items


@router.get("/review", response_model=list[ReviewItem])
def review_queue(db: Session = Depends(get_session)) -> list[ReviewItem]:
    """Open commitments awaiting a human decision, oldest first."""
    rows = db.scalars(
        select(Commitment)
        .where(Commitment.state == "needs_review", Commitment.status == "open")
        .options(selectinload(Commitment.evidence), selectinload(Commitment.contact))
        .order_by(Commitment.created_at)
    ).all()

    items: list[ReviewItem] = []
    for c in rows:
        dup = None
        if c.possible_duplicate_of:
            other = db.get(Commitment, c.possible_duplicate_of)
            if other:
                primary = next(
                    (e for e in other.evidence if e.is_primary), None
                ) or (other.evidence[0] if other.evidence else None)
                dup = DuplicateInfo(
                    id=other.id, what=other.what, quote=primary.quote if primary else None
                )
        items.append(ReviewItem(**_serialize(c).model_dump(), duplicate_of=dup))
    return items


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


@router.post("/commitments/{commitment_id}/draft", response_model=DraftResponse)
def draft(
    commitment_id: uuid.UUID,
    body: DraftRequest,
    db: Session = Depends(get_session),
) -> DraftResponse:
    """Generate a short, source-grounded follow-up for this commitment."""
    c = _load(db, commitment_id)
    if not c.evidence:
        raise HTTPException(status_code=409, detail="commitment has no evidence to ground a draft")
    return generate_draft(db, c, body.tone)


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
