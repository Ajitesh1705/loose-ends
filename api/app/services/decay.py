"""Deterministic decay scoring — pure functions, no DB, no network, no LLM.

"Going cold" is a plain-Python computation, unit-tested and explainable in a tooltip
(plan.md non-negotiable #4). The LLM never decides staleness. Every factor that moves
the score also appends a human-readable line to `explanation`, which the UI renders
verbatim.

Model, in one paragraph: a commitment decays from two independent pressures —
**silence** (how long since anyone touched it) and **the deadline** (approaching, or
past). Silence is measured against a stated cadence if one exists, else against a
21-day ramp. `they_owe` items decay a little faster than `i_owe` because the operator
has to *chase* them — silence there is more likely a thing slipping. Deadline pressure
is dampened by how precise the deadline is: a vague "next week" applies less than an
exact date. Closed commitments (done/dropped/superseded) short-circuit to zero.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Band = Literal["fresh", "warm", "cooling", "cold", "overdue"]

# --- tunables (documented so the model is inspectable) ---
SILENCE_MAX = 70.0  # max points from silence alone
SILENCE_DAYS_TO_MAX = 21.0  # days of silence (no cadence) that reach SILENCE_MAX
THEY_OWE_SILENCE_MULT = 1.2  # chase-factor: things others owe you slip quietly

DUE_APPROACH_MAX = 30.0  # max points as an upcoming deadline nears
DUE_APPROACH_WINDOW = 10.0  # days before due that pressure starts building
OVERDUE_BASE = 35.0  # points the moment something goes overdue
OVERDUE_PER_DAY = 3.0  # additional points per day overdue
DUE_OVERDUE_MAX = 55.0  # cap on overdue points (before precision weighting)

# How much to trust the deadline given how precisely it was stated.
PRECISION_WEIGHT = {"exact": 1.0, "day": 1.0, "week": 0.75, "vague": 0.5, "none": 0.0}

# Score -> band thresholds (non-overdue).
FRESH_BELOW = 20.0
WARM_BELOW = 45.0
COOLING_BELOW = 70.0

_CLOSED = {"done", "dropped", "superseded"}


@dataclass(frozen=True)
class DecayResult:
    score: float  # 0–100, higher = needs attention
    band: Band
    explanation: list[str]


def _days_between(a: datetime, b: datetime) -> float:
    return (a - b).total_seconds() / 86400.0


def _band_from_score(score: float) -> Band:
    if score < FRESH_BELOW:
        return "fresh"
    if score < WARM_BELOW:
        return "warm"
    if score < COOLING_BELOW:
        return "cooling"
    return "cold"


def decay_score(
    *,
    now: datetime,
    due_at: datetime | None,
    due_precision: str,
    last_touch_at: datetime | None,
    direction: str,
    status: str,
    stated_cadence_days: float | None = None,
) -> DecayResult:
    if status in _CLOSED:
        return DecayResult(0.0, "fresh", [f"Marked {status}; no follow-up needed."])

    explanation: list[str] = []

    # --- direction (framing, and the silence chase-factor) ---
    if direction == "they_owe":
        explanation.append("They owe you")
    else:
        explanation.append("You owe them")

    # --- silence pressure ---
    if last_touch_at is None:
        days_silent = 0.0
        explanation.append("No recorded contact yet")
    else:
        days_silent = max(0.0, _days_between(now, last_touch_at))

    if stated_cadence_days:
        ratio = days_silent / stated_cadence_days
        silence = min(SILENCE_MAX, max(0.0, ratio - 1.0) * SILENCE_MAX)
        if ratio > 1.0:
            explanation.append(
                f"Last contact {round(days_silent)}d ago — past the "
                f"~{round(stated_cadence_days)}d cadence"
            )
        else:
            explanation.append(
                f"Last contact {round(days_silent)}d ago — within the "
                f"~{round(stated_cadence_days)}d cadence"
            )
    else:
        silence = min(SILENCE_MAX, (days_silent / SILENCE_DAYS_TO_MAX) * SILENCE_MAX)
        if last_touch_at is not None and days_silent >= 1:
            explanation.append(f"No contact for {round(days_silent)}d")

    if direction == "they_owe":
        silence = min(SILENCE_MAX, silence * THEY_OWE_SILENCE_MULT)

    # --- deadline pressure ---
    prec_w = PRECISION_WEIGHT.get(due_precision, 0.5)
    due_points = 0.0
    overdue = False
    if due_at is not None and due_precision != "none":
        days_to_due = _days_between(due_at, now)
        approx = " (deadline was approximate)" if due_precision in {"week", "vague"} else ""
        if days_to_due < 0:
            overdue = True
            days_over = -days_to_due
            raw = min(DUE_OVERDUE_MAX, OVERDUE_BASE + days_over * OVERDUE_PER_DAY)
            due_points = raw * prec_w
            explanation.append(f"Due {round(days_over)}d ago{approx}")
        elif days_to_due <= DUE_APPROACH_WINDOW:
            raw = ((DUE_APPROACH_WINDOW - days_to_due) / DUE_APPROACH_WINDOW) * DUE_APPROACH_MAX
            due_points = raw * prec_w
            explanation.append(f"Due in {round(days_to_due)}d{approx}")
        else:
            explanation.append(f"Due in {round(days_to_due)}d — plenty of runway")
    else:
        explanation.append("No deadline set")

    score = round(min(100.0, silence + due_points), 1)
    band: Band = "overdue" if overdue else _band_from_score(score)
    return DecayResult(score=score, band=band, explanation=explanation)
