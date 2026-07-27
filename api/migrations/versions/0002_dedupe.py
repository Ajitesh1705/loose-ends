"""dedupe support: commitment embedding + possible-duplicate pointer

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-27
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Embedding of `what`, for dedupe cosine similarity (text-embedding-3-small = 1536).
    # Deferred from 0001 (it's a Phase 4 concern, not in plan.md §3).
    op.add_column("commitments", sa.Column("what_embedding", Vector(1536)))
    # When a new commitment lands in the 0.65–0.85 "possible duplicate" band, point at
    # the existing commitment it might duplicate so the review UI can diff them.
    op.add_column(
        "commitments",
        sa.Column(
            "possible_duplicate_of",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("commitments.id", ondelete="SET NULL"),
        ),
    )


def downgrade() -> None:
    op.drop_column("commitments", "possible_duplicate_of")
    op.drop_column("commitments", "what_embedding")
