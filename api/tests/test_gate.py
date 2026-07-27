from app.services.gate import gate

THRESHOLD = 0.75


def _gate(**overrides):
    base = dict(
        confidence=0.9,
        due_precision="day",
        due_raw="by Friday",
        ambiguity_note=None,
        num_candidate_contacts=1,
        threshold=THRESHOLD,
    )
    base.update(overrides)
    return gate(**base)


def test_clean_high_confidence_is_active():
    d = _gate()
    assert d.state == "active"
    assert d.ambiguity_note is None


def test_low_confidence_goes_to_review_with_specific_note():
    d = _gate(confidence=0.5)
    assert d.state == "needs_review"
    assert "50%" in d.ambiguity_note and "75%" in d.ambiguity_note
    assert "low confidence" not in d.ambiguity_note.lower() or "%" in d.ambiguity_note


def test_vague_deadline_goes_to_review_and_quotes_phrase():
    d = _gate(due_precision="vague", due_raw="next week")
    assert d.state == "needs_review"
    assert "next week" in d.ambiguity_note


def test_week_deadline_goes_to_review():
    d = _gate(due_precision="week", due_raw="next week")
    assert d.state == "needs_review"
    assert "next week" in d.ambiguity_note


def test_none_deadline_alone_does_not_trigger_review():
    d = _gate(due_precision="none", due_raw=None)
    assert d.state == "active"


def test_extractor_ambiguity_note_is_preferred():
    note = "Conditional: only if the client approves the budget."
    d = _gate(ambiguity_note=note)
    assert d.state == "needs_review"
    assert note in d.ambiguity_note


def test_two_candidate_contacts_goes_to_review():
    d = _gate(num_candidate_contacts=2)
    assert d.state == "needs_review"
    assert "counterparty" in d.ambiguity_note


def test_combined_triggers_are_all_reported():
    note = "Third party ('my designer') will actually do it."
    d = _gate(confidence=0.4, due_precision="vague", due_raw="soon", ambiguity_note=note)
    assert d.state == "needs_review"
    assert note in d.ambiguity_note
    assert "40%" in d.ambiguity_note
    assert "soon" in d.ambiguity_note
