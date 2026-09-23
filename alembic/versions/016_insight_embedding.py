"""Insights: embedding column for relevance-scoped behavior_rule injection.

Behavior rules were being injected into every prompt unconditionally (all
published rules, every turn). This adds an embedding per rule so retrieval can
rank by similarity to the current message instead, the same pattern already
used for moves/expressions.

Revision ID: 016
Revises: 015
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("insights", sa.Column("embedding", Vector(1536), nullable=True))


def downgrade() -> None:
    op.drop_column("insights", "embedding")
