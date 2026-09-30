"""Per-organization timezone (grounds the LLM's sense of "now" in prompts).

Revision ID: 020
Revises: 019
Create Date: 2026-09-29
"""

from alembic import op
import sqlalchemy as sa


revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "timezone",
            sa.String(64),
            nullable=False,
            server_default="America/New_York",
        ),
    )


def downgrade() -> None:
    op.drop_column("organizations", "timezone")
