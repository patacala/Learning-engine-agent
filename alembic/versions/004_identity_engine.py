"""Identity engine: expand agent_identity, remove words_to_avoid from personality.

Revision ID: 004
Revises: 003
Create Date: 2026-07-13
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new JSONB columns to agent_identity
    op.add_column("agent_identity", sa.Column("principles", JSONB, server_default=sa.text("'[]'")))
    op.add_column("agent_identity", sa.Column("beliefs", JSONB, server_default=sa.text("'[]'")))
    op.add_column("agent_identity", sa.Column("values_list", JSONB, server_default=sa.text("'[]'")))
    op.add_column("agent_identity", sa.Column("words_never_use", JSONB, server_default=sa.text("'[]'")))
    op.add_column("agent_identity", sa.Column("words_prefer", JSONB, server_default=sa.text("'[]'")))

    # Remove words_to_avoid from agent_personality (now lives in identity)
    op.drop_column("agent_personality", "words_to_avoid")


def downgrade() -> None:
    # Re-add words_to_avoid to agent_personality
    op.add_column("agent_personality", sa.Column("words_to_avoid", JSONB, server_default=sa.text("'[]'")))

    # Remove new columns from agent_identity
    op.drop_column("agent_identity", "words_prefer")
    op.drop_column("agent_identity", "words_never_use")
    op.drop_column("agent_identity", "values_list")
    op.drop_column("agent_identity", "beliefs")
    op.drop_column("agent_identity", "principles")
