from datetime import datetime, timezone

from app.schemas.extraction import ExtractedCommitment
from app.services.prepare import DroppedCandidate, PreparedCommitment, prepare_commitment

SOURCE = (
    "Me: Yeah I'll get the Q3 audience breakdown over to you before Friday.\n"
    "Priya: Perfect."
)
ANCHOR = datetime(2026, 7, 21, 15, 0, tzinfo=timezone.utc)  # Tuesday


def _candidate(**overrides) -> ExtractedCommitment:
    base = dict(
        direction="i_owe",
        what="Send the Q3 audience breakdown",
        who="Priya Raman",
        due_raw="before Friday",
        confidence=0.86,
        quote="I'll get the Q3 audience breakdown over to you before Friday",
        ambiguity_note=None,
    )
    base.update(overrides)
    return ExtractedCommitment(**base)


def test_locatable_candidate_is_prepared_with_span_and_due():
    result = prepare_commitment(
        source_text=SOURCE, anchor=ANCHOR, candidate=_candidate()
    )
    assert isinstance(result, PreparedCommitment)
    # The stored quote is the exact source substring (for an exact highlight).
    assert SOURCE[result.start_char : result.end_char] == result.quote
    assert "Q3 audience breakdown" in result.quote
    assert result.due_at is not None
    assert result.due_at.weekday() == 4  # Friday
    assert result.due_precision == "day"


def test_unlocatable_quote_is_dropped_as_hallucination():
    """DoD: a commitment whose quote cannot be found in the source is discarded."""
    bad = _candidate(
        quote="I promise to fly you to the moon next quarter"  # not in SOURCE
    )
    result = prepare_commitment(source_text=SOURCE, anchor=ANCHOR, candidate=bad)
    assert isinstance(result, DroppedCandidate)
    assert result.reason == "unlocatable_quote"
