"""Real chunking for Knowledge/RAG: split knowledge_documents into
knowledge_chunks so retrieval returns small, complete, fact-sized units
instead of a single embedding per whole document.

Root cause this fixes: index_document() used to embed a whole document as
ONE vector (one row = one document = one embedding), and ResponsePlanner
truncated retrieved content to 200 chars before handing it to the response
LLM — together these cut business-critical facts (e.g. a Saturday
business-hours line) mid-sentence, causing the LLM to "complete" a fact it
was never fully given. Confirmed live in production: 2/10 runs of the same
factual question produced a fabricated answer.

Clean-slate migration — existing knowledge_documents rows (and their single
whole-document embeddings) are dropped, not backfilled. Confirmed with the
user this data may be deleted; new content is re-uploaded after this lands.

Revision ID: 019
Revises: 018
Create Date: 2026-09-29
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Clean slate: drop all existing knowledge_documents rows (and their
    # single-vector-per-document embeddings) before restructuring. Approved
    # by the user — no backfill/migration of existing content; new content
    # is re-uploaded after this migration lands.
    op.execute("DELETE FROM knowledge_documents")

    # The document row is now purely the "source" record: title/category/
    # full original content/metadata for display and re-chunking. It no
    # longer carries an embedding — that moves to knowledge_chunks below.
    op.drop_column("knowledge_documents", "embedding")

    op.create_table(
        "knowledge_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Denormalized from the parent document at insert time so retrieval
        # can filter by org without a join on the hot path.
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=True,
        ),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_knowledge_chunks_document_id", "knowledge_chunks", ["document_id"]
    )
    op.create_index(
        "ix_knowledge_chunks_organization_id", "knowledge_chunks", ["organization_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_chunks_organization_id", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_document_id", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
    op.add_column("knowledge_documents", sa.Column("embedding", Vector(1536), nullable=True))
