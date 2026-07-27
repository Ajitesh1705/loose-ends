from app.llm.draft import _unsupported_dates


def test_date_present_in_source_is_allowed():
    allowed = "i'll send the deck by thursday before friday".lower()
    assert _unsupported_dates("I'll get it to you by Thursday.", allowed) == []


def test_invented_date_is_flagged():
    allowed = "i'll send the deck by thursday".lower()
    bad = _unsupported_dates("I'll have it to you by Monday, January 5th.", allowed)
    assert "monday" in bad
    assert any("january" in b for b in bad)


def test_relative_phrase_present_is_allowed():
    allowed = "get you the brand guidelines by early next week".lower()
    assert _unsupported_dates("Nudge on the brand guidelines due next week.", allowed) == []


def test_no_dates_is_clean():
    assert _unsupported_dates("Just following up on the pricing deck.", "anything") == []
