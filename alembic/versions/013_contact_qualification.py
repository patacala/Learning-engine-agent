"""Per-contact qualification (funnel-agnostic signals for the CRM).

Revision ID: 013
Revises: 012
Create Date: 2026-08-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contact_qualifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("temperature", sa.String(10), server_default="cold"),
        sa.Column("status", sa.String(20), server_default="unqualified"),
        sa.Column("readiness", sa.Float, server_default="0"),
        sa.Column("bant", JSONB, server_default=sa.text("'{}'")),
        sa.Column("signals", JSONB, server_default=sa.text("'{}'")),
        sa.Column("facts", JSONB, server_default=sa.text("'{}'")),
        sa.Column("suggested_transition", sa.String(20), server_default="hold"),
        sa.Column("last_conversation_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_contact_qualifications_client_id", "contact_qualifications", ["client_id"], unique=True
    )
    op.create_index(
        "ix_contact_qualifications_organization_id", "contact_qualifications", ["organization_id"]
    )


def downgrade() -> None:
    op.drop_table("contact_qualifications")
