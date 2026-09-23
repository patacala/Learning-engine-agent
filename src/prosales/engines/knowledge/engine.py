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
        try:
            async with self._sf() as s:
                documents = await PGVectorStore(s, organization_id=org_id).search(message, top_k=3)
            result = KnowledgeResult(documents=documents, query_used=message)
        except Exception:
            logger.exception("Knowledge retrieval failed")
            result = KnowledgeResult(query_used=message)

        return {"knowledge": result}
