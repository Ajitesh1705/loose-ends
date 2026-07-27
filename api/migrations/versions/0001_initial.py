"""initial schema (plan.md §3)

Revision ID: 0001
Revises:
Create Date: 2026-07-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pgvector for Phase 4 dedupe embeddings. gen_random_uuid() is core in PG15.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "sources",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("channel_ts", sa.DateTime(timezone=True)),
        sa.Column("contact_hint", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('call_transcript','email_thread','whatsapp_export','session_note')",
            name="ck_sources_kind",
        ),
    )

    op.create_table(
        "contacts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("display_name", sa.Text, nullable=False),
        sa.Column(
            "aliases",
            postgresql.ARRAY(sa.Text),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("email", sa.Text),
        sa.Column("phone", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "commitments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("direction", sa.String(16), nullable=False),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
        ),
        sa.Column("what", sa.Text, nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("due_precision", sa.String(16), nullable=False, server_default="none"),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("state", sa.String(16), nullable=False, server_default="active"),
        sa.Column("ambiguity_note", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_touch_at", sa.DateTime(timezone=True)),
        sa.Column("prompt_version", sa.String(32)),
        sa.Column("model", sa.String(64)),
        sa.CheckConstraint(
            "direction IN ('i_owe','they_owe')", name="ck_commitments_direction"
        ),
        sa.CheckConstraint(
            "due_precision IN ('exact','day','week','vague','none')",
            name="ck_commitments_due_precision",
        ),
        sa.CheckConstraint(
            "status IN ('open','done','dropped','superseded')",
            name="ck_commitments_status",
        ),
        sa.CheckConstraint(
            "state IN ('active','needs_review')", name="ck_commitments_state"
        ),
    )
    op.create_index("ix_commitments_contact_id", "commitments", ["contact_id"])
    op.create_index("ix_commitments_state", "commitments", ["state"])
    op.create_index("ix_commitments_due_at", "commitments", ["due_at"])

    op.create_table(
        "evidence",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "commitment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("commitments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("start_char", sa.Integer, nullable=False),
        sa.Column("end_char", sa.Integer, nullable=False),
        sa.Column("quote", sa.Text, nullable=False),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default="true"),
    )
    op.create_index("ix_evidence_commitment_id", "evidence", ["commitment_id"])
    op.create_index("ix_evidence_source_id", "evidence", ["source_id"])

    op.create_table(
        "merges",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "canonical_commitment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("commitments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("absorbed_commitment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reason", sa.String(48), nullable=False),
        sa.Column("similarity", sa.Float),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "reason IN ('embedding+entity+window','manual','explicit_restatement')",
            name="ck_merges_reason",
        ),
    )
    op.create_index("ix_merges_canonical", "merges", ["canonical_commitment_id"])

    op.create_table(
        "jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('pending','running','done','failed')", name="ck_jobs_status"
        ),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])

    op.create_table(
        "llm_calls",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("prompt_version", sa.String(32)),
        sa.Column("prompt_tokens", sa.Integer),
        sa.Column("completion_tokens", sa.Integer),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("cost_usd", sa.Float),
        sa.Column("cache_hit", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("repaired", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("error", sa.Text),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "llm_cache",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("response", postgresql.JSONB, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("llm_cache")
    op.drop_table("llm_calls")
    op.drop_index("ix_jobs_status", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_merges_canonical", table_name="merges")
    op.drop_table("merges")
    op.drop_index("ix_evidence_source_id", table_name="evidence")
    op.drop_index("ix_evidence_commitment_id", table_name="evidence")
    op.drop_table("evidence")
    op.drop_index("ix_commitments_due_at", table_name="commitments")
    op.drop_index("ix_commitments_state", table_name="commitments")
    op.drop_index("ix_commitments_contact_id", table_name="commitments")
    op.drop_table("commitments")
    op.drop_table("contacts")
    op.drop_table("sources")
