"""Voice calls: track active and completed voice sessions.

Revision ID: 008
Revises: 007
Create Date: 2026-07-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "voice_calls",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", sa.String(255), unique=True, nullable=False),
        sa.Column("provider_type", sa.String(50), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("client_id", UUID(as_uuid=True), nullable=False),
        sa.Column("from_number", sa.String(50), nullable=True),
        sa.Column("to_number", sa.String(50), nullable=True),
        sa.Column("direction", sa.String(20), server_default="inbound"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("started_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime, nullable=True),
        sa.Column("duration_seconds", sa.Integer, nullable=True),
        sa.Column("disconnect_reason", sa.String(100), nullable=True),
        sa.Column("turn_count", sa.Integer, server_default="0"),
        sa.Column("metadata", JSONB, server_default=sa.text("'{}'")),
    )
    op.create_index("ix_voice_calls_session_id", "voice_calls", ["session_id"])
    op.create_index("ix_voice_calls_conversation_id", "voice_calls", ["conversation_id"])
    op.create_index("ix_voice_calls_provider_type", "voice_calls", ["provider_type"])
    op.create_index("ix_voice_calls_organization_id", "voice_calls", ["organization_id"])


def downgrade() -> None:
    op.drop_table("voice_calls")
