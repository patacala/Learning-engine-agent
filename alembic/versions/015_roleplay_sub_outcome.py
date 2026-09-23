"""Roleplay: scenario-flavored sub_outcome alongside the terminal Outcome.

Revision ID: 015
Revises: 014
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("sub_outcome", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("conversations", "sub_outcome")
