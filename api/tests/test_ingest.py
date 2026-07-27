from datetime import datetime, timezone

from sqlalchemy import select

from app.models import Commitment, Evidence, Source
from app.schemas.extraction import ExtractedCommitment
from app.services.ingest import persist_extraction

RAW = (
    "Me: Yeah I'll get the Q3 audience breakdown over to you before Friday.\n"
    "Priya: Great. I'll send the updated brand guidelines next week.\n"
    "Me: Let's find time later to review the funnel."
)


def _source(db) -> Source:
    s = Source(
        kind="call_transcript",
        title="Northwind call",
        raw_text=RAW,
        channel_ts=datetime(2026, 7, 21, 15, 0, tzinfo=timezone.utc),
        contact_hint="Priya Raman",
    )
    db.add(s)
    db.flush()
    return s


def _cand(**o) -> ExtractedCommitment:
    base = dict(
        direction="i_owe",
        what="Send the Q3 audience breakdown",
        who="Priya Raman",
        due_raw="before Friday",
        confidence=0.9,
        quote="I'll get the Q3 audience breakdown over to you before Friday",
        ambiguity_note=None,
    )
    base.update(o)
    return ExtractedCommitment(**base)


def test_persists_commitment_with_evidence_and_resolved_due(db):
    source = _source(db)
    result = persist_extraction(db, source, [_cand()])

    assert result.created_count == 1
    c = result.created[0]
    assert c.due_at is not None and c.due_at.weekday() == 4  # Friday
    assert c.state == "active"

    ev = db.scalars(select(Evidence).where(Evidence.commitment_id == c.id)).all()
    assert len(ev) == 1
    assert RAW[ev[0].start_char : ev[0].end_char] == ev[0].quote


def test_unlocatable_candidate_is_dropped(db):
    source = _source(db)
    bad = _cand(quote="I promise to relocate the office to Mars")
    result = persist_extraction(db, source, [_cand(), bad])
    assert result.created_count == 1
    assert result.dropped_count == 1
    assert result.dropped[0].reason == "unlocatable_quote"


def test_evidence_invariant_every_commitment_has_evidence(db):
    source = _source(db)
    result = persist_extraction(
        db,
        source,
        [
            _cand(),
            _cand(
                direction="they_owe",
                what="Send updated brand guidelines",
                due_raw="next week",
                quote="I'll send the updated brand guidelines next week",
            ),
        ],
    )
    assert result.created_count == 2
    for c in result.created:
        n = db.scalar(
            select(Evidence).where(Evidence.commitment_id == c.id).limit(1)
        )
        assert n is not None, "commitment stored without evidence violates the invariant"


def test_vague_deadline_routes_to_review(db):
    source = _source(db)
    result = persist_extraction(
        db,
        source,
        [
            _cand(
                direction="they_owe",
                what="Send updated brand guidelines",
                due_raw="next week",
                quote="I'll send the updated brand guidelines next week",
            )
        ],
    )
    assert result.review_count == 1
    assert result.created[0].state == "needs_review"
    assert "next week" in result.created[0].ambiguity_note


def test_low_confidence_routes_to_review(db):
    source = _source(db)
    result = persist_extraction(db, source, [_cand(confidence=0.4)])
    assert result.created[0].state == "needs_review"
