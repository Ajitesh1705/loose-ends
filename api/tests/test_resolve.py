"""Dedupe unit tests. Embeddings are injected as controlled vectors so the merge
mechanics and banding are deterministic and offline. (Real embeddings are exercised in
the live end-to-end check, not here.)
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.models import Commitment, Contact, Evidence, Merge, Source
from app.services.resolve import resolve_commitment

NOW = datetime(2026, 7, 21, 15, 0, tzinfo=timezone.utc)


def evec(*idx: int) -> list[float]:
    v = [0.0] * 1536
    for i in idx:
        v[i] = 1.0
    return v


def _contact(db) -> Contact:
    c = Contact(display_name="Priya Raman", aliases=[])
    db.add(c)
    db.flush()
    return c


def _source(db, text="src") -> Source:
    s = Source(kind="call_transcript", title="t", raw_text=text, channel_ts=NOW)
    db.add(s)
    db.flush()
    return s


def _commit(db, *, what, contact, source, quote, direction="i_owe", due_at=None,
            due_precision="none", embedding=None, state="active"):
    c = Commitment(
        direction=direction,
        contact_id=contact.id,
        what=what,
        due_at=due_at,
        due_precision=due_precision,
        status="open",
        confidence=1.0,
        state=state,
        last_touch_at=due_at or NOW,
        what_embedding=embedding,
    )
    db.add(c)
    db.flush()
    db.add(
        Evidence(
            commitment_id=c.id,
            source_id=source.id,
            start_char=0,
            end_char=len(quote),
            quote=quote,
            is_primary=True,
        )
    )
    db.flush()
    return c


def _evidence_count(db, commitment_id) -> int:
    return db.scalar(
        select(func.count()).select_from(Evidence).where(
            Evidence.commitment_id == commitment_id
        )
    )


def test_auto_merge_call_plus_confirming_email(db):
    """Tuesday call + Wednesday confirming email about the same promise -> ONE
    commitment with TWO evidence rows and a visible merge trail."""
    contact = _contact(db)
    call = _source(db, "call")
    email = _source(db, "email")

    canonical = _commit(
        db,
        what="Send the Q3 audience breakdown",
        contact=contact,
        source=call,
        quote="I'll get the Q3 audience breakdown over to you before Friday",
        due_at=NOW + timedelta(days=3),
        due_precision="week",
        embedding=evec(0),
    )
    # the confirming email: same promise, more precise date, explicit restatement
    new = _commit(
        db,
        what="Send the Q3 audience breakdown",
        contact=contact,
        source=email,
        quote="As discussed, confirming I'll send the Q3 audience breakdown by Thursday",
        due_at=NOW + timedelta(days=2),
        due_precision="day",
        embedding=None,  # forces the embed path
    )

    outcome = resolve_commitment(db, new, embed=lambda _t: evec(0))

    assert outcome.action == "merged"
    assert outcome.canonical_id == canonical.id
    # exactly one commitment remains for this contact
    remaining = db.scalars(
        select(Commitment).where(Commitment.contact_id == contact.id)
    ).all()
    assert len(remaining) == 1 and remaining[0].id == canonical.id
    # two evidence rows now hang off the canonical (call + email)
    assert _evidence_count(db, canonical.id) == 2
    # absorbed row is gone
    assert db.get(Commitment, new.id) is None
    # more precise due_at won
    assert canonical.due_precision == "day"
    assert canonical.due_at == NOW + timedelta(days=2)
    # merge trail recorded, restatement recognised
    merge = db.scalar(
        select(Merge).where(Merge.canonical_commitment_id == canonical.id)
    )
    assert merge is not None
    assert merge.reason == "explicit_restatement"
    assert merge.similarity is not None


def test_distinct_promises_stay_separate(db):
    """Two similar-context but semantically distinct promises to the same person
    remain two commitments."""
    contact = _contact(db)
    s = _source(db)
    _commit(
        db,
        what="Send the Q3 audience breakdown",
        contact=contact,
        source=s,
        quote="I'll send the Q3 audience breakdown",
        embedding=evec(0),
    )
    new = _commit(
        db,
        what="Book the venue for the December offsite",
        contact=contact,
        source=s,
        quote="I'll book the venue for the December offsite",
        embedding=None,
    )
    outcome = resolve_commitment(db, new, embed=lambda _t: evec(500))  # orthogonal

    assert outcome.action == "separate"
    assert db.get(Commitment, new.id) is not None
    assert (
        db.scalar(select(func.count()).select_from(Commitment).where(
            Commitment.contact_id == contact.id)) == 2
    )


def test_mid_band_flags_possible_duplicate(db):
    contact = _contact(db)
    s = _source(db)
    canonical = _commit(
        db,
        what="Send the quarterly revenue report",
        contact=contact,
        source=s,
        quote="I'll send the quarterly revenue report",
        embedding=evec(0),
    )
    new = _commit(
        db,
        what="Send the quarterly audience report",
        contact=contact,
        source=s,
        quote="I'll send the quarterly audience report",  # no restatement marker
        embedding=None,
    )
    outcome = resolve_commitment(db, new, embed=lambda _t: evec(0))  # cosine 1.0

    assert outcome.action == "review_possible_duplicate"
    assert 0.65 <= outcome.score < 0.80
    assert db.get(Commitment, new.id) is not None
    assert new.state == "needs_review"
    assert new.possible_duplicate_of == canonical.id
    assert "Possible duplicate" in new.ambiguity_note


def test_different_direction_is_never_a_candidate(db):
    contact = _contact(db)
    s = _source(db)
    _commit(
        db,
        what="Send the Q3 audience breakdown",
        contact=contact,
        source=s,
        quote="I'll send the Q3 audience breakdown",
        direction="i_owe",
        embedding=evec(0),
    )
    new = _commit(
        db,
        what="Send the Q3 audience breakdown",
        contact=contact,
        source=s,
        quote="you'll send the Q3 audience breakdown",
        direction="they_owe",
        embedding=None,
    )
    outcome = resolve_commitment(db, new, embed=lambda _t: evec(0))
    assert outcome.action == "separate"


def test_out_of_due_window_is_never_a_candidate(db):
    contact = _contact(db)
    s = _source(db)
    _commit(
        db,
        what="Send the Q3 audience breakdown",
        contact=contact,
        source=s,
        quote="I'll send the Q3 audience breakdown",
        due_at=NOW,
        due_precision="day",
        embedding=evec(0),
    )
    new = _commit(
        db,
        what="Send the Q3 audience breakdown",
        contact=contact,
        source=s,
        quote="I'll send the Q3 audience breakdown",
        due_at=NOW + timedelta(days=20),  # >4 days apart
        due_precision="day",
        embedding=None,
    )
    outcome = resolve_commitment(db, new, embed=lambda _t: evec(0))
    assert outcome.action == "separate"
