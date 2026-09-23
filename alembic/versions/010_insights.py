"""Insights layer: generated conclusions + behavior rules from cluster stats.

Revision ID: 010
Revises: 009
Create Date: 2026-08-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "insights",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("insight_text", sa.Text),
        sa.Column("behavior_rule", sa.Text, server_default=""),
        sa.Column("supporting_cluster_ids", JSONB, server_default=sa.text("'[]'")),
        sa.Column("pattern_kinds", JSONB, server_default=sa.text("'[]'")),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("sample_size", sa.Integer, server_default="0"),
        sa.Column("status", sa.String(20), server_default="draft"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_insights_agent_version_id", "insights", ["agent_version_id"])
    op.create_index("ix_insights_organization_id", "insights", ["organization_id"])
    op.create_index("ix_insights_status", "insights", ["status"])


def downgrade() -> None:
    op.drop_table("insights")
