"""Pydantic v2 API schemas. (LLM/OpenAI JSON schemas arrive in Phase 2.)"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SourceKind = Literal[
    "call_transcript", "email_thread", "whatsapp_export", "session_note"
]


class SourceCreate(BaseModel):
    kind: SourceKind
    title: str = Field(min_length=1)
    raw_text: str = Field(min_length=1)
    channel_ts: datetime | None = None
    contact_hint: str | None = None


class SourceCreated(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    title: str
    channel_ts: datetime | None
    contact_hint: str | None
    created_at: datetime


class SourceDetail(SourceOut):
    raw_text: str


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_id: uuid.UUID
    start_char: int
    end_char: int
    quote: str
    is_primary: bool


class CommitmentOut(BaseModel):
    id: uuid.UUID
    direction: str
    contact_id: uuid.UUID | None
    contact_name: str | None
    what: str
    due_at: datetime | None
    due_precision: str
    status: str
    confidence: float
    state: str
    ambiguity_note: str | None
    created_at: datetime
    updated_at: datetime
    last_touch_at: datetime | None
    evidence: list[EvidenceOut]


class ConfirmPayload(BaseModel):
    """Operator edits when confirming a review item. All fields optional."""

    what: str | None = None
    who: str | None = None
    due_at: datetime | None = None
    due_precision: Literal["exact", "day", "week", "vague", "none"] | None = None


class OkResponse(BaseModel):
    ok: bool = True
