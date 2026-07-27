"""Grounded draft generation (plan.md §Phase 7).

Retrieves each evidence quote plus ±400 chars of surrounding source, asks the draft
model for a short, specific follow-up, then runs a deterministic date-hallucination
guard: any date/day in the body that isn't present in the grounding text or the
commitment's own due date triggers one regeneration; if it survives, the draft is
returned flagged rather than silently trusted.
"""

import re
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.llm.client import get_llm_client
from app.models import Commitment, Source
from app.schemas.draft import DraftLLMOut, DraftResponse, GroundingQuote, Tone

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "draft_v1.md"
SYSTEM_PROMPT = _PROMPT_PATH.read_text()

CONTEXT_CHARS = 400

# Month names only count as dates when paired with a day/year, so "deck" (≠ December)
# and a bare "may" don't false-positive.
_MONTHS = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_DATE_PATTERNS = [
    r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b",
    r"\b\d{1,2}(?:st|nd|rd|th)\b",
    r"\b\d{1,2}\s*(?:am|pm)\b",
    r"\b\d{1,2}[:.]\d{2}\s*(?:am|pm)?\b",
    r"\b" + _MONTHS + r"\s+\d{1,2}(?:st|nd|rd|th)?\b",
    r"\b\d{1,2}(?:st|nd|rd|th)?\s+" + _MONTHS + r"\b",
    r"\b" + _MONTHS + r"\s+\d{4}\b",
    r"\b(?:today|tomorrow|tonight|next week|this week|next month|end of (?:week|month))\b",
]


def _grounding_blocks(db: Session, commitment: Commitment) -> list[dict]:
    blocks = []
    for i, e in enumerate(commitment.evidence):
        src = db.get(Source, e.source_id)
        lo = max(0, e.start_char - CONTEXT_CHARS)
        hi = min(len(src.raw_text), e.end_char + CONTEXT_CHARS)
        blocks.append(
            {
                "index": i,
                "evidence_id": e.id,
                "quote": e.quote,
                "context": src.raw_text[lo:hi],
                "source_kind": src.kind,
            }
        )
    return blocks


def _allowed_text(blocks: list[dict], commitment: Commitment) -> str:
    parts = [b["quote"] + " " + b["context"] for b in blocks]
    parts.append(commitment.what)
    due = commitment.due_at
    if isinstance(due, datetime):
        # let the model legitimately reference the real due date in several forms
        parts += [
            due.strftime("%A"),  # weekday
            due.strftime("%B"),  # month
            due.strftime("%B %d"),
            due.strftime("%d"),
            due.date().isoformat(),
        ]
    return " ".join(parts).lower()


def _unsupported_dates(body: str, allowed: str) -> list[str]:
    found: list[str] = []
    low = body.lower()
    for pattern in _DATE_PATTERNS:
        for m in re.findall(pattern, low):
            token = m if isinstance(m, str) else m[0]
            if token and token not in allowed and token not in found:
                found.append(token)
    return found


def _build_user(commitment: Commitment, blocks: list[dict], tone: Tone) -> str:
    who = commitment.contact.display_name if commitment.contact else "the counterparty"
    direction = "you owe them" if commitment.direction == "i_owe" else "they owe you"
    due = commitment.due_at.date().isoformat() if commitment.due_at else "no specific deadline"
    lines = [
        "Commitment to follow up on:",
        f"- what: {commitment.what}",
        f"- direction: {direction}",
        f"- who: {who}",
        f"- due: {due}",
        f"\nTone: {tone}",
        "\nGrounding excerpts:",
    ]
    for b in blocks:
        lines.append(
            f'[{b["index"]}] ({b["source_kind"]}) quote: "{b["quote"]}"\n'
            f'    context: ...{b["context"]}...'
        )
    return "\n".join(lines)


def generate_draft(db: Session, commitment: Commitment, tone: Tone) -> DraftResponse:
    settings = get_settings()
    client = get_llm_client()
    blocks = _grounding_blocks(db, commitment)
    allowed = _allowed_text(blocks, commitment)
    user = _build_user(commitment, blocks, tone)

    out: DraftLLMOut = client.structured(
        kind="draft",
        model=settings.openai_model_draft,
        system=SYSTEM_PROMPT,
        user=user,
        schema=DraftLLMOut,
        temperature=0.4,
    )

    flagged = False
    flag_reason = None
    bad = _unsupported_dates(out.body, allowed)
    if bad:
        # regenerate once, strictly
        strict_user = (
            user
            + "\n\nIMPORTANT: your previous draft mentioned date(s) "
            + f"{bad} that do not appear in the excerpts. Do not mention ANY date or "
            "day that is not present verbatim in the excerpts above."
        )
        out = client.structured(
            kind="draft",
            model=settings.openai_model_draft,
            system=SYSTEM_PROMPT,
            user=strict_user,
            schema=DraftLLMOut,
            temperature=0.2,
        )
        bad = _unsupported_dates(out.body, allowed)
        if bad:
            flagged = True
            flag_reason = (
                f"Draft references date(s) not grounded in the source: {bad}. "
                "Review before sending."
            )

    by_index = {b["index"]: b for b in blocks}
    grounding = [
        GroundingQuote(
            evidence_id=by_index[i]["evidence_id"],
            quote=by_index[i]["quote"],
            source_kind=by_index[i]["source_kind"],
        )
        for i in out.grounding_quote_indices
        if i in by_index
    ]

    return DraftResponse(
        subject=out.subject,
        body=out.body,
        tone=tone,
        word_count=len(out.body.split()),
        grounding=grounding,
        flagged=flagged,
        flag_reason=flag_reason,
    )
