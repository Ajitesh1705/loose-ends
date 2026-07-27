"""Dedupe / resolve (plan.md §Phase 4) — the hard part.

When a new commitment is created, try to merge it into an existing one for the same
contact. A cheap SQL gate narrows candidates; a weighted score decides the band:

    score = 0.60 * cosine(what embeddings)         # semantics (primary)
          + 0.25 * lemma_overlap(what)             # lexical (secondary)
          + 0.15 if an explicit restatement marker # "as discussed", "confirming"…
    same direction is a HARD requirement (enforced in the gate, not the score)

    score >= 0.80            -> auto-merge
    0.65 <= score < 0.80     -> needs_review as a possible duplicate (diff the quotes)
    score <  0.65            -> separate

The auto-merge floor is 0.80, not the plan's 0.85 — a deliberate, data-driven
recalibration (see NOTES.md). text-embedding-3-small compresses paraphrase similarity:
on the fixtures, a genuine cross-channel restatement scores ~0.82 while the closest
*distinct* same-contact pair scores ~0.43. 0.85 sat above the true positives and missed
them; 0.80 clears them with a ~0.37 margin over the noise floor.

On merge: the EARLIER commitment stays canonical; the new one's evidence is re-pointed
to it (so one commitment is provenanced to a call AND an email — the money shot), the
more precise due_at wins, last_touch_at advances, a `merges` row records the trail, and
the absorbed commitment row is deleted.

The embedder is injected so the merge mechanics are unit-testable without OpenAI.

Merge policy rationale and "what I'd change with real data" live in NOTES.md.
"""

import math
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Callable, Sequence

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import Commitment, Merge, Source
from app.services.lemma import has_restatement_marker, lemma_overlap

W_EMBED = 0.60
W_OVERLAP = 0.25
RESTATEMENT_BONUS = 0.15

AUTO_MERGE = 0.80  # recalibrated for text-embedding-3-small (see module docstring)
REVIEW_LOW = 0.65

DUE_WINDOW_DAYS = 4
CREATED_WINDOW_DAYS = 30

# for "take the more precise due_at"
PRECISION_RANK = {"exact": 4, "day": 3, "week": 2, "vague": 1, "none": 0}

Embedder = Callable[[str], Sequence[float]]


@dataclass
class ResolveOutcome:
    action: str  # 'merged' | 'review_possible_duplicate' | 'separate' | 'skipped'
    score: float | None = None
    similarity: float | None = None  # raw cosine
    canonical_id: uuid.UUID | None = None


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _candidates(db: Session, c: Commitment) -> list[Commitment]:
    if c.contact_id is None:
        return []  # can't gate on an unknown counterparty

    if c.due_at is None:
        due_cond = Commitment.due_at.is_(None)
    else:
        window = timedelta(days=DUE_WINDOW_DAYS)
        due_cond = and_(
            Commitment.due_at.isnot(None),
            Commitment.due_at.between(c.due_at - window, c.due_at + window),
        )

    created_cond = (
        func.abs(func.extract("epoch", Commitment.created_at - c.created_at))
        <= CREATED_WINDOW_DAYS * 86400
    )

    stmt = select(Commitment).where(
        Commitment.id != c.id,
        Commitment.contact_id == c.contact_id,
        Commitment.direction == c.direction,  # same direction: hard requirement
        Commitment.status == "open",
        Commitment.what_embedding.isnot(None),
        due_cond,
        created_cond,
    )
    return list(db.scalars(stmt))


def _score(new_c: Commitment, cand: Commitment, restatement_text: str) -> tuple[float, float]:
    cos = _cosine(new_c.what_embedding, cand.what_embedding)
    overlap = lemma_overlap(new_c.what, cand.what)
    bonus = RESTATEMENT_BONUS if has_restatement_marker(restatement_text) else 0.0
    score = W_EMBED * max(0.0, cos) + W_OVERLAP * overlap + bonus
    return min(1.0, score), cos


def _merge(db: Session, *, canonical: Commitment, absorbed: Commitment, similarity: float,
           restatement: bool) -> None:
    # Re-point the absorbed commitment's evidence onto the canonical one via the ORM
    # relationship: appending to canonical.evidence updates each row's FK and removes it
    # from absorbed.evidence (back_populates), so the delete-orphan cascade below won't
    # take the moved rows with it.
    for evidence in list(absorbed.evidence):
        evidence.is_primary = False
        canonical.evidence.append(evidence)
    # take the more precise due_at
    if PRECISION_RANK.get(absorbed.due_precision, 0) > PRECISION_RANK.get(
        canonical.due_precision, 0
    ):
        canonical.due_at = absorbed.due_at
        canonical.due_precision = absorbed.due_precision
    # advance last_touch to the later communication
    if absorbed.last_touch_at and (
        canonical.last_touch_at is None or absorbed.last_touch_at > canonical.last_touch_at
    ):
        canonical.last_touch_at = absorbed.last_touch_at

    db.add(
        Merge(
            canonical_commitment_id=canonical.id,
            absorbed_commitment_id=absorbed.id,
            reason="explicit_restatement" if restatement else "embedding+entity+window",
            similarity=similarity,
        )
    )
    db.delete(absorbed)
    db.flush()


def resolve_commitment(
    db: Session, commitment: Commitment, *, embed: Embedder
) -> ResolveOutcome:
    """Embed the commitment, then merge / flag / leave it, against existing ones."""
    if commitment.what_embedding is None:
        commitment.what_embedding = list(embed(commitment.what))
        db.flush()

    # A restatement ("as discussed", "confirming") is a property of the *artifact*, and
    # often sits outside the tight promise quote — so scan the quotes AND the source text.
    source_ids = {e.source_id for e in commitment.evidence}
    source_texts = (
        db.scalars(select(Source.raw_text).where(Source.id.in_(source_ids))).all()
        if source_ids
        else []
    )
    restatement_text = " ".join(
        [e.quote for e in commitment.evidence] + list(source_texts)
    )

    candidates = _candidates(db, commitment)
    best: Commitment | None = None
    best_score = -1.0
    best_cos = 0.0
    for cand in candidates:
        score, cos = _score(commitment, cand, restatement_text)
        if score > best_score:
            best, best_score, best_cos = cand, score, cos

    if best is None:
        return ResolveOutcome("separate")

    restatement = has_restatement_marker(restatement_text)

    if best_score >= AUTO_MERGE:
        _merge(db, canonical=best, absorbed=commitment, similarity=best_cos,
               restatement=restatement)
        return ResolveOutcome("merged", best_score, best_cos, best.id)

    if best_score >= REVIEW_LOW:
        note = (
            f'Possible duplicate of an existing commitment: "{best.what}" '
            f"(similarity {best_score:.0%}). Confirm whether to merge."
        )
        commitment.state = "needs_review"
        commitment.possible_duplicate_of = best.id
        commitment.ambiguity_note = (
            f"{commitment.ambiguity_note} {note}".strip()
            if commitment.ambiguity_note
            else note
        )
        db.flush()
        return ResolveOutcome("review_possible_duplicate", best_score, best_cos, best.id)

    return ResolveOutcome("separate", best_score, best_cos)
