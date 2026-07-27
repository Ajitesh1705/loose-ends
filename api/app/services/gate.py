"""Confidence gating (plan.md §Phase 3). Deterministic: decide whether an extracted
commitment lands in the ledger (`active`) or the review queue (`needs_review`), and
carry a *specific* human-readable ambiguity note — never "low confidence".

A commitment goes to review if ANY of:
  - confidence is below the threshold, OR
  - the deadline names no specific day (`due_precision` in {`week`, `vague`}), OR
  - the extractor flagged an ambiguity (conditional, third-party, unclear party…), OR
  - more than one candidate contact could be the counterparty.

(Deviation from plan.md's literal "(vague, none)" list, documented in NOTES.md: the
plan's own example note is about "next week", a week-granularity deadline, so `week`
must be reviewable too. `none` means genuinely no deadline and is NOT a trigger.)

The extractor's own `ambiguity_note` is preferred when present (it's the most specific);
deterministic reasons are appended so the operator sees every trigger.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GateDecision:
    state: str  # 'active' | 'needs_review'
    ambiguity_note: str | None


def gate(
    *,
    confidence: float,
    due_precision: str,
    due_raw: str | None,
    ambiguity_note: str | None,
    num_candidate_contacts: int,
    threshold: float,
) -> GateDecision:
    notes: list[str] = []

    if ambiguity_note and ambiguity_note.strip():
        notes.append(ambiguity_note.strip())

    if confidence < threshold:
        notes.append(
            f"Confidence {confidence:.0%} is below the {threshold:.0%} bar for the ledger."
        )

    if due_precision in ("week", "vague"):
        phrase = f"'{due_raw.strip()}'" if due_raw and due_raw.strip() else "the deadline"
        notes.append(f"{phrase} implies a deadline but names no specific day.")

    if num_candidate_contacts > 1:
        notes.append(
            f"{num_candidate_contacts} people could be the counterparty — confirm who."
        )

    if notes:
        return GateDecision("needs_review", " ".join(notes))
    return GateDecision("active", None)
