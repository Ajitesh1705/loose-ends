"""Persist an extraction: parsed candidates -> commitments + evidence in the DB.

This is the whole ingest pipeline *except* the OpenAI call itself, so it is fully
testable without a key. The worker's `extract` handler is just:

    candidates = llm_extract(source)      # the only key-gated step
    persist_extraction(db, source, candidates)
    db.commit()

Enforces the plan's key invariant: **a commitment is never stored without at least one
evidence row.** Hallucinated (unlocatable) candidates are dropped and counted.

Does NOT commit — the caller owns the unit of work.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Commitment, Evidence, Source
from app.schemas.extraction import ExtractedCommitment
from app.services.contacts import get_or_create_contact
from app.services.gate import gate
from app.services.prepare import DroppedCandidate, prepare_commitment


@dataclass
class IngestResult:
    created: list[Commitment] = field(default_factory=list)
    dropped: list[DroppedCandidate] = field(default_factory=list)
    review_count: int = 0

    @property
    def created_count(self) -> int:
        return len(self.created)

    @property
    def dropped_count(self) -> int:
        return len(self.dropped)


def persist_extraction(
    db: Session,
    source: Source,
    candidates: list[ExtractedCommitment],
    settings: Settings | None = None,
) -> IngestResult:
    settings = settings or get_settings()
    anchor = source.channel_ts or source.created_at or datetime.now(timezone.utc)
    result = IngestResult()

    for candidate in candidates:
        prepared = prepare_commitment(
            source_text=source.raw_text, anchor=anchor, candidate=candidate
        )
        if isinstance(prepared, DroppedCandidate):
            result.dropped.append(prepared)
            continue

        contact = get_or_create_contact(db, prepared.who, source.contact_hint)
        decision = gate(
            confidence=prepared.confidence,
            due_precision=prepared.due_precision,
            due_raw=prepared.due_raw,
            ambiguity_note=prepared.ambiguity_note,
            num_candidate_contacts=1,
            threshold=settings.confidence_threshold,
        )

        commitment = Commitment(
            direction=prepared.direction,
            contact_id=contact.id,
            what=prepared.what,
            due_at=prepared.due_at,
            due_precision=prepared.due_precision,
            status="open",
            confidence=prepared.confidence,
            state=decision.state,
            ambiguity_note=decision.ambiguity_note,
            last_touch_at=anchor,
            prompt_version=settings.prompt_version,
            model=settings.openai_model_extract,
        )
        db.add(commitment)
        db.flush()  # need commitment.id for the evidence row

        # Invariant: every commitment gets at least one evidence row, here.
        db.add(
            Evidence(
                commitment_id=commitment.id,
                source_id=source.id,
                start_char=prepared.start_char,
                end_char=prepared.end_char,
                quote=prepared.quote,
                is_primary=True,
            )
        )
        db.flush()

        result.created.append(commitment)
        if decision.state == "needs_review":
            result.review_count += 1

    return result
