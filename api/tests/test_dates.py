from datetime import datetime, timedelta, timezone

from app.services.dates import resolve_due

# A Tuesday anchor (matches the seeded Northwind call).
ANCHOR = datetime(2026, 7, 21, 15, 0, tzinfo=timezone.utc)
assert ANCHOR.weekday() == 1, "test anchor should be a Tuesday"


def _delta_days(dt) -> int:
    return (dt.date() - ANCHOR.date()).days


def test_none_and_empty():
    assert resolve_due(None, ANCHOR).precision == "none"
    assert resolve_due(None, ANCHOR).due_at is None
    assert resolve_due("", ANCHOR).precision == "none"


def test_by_friday_this_week():
    r = resolve_due("by Friday", ANCHOR)
    assert r.precision == "day"
    assert r.due_at.weekday() == 4  # Friday
    assert 0 < _delta_days(r.due_at) <= 7


def test_before_friday_strips_preposition():
    assert resolve_due("before Friday", ANCHOR).due_at == resolve_due("Friday", ANCHOR).due_at


def test_tomorrow():
    r = resolve_due("tomorrow evening", ANCHOR)
    assert r.precision == "day"
    assert _delta_days(r.due_at) == 1


def test_next_week_is_friday_of_following_week():
    r = resolve_due("next week", ANCHOR)
    assert r.precision == "week"
    assert r.due_at.weekday() == 4
    assert 7 <= _delta_days(r.due_at) <= 13


def test_early_next_week_is_monday():
    r = resolve_due("early next week", ANCHOR)
    assert r.precision == "week"
    assert r.due_at.weekday() == 0  # Monday


def test_end_of_week():
    r = resolve_due("by end of week", ANCHOR)
    assert r.precision == "week"
    assert r.due_at.weekday() == 4


def test_end_of_month():
    r = resolve_due("end of month", ANCHOR)
    assert r.precision == "week"
    assert r.due_at.month == 7
    assert r.due_at.day == 31


def test_couple_of_days_is_vague():
    r = resolve_due("in a couple of days", ANCHOR)
    assert r.precision == "vague"
    assert _delta_days(r.due_at) == 2


def test_in_n_days():
    r = resolve_due("in 3 days", ANCHOR)
    assert r.precision == "day"
    assert _delta_days(r.due_at) == 3


def test_explicit_date():
    r = resolve_due("July 30", ANCHOR)
    assert r.precision in {"day", "exact"}
    assert r.due_at.month == 7
    assert r.due_at.day == 30


def test_unresolved_phrase_is_vague_with_no_date():
    r = resolve_due("whenever you get a chance", ANCHOR)
    assert r.precision == "vague"
    assert r.due_at is None


def test_due_at_is_end_of_day():
    r = resolve_due("by Friday", ANCHOR)
    assert (r.due_at.hour, r.due_at.minute) == (23, 59)
