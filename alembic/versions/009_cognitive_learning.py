"""Cognitive Learning Engine: evidence, conversation moves, expressions,
pattern clusters, conversation DNA and agent style profiles.

Revision ID: 009
Revises: 008
Create Date: 2026-08-05
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # messages.turn_index (provenance for live conversations)
    op.add_column("messages", sa.Column("turn_index", sa.Integer, nullable=True))

    # --- Evidence layer ---
    op.create_table(
        "evidence_sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_type", sa.String(30), server_default="expert_transcript"),
        sa.Column("agent_version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("conversation_id", UUID(as_uuid=True), nullable=True),
        sa.Column("training_session_id", UUID(as_uuid=True), nullable=True),
        sa.Column("outcome", sa.String(50), server_default="pending"),
        sa.Column("outcome_score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_evidence_sources_agent_version_id", "evidence_sources", ["agent_version_id"])
    op.create_index("ix_evidence_sources_organization_id", "evidence_sources", ["organization_id"])
    op.create_index("ix_evidence_sources_conversation_id", "evidence_sources", ["conversation_id"])
    op.create_index("ix_evidence_sources_training_session_id", "evidence_sources", ["training_session_id"])
    op.create_index("ix_evidence_sources_outcome", "evidence_sources", ["outcome"])

    op.create_table(
        "evidence_turns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("evidence_source_id", UUID(as_uuid=True), nullable=False),
        sa.Column("turn_index", sa.Integer, nullable=False),
        sa.Column("speaker", sa.String(20)),
        sa.Column("text", sa.Text),
        sa.Column("timestamp", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("evidence_source_id", "turn_index", name="uq_evidence_turn"),
    )
    op.create_index("ix_evidence_turns_evidence_source_id", "evidence_turns", ["evidence_source_id"])

    # --- Conversation Moves ---
    op.create_table(
        "conversation_moves",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("evidence_source_id", UUID(as_uuid=True), nullable=False),
        sa.Column("agent_version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("start_turn_index", sa.Integer, server_default="0"),
        sa.Column("end_turn_index", sa.Integer, server_default="0"),
        sa.Column("move_kind", sa.String(50)),
        sa.Column("goal", sa.Text, server_default=""),
        sa.Column("client_state_before", sa.String(50), server_default=""),
        sa.Column("client_state_after", sa.String(50), server_default=""),
        sa.Column("transcript_excerpt", sa.Text),
        sa.Column("polarity", sa.String(10), server_default="positive"),
        sa.Column("outcome_label", sa.String(50), server_default=""),
        sa.Column("score", sa.Float, server_default="0"),
        sa.Column("confidence", sa.Float, server_default="0.8"),
        sa.Column("human_rating", sa.Float, nullable=True),
        sa.Column("conditions", JSONB, server_default=sa.text("'{}'")),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("cluster_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_conversation_moves_evidence_source_id", "conversation_moves", ["evidence_source_id"])
    op.create_index("ix_conversation_moves_agent_version_id", "conversation_moves", ["agent_version_id"])
    op.create_index("ix_conversation_moves_organization_id", "conversation_moves", ["organization_id"])
    op.create_index("ix_conversation_moves_move_kind", "conversation_moves", ["move_kind"])
    op.create_index("ix_conversation_moves_cluster_id", "conversation_moves", ["cluster_id"])
    op.create_index("ix_conversation_moves_status", "conversation_moves", ["status"])

    # --- Expressions (winning / anti) ---
    op.create_table(
        "expressions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("exact_phrase", sa.Text),
        sa.Column("normalized_phrase", sa.String(500)),
        sa.Column("polarity", sa.String(10), server_default="winning"),
        sa.Column("goal", sa.Text, server_default=""),
        sa.Column("contexts", JSONB, server_default=sa.text("'[]'")),
        sa.Column("stage", sa.String(50), server_default=""),
        sa.Column("times_used", sa.Integer, server_default="1"),
        sa.Column("success_rate", sa.Float, server_default="0"),
        sa.Column("avg_score", sa.Float, server_default="0"),
        sa.Column("conversation_ids", JSONB, server_default=sa.text("'[]'")),
        sa.Column("agent_ids", JSONB, server_default=sa.text("'[]'")),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_expressions_agent_version_id", "expressions", ["agent_version_id"])
    op.create_index("ix_expressions_organization_id", "expressions", ["organization_id"])
    op.create_index("ix_expressions_normalized_phrase", "expressions", ["normalized_phrase"])

    # --- Pattern Clusters ---
    op.create_table(
        "pattern_clusters",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("move_kind", sa.String(50)),
        sa.Column("polarity", sa.String(10), server_default="positive"),
        sa.Column("canonical_excerpt", sa.Text, server_default=""),
        sa.Column("centroid", Vector(1536), nullable=True),
        sa.Column("occurrence_count", sa.Integer, server_default="0"),
        sa.Column("positive_count", sa.Integer, server_default="0"),
        sa.Column("negative_count", sa.Integer, server_default="0"),
        sa.Column("success_rate", sa.Float, server_default="0"),
        sa.Column("avg_score", sa.Float, server_default="0"),
        sa.Column("condition_profile", JSONB, server_default=sa.text("'{}'")),
        sa.Column("rank", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_pattern_clusters_agent_version_id", "pattern_clusters", ["agent_version_id"])
    op.create_index("ix_pattern_clusters_organization_id", "pattern_clusters", ["organization_id"])
    op.create_index("ix_pattern_clusters_move_kind", "pattern_clusters", ["move_kind"])

    # --- Agent Style Profiles ---
    op.create_table(
        "agent_style_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("empathy_level", sa.Float, server_default="0"),
        sa.Column("question_ratio", sa.Float, server_default="0"),
        sa.Column("formality", sa.Float, server_default="0"),
        sa.Column("avg_response_length", sa.Float, server_default="0"),
        sa.Column("technical_level", sa.Float, server_default="0"),
        sa.Column("analogy_use", sa.Float, server_default="0"),
        sa.Column("example_use", sa.Float, server_default="0"),
        sa.Column("humor_use", sa.Float, server_default="0"),
        sa.Column("emotional_validation_freq", sa.Float, server_default="0"),
        sa.Column("sales_pressure", sa.Float, server_default="0"),
        sa.Column("confidence_level", sa.Float, server_default="0"),
        sa.Column("microexpressions", JSONB, server_default=sa.text("'[]'")),
        sa.Column("linguistic_style", JSONB, server_default=sa.text("'{}'")),
        sa.Column("computed_from_n_conversations", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_agent_style_profiles_agent_version_id",
        "agent_style_profiles",
        ["agent_version_id"],
        unique=True,
    )
    op.create_index("ix_agent_style_profiles_organization_id", "agent_style_profiles", ["organization_id"])

    # --- Conversation DNA ---
    op.create_table(
        "conversation_dna",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("evidence_source_id", UUID(as_uuid=True), nullable=True),
        sa.Column("conversation_id", UUID(as_uuid=True), nullable=True),
        sa.Column("agent_version_id", UUID(as_uuid=True), nullable=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("trust_score", sa.Float, server_default="0"),
        sa.Column("curiosity_score", sa.Float, server_default="0"),
        sa.Column("empathy_score", sa.Float, server_default="0"),
        sa.Column("urgency_score", sa.Float, server_default="0"),
        sa.Column("storytelling_score", sa.Float, server_default="0"),
        sa.Column("pressure_score", sa.Float, server_default="0"),
        sa.Column("question_count", sa.Integer, server_default="0"),
        sa.Column("objection_count", sa.Integer, server_default="0"),
        sa.Column("objections_resolved", sa.Integer, server_default="0"),
        sa.Column("avg_turn_length", sa.Float, server_default="0"),
        sa.Column("talk_ratio", sa.Float, server_default="0"),
        sa.Column("conversational_balance", sa.Float, server_default="0"),
        sa.Column("dna_vector", Vector(12), nullable=True),
        sa.Column("outcome", sa.String(50), server_default="pending"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_conversation_dna_evidence_source_id", "conversation_dna", ["evidence_source_id"])
    op.create_index("ix_conversation_dna_conversation_id", "conversation_dna", ["conversation_id"])
    op.create_index("ix_conversation_dna_agent_version_id", "conversation_dna", ["agent_version_id"])
    op.create_index("ix_conversation_dna_organization_id", "conversation_dna", ["organization_id"])
    op.create_index("ix_conversation_dna_outcome", "conversation_dna", ["outcome"])


def downgrade() -> None:
    op.drop_table("conversation_dna")
    op.drop_table("agent_style_profiles")
    op.drop_table("pattern_clusters")
    op.drop_table("expressions")
    op.drop_table("conversation_moves")
    op.drop_table("evidence_turns")
    op.drop_table("evidence_sources")
    op.drop_column("messages", "turn_index")
