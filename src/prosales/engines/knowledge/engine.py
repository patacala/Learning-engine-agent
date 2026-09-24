import logging
from typing import Any

from prosales.core.interfaces.engine import BaseEngine
from prosales.engines.knowledge.models import KnowledgeResult
from prosales.infrastructure.vector_store.pgvector import PGVectorStore

logger = logging.getLogger(__name__)


class KnowledgeEngine(BaseEngine):
    """RAG engine using PGVector. Opens a short session per retrieval so the DB
    connection is not held across the LLM-heavy nodes."""

    def __init__(self, session_factory):
        self._sf = session_factory

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        message = state["current_message"]
        ctx = state.get("agent_context")

        # Capability gating: knowledge belongs to org
        if ctx and not ctx.has_org_capability("knowledge"):
            return {"knowledge": KnowledgeResult(query_used=message)}

        org_id = ctx.organization_id if ctx else None
        # Reuse an embedding already computed this turn (none yet on full_path —
        # this is typically the first node to need one) instead of re-embedding.
        embedding = state.get("message_embedding")
        updates: dict[str, Any] = {}
        try:
            async with self._sf() as s:
                store = PGVectorStore(s, organization_id=org_id)
                if embedding is None:
                    embedding = await store.embed(message)
                    updates["message_embedding"] = embedding
                documents = await store.search_by_embedding(embedding, top_k=3)
            result = KnowledgeResult(documents=documents, query_used=message)
        except Exception:
            logger.exception("Knowledge retrieval failed")
            result = KnowledgeResult(query_used=message)

        updates["knowledge"] = result
        return updates
