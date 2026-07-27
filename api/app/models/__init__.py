"""SQLAlchemy models for every table in plan.md §3.

Enum-ish fields are plain strings with CHECK constraints enforced in the migration
(see migrations/versions/0001_initial.py) — see NOTES.md for why not native enums.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = _pk()
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    channel_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    contact_hint: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    evidence: Mapped[list["Evidence"]] = relationship(back_populates="source")


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = _pk()
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    aliases: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    commitments: Mapped[list["Commitment"]] = relationship(back_populates="contact")


class Commitment(Base):
    __tablename__ = "commitments"

    id: Mapped[uuid.UUID] = _pk()
    direction: Mapped[str] = mapped_column(String(16), nullable=False)  # i_owe|they_owe
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL")
    )
    what: Mapped[str] = mapped_column(Text, nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_precision: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="none"
    )  # exact|day|week|vague|none
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="open"
    )  # open|done|dropped|superseded
    confidence: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="active"
    )  # active|needs_review
    ambiguity_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_touch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(64))

    contact: Mapped["Contact | None"] = relationship(back_populates="commitments")
    evidence: Mapped[list["Evidence"]] = relationship(
        back_populates="commitment", cascade="all, delete-orphan"
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = _pk()
    commitment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    commitment: Mapped["Commitment"] = relationship(back_populates="evidence")
    source: Mapped["Source"] = relationship(back_populates="evidence")


class Merge(Base):
    __tablename__ = "merges"

    id: Mapped[uuid.UUID] = _pk()
    canonical_commitment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False
    )
    absorbed_commitment_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    reason: Mapped[str] = mapped_column(String(48), nullable=False)
    similarity: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = _pk()
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="pending"
    )  # pending|running|done|failed
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LLMCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[uuid.UUID] = _pk()
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # extract|draft|embed
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    cache_hit: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    repaired: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LLMCache(Base):
    __tablename__ = "llm_cache"

    # key = sha256(prompt_version + model + input_text)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    response: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


__all__ = [
    "Source",
    "Contact",
    "Commitment",
    "Evidence",
    "Merge",
    "Job",
    "LLMCall",
    "LLMCache",
]
