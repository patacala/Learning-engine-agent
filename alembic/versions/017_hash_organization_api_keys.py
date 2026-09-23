"""Hash organization API keys at rest.

Revision ID: 017
Revises: 016
Create Date: 2026-09-22
"""

import hashlib

from alembic import op
import sqlalchemy as sa


revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("api_key_hash", sa.String(64), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, api_key FROM organizations")).fetchall()
    for row in rows:
        conn.execute(
            sa.text("UPDATE organizations SET api_key_hash = :hash WHERE id = :id"),
            {"id": row.id, "hash": hashlib.sha256(row.api_key.encode()).hexdigest()},
        )

    op.alter_column("organizations", "api_key_hash", nullable=False)
    op.create_unique_constraint("uq_organizations_api_key_hash", "organizations", ["api_key_hash"])
    op.drop_constraint("organizations_api_key_key", "organizations", type_="unique")
    op.drop_column("organizations", "api_key")


def downgrade() -> None:
    op.add_column("organizations", sa.Column("api_key", sa.String(255), nullable=True))
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id FROM organizations")).fetchall()
    for row in rows:
        conn.execute(
            sa.text("UPDATE organizations SET api_key = :key WHERE id = :id"),
            {"id": row.id, "key": f"unrecoverable-{row.id}"},
        )
    op.alter_column("organizations", "api_key", nullable=False)
    op.create_unique_constraint("organizations_api_key_key", "organizations", ["api_key"])
    op.drop_constraint("uq_organizations_api_key_hash", "organizations", type_="unique")
    op.drop_column("organizations", "api_key_hash")
