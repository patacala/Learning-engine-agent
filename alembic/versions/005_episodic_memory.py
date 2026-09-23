"""Episodic memory: structured conversation episodes with observable facts.

Revision ID: 005
Revises: 004
Create Date: 2026-07-13
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "episodic_memories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("client_id", UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True),
        # Temporal
        sa.Column("started_at", sa.DateTime, nullable=True),
        sa.Column("closed_at", sa.DateTime, nullable=True),
        sa.Column("duration_seconds", sa.Float, server_default="0.0"),
        sa.Column("message_count", sa.Integer, server_default="0"),
        # Observable facts
        sa.Column("dominant_intent", sa.String(50), server_default=""),
        sa.Column("dominant_sentiment", sa.String(50), server_default=""),
        sa.Column("sentiment_shifts", sa.Integer, server_default="0"),
        sa.Column("final_stage", sa.String(50), server_default=""),
        sa.Column("objections_detected", JSONB, server_default=sa.text("'[]'")),
        sa.Column("strategies_used", JSONB, server_default=sa.text("'[]'")),
        sa.Column("urgency_signals", JSONB, server_default=sa.text("'[]'")),
        sa.Column("risk_signals", JSONB, server_default=sa.text("'[]'")),
        # CRM feedback
        sa.Column("outcome", sa.String(50), server_default="pending"),
        sa.Column("outcome_notes", sa.Text, server_default=""),
        # Embedding
        sa.Column("embedding", Vector(1536), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # Indexes
    op.create_unique_constraint("uq_episodic_memories_conversation_id", "episodic_memories", ["conversation_id"])
    op.create_index("ix_episodic_memories_client_id", "episodic_memories", ["client_id"])
    op.create_index("ix_episodic_memories_organization_id", "episodic_memories", ["organization_id"])
    op.create_index("ix_episodic_memories_outcome", "episodic_memories", ["outcome"])


def downgrade() -> None:
    op.drop_table("episodic_memories")
