"""Pure transform: raw extraction candidate -> a commitment ready to persist, OR a
drop. No DB, no network. This is where provenance is enforced and hallucinations are
discarded, so it is unit-tested without touching OpenAI.

Contract:
  - locate the candidate's quote in the source (locate.locate_span). If it cannot be
    located, the candidate is DROPPED as a hallucination.
  - resolve due_raw -> due_at + due_precision against the source's anchor timestamp.
  - the stored `quote` is the located *source substring* (so the UI highlight is exact),
    not the model's paraphrase.
"""

from dataclasses import dataclass
from datetime import datetime

from app.schemas.extraction import ExtractedCommitment
from app.services.dates import resolve_due
from app.services.locate import LocatedSpan, locate_span


@dataclass
class PreparedCommitment:
    direction: str
    what: str
    who: str
    confidence: float
    quote: str
    start_char: int
    end_char: int
    span_method: str
    span_score: float
    due_raw: str | None
    due_at: datetime | None
    due_precision: str
    due_rule: str
    ambiguity_note: str | None


@dataclass
class DroppedCandidate:
    reason: str  # currently only 'unlocatable_quote'
    candidate: ExtractedCommitment


def prepare_commitment(
    *, source_text: str, anchor: datetime, candidate: ExtractedCommitment
) -> PreparedCommitment | DroppedCandidate:
    span: LocatedSpan | None = locate_span(source_text, candidate.quote)
    if span is None:
        return DroppedCandidate(reason="unlocatable_quote", candidate=candidate)

    due = resolve_due(candidate.due_raw, anchor)
    return PreparedCommitment(
        direction=candidate.direction,
        what=candidate.what.strip(),
        who=candidate.who.strip(),
        confidence=candidate.confidence,
        quote=source_text[span.start : span.end],
        start_char=span.start,
        end_char=span.end,
        span_method=span.method,
        span_score=span.score,
        due_raw=candidate.due_raw,
        due_at=due.due_at,
        due_precision=due.precision,
        due_rule=due.rule,
        ambiguity_note=candidate.ambiguity_note,
    )
