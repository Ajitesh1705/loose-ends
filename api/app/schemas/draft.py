"""Draft (Phase 7) schemas: request, the strict LLM output, and the API response."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field

Tone = Literal["warm", "direct", "brief"]


class DraftRequest(BaseModel):
    tone: Tone = "warm"


class DraftLLMOut(BaseModel):
    """Strict structured output from the model."""

    subject: str | None = Field(description="Email subject, or null for a message.")
    body: str
    grounding_quote_indices: list[int] = Field(
        description="Indices of the grounding excerpts actually used."
    )


class GroundingQuote(BaseModel):
    evidence_id: uuid.UUID
    quote: str
    source_kind: str


class DraftResponse(BaseModel):
    subject: str | None
    body: str
    tone: Tone
    word_count: int
    grounding: list[GroundingQuote]
    flagged: bool = False
    flag_reason: str | None = None
