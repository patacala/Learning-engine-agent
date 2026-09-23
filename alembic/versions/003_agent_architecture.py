"""Agent-centric architecture: organizations, agents, versions.

Revision ID: 003
Revises: 002
Create Date: 2026-07-12
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- 1. Create organizations table (lightweight tenant) ---
    op.create_table(
        "organizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("api_key", sa.String(255), unique=True, nullable=False),
        sa.Column("api_key_prefix", sa.String(8), nullable=False),
        sa.Column("capabilities", JSONB, server_default=sa.text("'[]'")),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # --- 2. Create agents table ---
    op.create_table(
        "agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("agent_type", sa.String(50), nullable=False, server_default="sales"),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # --- 3. Create agent_versions table ---
    op.create_table(
        "agent_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_published", sa.Boolean(), server_default="true"),
        sa.Column("capabilities", JSONB, server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("agent_id", "version_number"),
    )

    # --- 4. Create agent_identity table ---
    op.create_table(
        "agent_identity",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_version_id", UUID(as_uuid=True), sa.ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("communication_style", sa.Text(), server_default=""),
        sa.Column("compliance_notes", sa.Text(), server_default=""),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("agent_version_id"),
    )

    # --- 5. Create agent_personality table ---
    op.create_table(
        "agent_personality",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_version_id", UUID(as_uuid=True), sa.ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("brand_traits", JSONB, server_default=sa.text("'[]'")),
        sa.Column("brand_tone", sa.String(255), server_default="Profesional y cercano"),
        sa.Column("brand_instructions", JSONB, server_default=sa.text("'[]'")),
        sa.Column("voice_traits", JSONB, server_default=sa.text("'[]'")),
        sa.Column("voice_tone", sa.String(255), server_default="Natural y conversacional"),
        sa.Column("voice_instructions", JSONB, server_default=sa.text("'[]'")),
        sa.Column("words_to_avoid", JSONB, server_default=sa.text("'[]'")),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("agent_version_id"),
    )

    # --- 6. Create agent_rules table ---
    op.create_table(
        "agent_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_version_id", UUID(as_uuid=True), sa.ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("intent", sa.String(50), nullable=True),
        sa.Column("sentiment", sa.String(50), nullable=True),
        sa.Column("urgency", sa.String(50), nullable=True),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("action_params", JSONB, server_default=sa.text("'{}'")),
        sa.Column("priority", sa.Integer(), server_default="5"),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("agent_version_id", "rule_id", "version"),
    )

    # --- 7. Create agent_strategies table ---
    op.create_table(
        "agent_strategies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_version_id", UUID(as_uuid=True), sa.ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("strategy_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("triggers", JSONB, server_default=sa.text("'[]'")),
        sa.Column("priority", sa.Integer(), server_default="5"),
        sa.Column("cooldown_seconds", sa.Integer(), server_default="0"),
        sa.Column("enabled", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("agent_version_id", "strategy_type"),
    )

    # --- 8. Create agent_tactics table ---
    op.create_table(
        "agent_tactics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("strategy_id", UUID(as_uuid=True), sa.ForeignKey("agent_strategies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("prompt_instruction", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # --- 9. Create agent_prompt_templates table ---
    op.create_table(
        "agent_prompt_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_version_id", UUID(as_uuid=True), sa.ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("component", sa.String(50), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("agent_version_id", "component", "version"),
    )

    # --- 10. Create agent_voice table ---
    op.create_table(
        "agent_voice",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_version_id", UUID(as_uuid=True), sa.ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("backchannels_es", JSONB, server_default=sa.text("'[\"claro\", \"entiendo\"]'")),
        sa.Column("backchannels_en", JSONB, server_default=sa.text("'[\"I see\", \"sure\"]'")),
        sa.Column("backchannel_probability", sa.Float(), server_default="0.3"),
        sa.Column("enable_ssml", sa.Boolean(), server_default="true"),
        sa.Column("style_adaptations", JSONB, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("agent_version_id"),
    )

    # --- 11. Create organization_agents junction table ---
    op.create_table(
        "organization_agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_version_id", UUID(as_uuid=True), sa.ForeignKey("agent_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default="true"),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "agent_version_id"),
    )

    # --- 12. Replace workspace_id columns with organization_id ---
    # Drop old workspace_id columns
    op.drop_column("clients", "workspace_id")
    op.drop_column("conversations", "workspace_id")
    op.drop_column("knowledge_documents", "workspace_id")
    op.drop_column("events", "workspace_id")

    # Add organization_id columns with FK to organizations
    op.add_column("clients", sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True))
    op.add_column("conversations", sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True))
    op.add_column("knowledge_documents", sa.Column("organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=True))
    op.add_column("events", sa.Column("organization_id", UUID(as_uuid=True), nullable=True))

    op.create_index("ix_clients_organization_id", "clients", ["organization_id"])
    op.create_index("ix_conversations_organization_id", "conversations", ["organization_id"])
    op.create_index("ix_knowledge_documents_organization_id", "knowledge_documents", ["organization_id"])
    op.create_index("ix_events_organization_id", "events", ["organization_id"])

    # --- 13. Drop workspace tables ---
    op.drop_table("workspace_voice")
    op.drop_table("workspace_prompt_templates")
    op.drop_table("workspace_tactics")
    op.drop_table("workspace_strategies")
    op.drop_table("workspace_rules")
    op.drop_table("workspace_personality")
    op.drop_table("workspace_identity")
    op.drop_table("workspaces")


def downgrade() -> None:
    # Recreate workspace tables (from migration 002)
    op.create_table(
        "workspaces",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("api_key", sa.String(255), unique=True, nullable=False),
        sa.Column("api_key_prefix", sa.String(8), nullable=False),
        sa.Column("template", sa.String(50), server_default="custom"),
        sa.Column("capabilities", JSONB, server_default=sa.text("'[]'")),
        sa.Column("is_active", sa.Boolean(), server_default="true"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    # Remove organization_id columns and indexes
    op.drop_index("ix_events_organization_id", "events")
    op.drop_index("ix_knowledge_documents_organization_id", "knowledge_documents")
    op.drop_index("ix_conversations_organization_id", "conversations")
    op.drop_index("ix_clients_organization_id", "clients")
    op.drop_column("events", "organization_id")
    op.drop_column("knowledge_documents", "organization_id")
    op.drop_column("conversations", "organization_id")
    op.drop_column("clients", "organization_id")

    # Re-add workspace_id columns
    op.add_column("clients", sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=True))
    op.add_column("conversations", sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=True))
    op.add_column("knowledge_documents", sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.id"), nullable=True))
    op.add_column("events", sa.Column("workspace_id", UUID(as_uuid=True), nullable=True))

    # Drop new tables in reverse order
    op.drop_table("organization_agents")
    op.drop_table("agent_voice")
    op.drop_table("agent_prompt_templates")
    op.drop_table("agent_tactics")
    op.drop_table("agent_strategies")
    op.drop_table("agent_rules")
    op.drop_table("agent_personality")
    op.drop_table("agent_identity")
    op.drop_table("agent_versions")
    op.drop_table("agents")
    op.drop_table("organizations")
