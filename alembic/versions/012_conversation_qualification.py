"""Conversation qualification: Cognition-inferred outcome + agent link + learned flag.

Revision ID: 012
Revises: 011
Create Date: 2026-08-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("agent_version_id", UUID(as_uuid=True), nullable=True))
    op.add_column("conversations", sa.Column("outcome", sa.String(50), server_default="open"))
    op.add_column("conversations", sa.Column("outcome_confidence", sa.Float, server_default="0"))
    op.add_column("conversations", sa.Column("learned_at", sa.DateTime, nullable=True))
    op.create_index("ix_conversations_agent_version_id", "conversations", ["agent_version_id"])
    op.create_index("ix_conversations_outcome", "conversations", ["outcome"])


def downgrade() -> None:
    op.drop_index("ix_conversations_outcome", table_name="conversations")
    op.drop_index("ix_conversations_agent_version_id", table_name="conversations")
    op.drop_column("conversations", "learned_at")
    op.drop_column("conversations", "outcome_confidence")
    op.drop_column("conversations", "outcome")
    op.drop_column("conversations", "agent_version_id")
