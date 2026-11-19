import logging
from typing import Any

from learning_engine.config import settings
from learning_engine.core.interfaces.engine import BaseEngine
from learning_engine.engines.knowledge.models import KnowledgeResult
from learning_engine.engines.knowledge.reranker import LLMReranker
from learning_engine.infrastructure.vector_store.pgvector import PGVectorStore

logger = logging.getLogger(__name__)

_FINAL_K = 6  # documents handed to the response


class KnowledgeEngine(BaseEngine):
    """RAG engine using PGVector. Opens a short session per retrieval so the DB
    connection is not held across the LLM-heavy nodes. When enabled, retrieval
    is hybrid (dense + lexical, RRF-fused) followed by an LLM reranker; both are
    feature-flagged and degrade to pure vector search on any failure."""

    def __init__(self, session_factory, llm=None, model: str = "gpt-4o-mini"):
        self._sf = session_factory
        self.reranker = LLMReranker(llm, model) if llm is not None else None

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
                if settings.use_hybrid_search:
                    # Over-fetch a recall-oriented pool for the reranker to refine.
                    candidates = await store.search_hybrid(
                        message, embedding, top_k=_FINAL_K * 3
                    )
                else:
                    candidates = await store.search_by_embedding(embedding, top_k=_FINAL_K)

            # Rerank OUTSIDE the DB session so the LLM call never holds the connection.
            if settings.use_reranker and self.reranker and len(candidates) > _FINAL_K:
                documents = await self.reranker.rerank(message, candidates, top_k=_FINAL_K)
            else:
                documents = candidates[:_FINAL_K]
            result = KnowledgeResult(documents=documents, query_used=message)
        except Exception:
            logger.exception("Knowledge retrieval failed")
            result = KnowledgeResult(query_used=message)

        updates["knowledge"] = result
        return updates
