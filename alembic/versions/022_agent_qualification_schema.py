"""Per-agent configurable lead-qualification schema.

One row per agent_version holding the ordered list of fields the agent should
capture (JSONB). Additive; existing versions get no row until configured (code
falls back to a default schema). Reversible.

Revision ID: 022
Revises: 021
Create Date: 2026-10-04
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_qualification_schema",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fields", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["agent_version_id"], ["agent_versions.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("agent_version_id"),
    )


def downgrade() -> None:
    op.drop_table("agent_qualification_schema")
