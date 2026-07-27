"""Pydantic v2 API schemas. (LLM/OpenAI JSON schemas arrive in Phase 2.)"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
