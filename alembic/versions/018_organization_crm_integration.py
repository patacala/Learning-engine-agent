"""Per-organization CRM integration credentials (for the /crm/inbound callback).

Revision ID: 018
Revises: 017
Create Date: 2026-09-27
"""

from alembic import op
import sqlalchemy as sa


revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organizations", sa.Column("crm_base_url", sa.String(500), nullable=True))
    op.add_column("organizations", sa.Column("crm_api_key", sa.String(255), nullable=True))
    op.add_column("organizations", sa.Column("crm_agent_id", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("organizations", "crm_agent_id")
    op.drop_column("organizations", "crm_api_key")
    op.drop_column("organizations", "crm_base_url")
