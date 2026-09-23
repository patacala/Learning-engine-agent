"""Test Playground: saved scenarios for isolated agent testing.

Revision ID: 007
Revises: 006
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "test_scenarios",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_version_id", UUID(as_uuid=True), nullable=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("company_name", sa.String(255), server_default=""),
        sa.Column("documents", JSONB, server_default="[]"),
        sa.Column("quick_facts", JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_test_scenarios_agent_version_id", "test_scenarios", ["agent_version_id"])
    op.create_index("ix_test_scenarios_organization_id", "test_scenarios", ["organization_id"])


def downgrade() -> None:
    op.drop_table("test_scenarios")
