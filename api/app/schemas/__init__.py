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
