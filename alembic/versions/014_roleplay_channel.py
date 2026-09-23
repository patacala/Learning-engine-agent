"""Roleplay training channel: scenario-driven conversations that feed learning.

Revision ID: 014
Revises: 013
Create Date: 2026-08-15
"""

from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("channel", sa.String(20), server_default="chat", nullable=False),
    )
    op.add_column("conversations", sa.Column("scenario", sa.Text, nullable=True))
    op.add_column("conversations", sa.Column("roleplay_mode", sa.String(20), nullable=True))
    op.create_index("ix_conversations_channel", "conversations", ["channel"])


def downgrade() -> None:
    op.drop_index("ix_conversations_channel", table_name="conversations")
    op.drop_column("conversations", "roleplay_mode")
    op.drop_column("conversations", "scenario")
    op.drop_column("conversations", "channel")
