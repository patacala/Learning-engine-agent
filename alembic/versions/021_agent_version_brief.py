"""Store the original brief an agent version's config was generated from.

Nullable free text — existing versions (configured manually, not from a brief)
simply have NULL. Additive and reversible.

Revision ID: 021
Revises: 020
Create Date: 2026-10-04
"""

from alembic import op
import sqlalchemy as sa


revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_versions", sa.Column("brief", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_versions", "brief")
