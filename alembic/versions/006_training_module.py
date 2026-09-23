"""Training module: sessions and proposals for expert knowledge extraction.

Revision ID: 006
Revises: 005
Create Date: 2026-07-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source_label", sa.String(255), server_default=""),
        sa.Column("transcript", sa.Text, server_default=""),
        sa.Column("source_type", sa.String(50), server_default="text"),
        sa.Column("status", sa.String(50), server_default="processing"),
        sa.Column("patterns_extracted", sa.Integer, server_default="0"),
        sa.Column("patterns_approved", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_index("ix_training_sessions_agent_version_id", "training_sessions", ["agent_version_id"])
    op.create_index("ix_training_sessions_organization_id", "training_sessions", ["organization_id"])

    op.create_table(
        "training_proposals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("agent_version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("pattern_type", sa.String(100), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("raw_excerpt", sa.Text, server_default=""),
        sa.Column("confidence", sa.Float, server_default="0.8"),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("knowledge_document_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_index("ix_training_proposals_session_id", "training_proposals", ["session_id"])
    op.create_index("ix_training_proposals_agent_version_id", "training_proposals", ["agent_version_id"])
    op.create_index("ix_training_proposals_status", "training_proposals", ["status"])


def downgrade() -> None:
    op.drop_table("training_proposals")
    op.drop_table("training_sessions")
