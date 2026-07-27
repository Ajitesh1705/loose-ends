from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from app.services.decay import decay_score

NOW = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)


def d(days: float) -> datetime:
    return NOW + timedelta(days=days)


@dataclass
class Case:
    name: str
    kwargs: dict
    expected_band: str


def _mk(
    *,
    due_at=None,
    due_precision="none",
    last_touch_days_ago: float | None = 0.0,
    direction="i_owe",
    status="open",
    stated_cadence_days=None,
):
    return dict(
        now=NOW,
        due_at=due_at,
        due_precision=due_precision,
        last_touch_at=None if last_touch_days_ago is None else d(-last_touch_days_ago),
        direction=direction,
        status=status,
        stated_cadence_days=stated_cadence_days,
    )


CASES = [
    # --- closed short-circuits ---
    Case("done", _mk(status="done"), "fresh"),
    Case("dropped", _mk(status="dropped"), "fresh"),
    Case("superseded", _mk(status="superseded"), "fresh"),
    # --- fresh ---
    Case(
        "far_future_touched_now",
        _mk(due_at=d(30), due_precision="exact", last_touch_days_ago=0),
        "fresh",
    ),
    Case("no_due_touched_now", _mk(last_touch_days_ago=0), "fresh"),
    # --- no due date can still go cold on silence ---
    Case("no_due_silent_25d", _mk(last_touch_days_ago=25), "cold"),
    # --- cooling: mid-range silence, no deadline ---
    Case("no_due_silent_15d", _mk(last_touch_days_ago=15), "cooling"),
    # --- overdue ---
    Case(
        "overdue_exact",
        _mk(due_at=d(-5), due_precision="exact", last_touch_days_ago=5),
        "overdue",
    ),
    Case(
        "overdue_week_precision",
        _mk(due_at=d(-3), due_precision="week", last_touch_days_ago=3),
        "overdue",
    ),
    # --- approaching deadline ---
    Case(
        "due_today",
        _mk(due_at=d(0.3), due_precision="exact", last_touch_days_ago=0),
        "warm",
    ),
    # --- cadence ---
    Case(
        "cadence_within",
        _mk(last_touch_days_ago=3, stated_cadence_days=7),
        "fresh",
    ),
    Case(
        "cadence_exceeded",
        _mk(last_touch_days_ago=20, stated_cadence_days=7),
        "cold",
    ),
]


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_band(case: Case):
    result = decay_score(**case.kwargs)
    assert result.band == case.expected_band, (case.name, result)


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_score_in_range_and_explained(case: Case):
    result = decay_score(**case.kwargs)
    assert 0.0 <= result.score <= 100.0
    assert isinstance(result.explanation, list)
    assert result.explanation and all(isinstance(x, str) for x in result.explanation)


def test_they_owe_decays_faster_than_i_owe():
    common = dict(last_touch_days_ago=10)
    they = decay_score(**_mk(direction="they_owe", **common))
    i = decay_score(**_mk(direction="i_owe", **common))
    assert they.score > i.score


def test_recent_touch_beats_long_silence():
    base = dict(due_at=d(5), due_precision="exact")
    recent = decay_score(**_mk(last_touch_days_ago=0, **base))
    stale = decay_score(**_mk(last_touch_days_ago=20, **base))
    assert recent.score < stale.score


def test_cadence_exceeded_beats_within():
    within = decay_score(**_mk(last_touch_days_ago=3, stated_cadence_days=7))
    exceeded = decay_score(**_mk(last_touch_days_ago=20, stated_cadence_days=7))
    assert exceeded.score > within.score


def test_overdue_precision_damping():
    """A confidently-overdue (exact) item scores higher than a vaguely-overdue one."""
    exact = decay_score(**_mk(due_at=d(-4), due_precision="exact", last_touch_days_ago=1))
    vague = decay_score(**_mk(due_at=d(-4), due_precision="vague", last_touch_days_ago=1))
    assert exact.band == vague.band == "overdue"
    assert exact.score > vague.score


def test_no_recorded_contact_is_explained():
    result = decay_score(**_mk(last_touch_days_ago=None))
    assert any("No recorded contact" in line for line in result.explanation)


def test_done_short_circuit_score_zero():
    result = decay_score(**_mk(status="done", due_at=d(-100), due_precision="exact"))
    assert result.score == 0.0
    assert result.band == "fresh"
