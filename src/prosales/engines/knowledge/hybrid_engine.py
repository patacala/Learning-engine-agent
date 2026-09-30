"""HybridKnowledgeEngine — RAG for the Test Playground.

Merges two retrieval sources for a single test turn:

- permanent: the agent's approved training knowledge (+ shared org documents)
- scenario:  ephemeral business-context documents from the active scenario

The scenario leg takes priority so a saved scenario (e.g. "Audi dealership")
overrides potentially stale business data baked into the agent, while the
agent keeps its selling identity and skills. Nothing is persisted.
"""

import logging
from typing import Any
from uuid import UUID

from prosales.core.interfaces.engine import BaseEngine
from prosales.engines.knowledge.models import KnowledgeResult
from prosales.engines.knowledge.temporary_store import TemporaryVectorStore
from prosales.infrastructure.vector_store.pgvector import PGVectorStore

logger = logging.getLogger(__name__)


class HybridKnowledgeEngine(BaseEngine):
    """Retrieves from permanent + scenario stores, scenario first."""

    def __init__(
        self,
        permanent_store: PGVectorStore,
        temporary_store: TemporaryVectorStore,
        agent_version_id: UUID,
        top_k: int = 6,
    ):
        self.permanent_store = permanent_store
        self.temporary_store = temporary_store
        self.agent_version_id = str(agent_version_id)
        self.top_k = top_k

    async def process(self, state: dict[str, Any]) -> dict[str, Any]:
        message = state["current_message"]

        try:
            query_embedding = await self.permanent_store.embed(message)
        except Exception:
            logger.exception("Failed to embed test query")
            return {"knowledge": KnowledgeResult(query_used=message)}

        scenario_docs = self._tag(
            self.temporary_store.search_by_embedding(query_embedding, top_k=self.top_k),
            source="scenario",
        )

        permanent_docs: list[dict] = []
        try:
            # Unscoped fetch: training documents are stored with
            # organization_id=NULL, so org-scoping would hide them. We fetch a
            # wider slice and filter by agent below.
            raw = await self.permanent_store.search_by_embedding(
                query_embedding, top_k=self.top_k * 5
            )
            permanent_docs = self._tag(self._filter_permanent(raw), source="permanent")
        except Exception:
            logger.exception("Permanent knowledge retrieval failed in test mode")

        # Scenario first (priority), then permanent fills remaining slots.
        merged = scenario_docs + permanent_docs
        merged = merged[: self.top_k]

        return {"knowledge": KnowledgeResult(documents=merged, query_used=message)}

    def _filter_permanent(self, docs: list[dict]) -> list[dict]:
        """Keep shared org docs and this agent's training; drop other agents'."""
        kept: list[dict] = []
        for doc in docs:
            metadata = doc.get("metadata") or {}
            owner = metadata.get("agent_version_id")
            if owner is None or str(owner) == self.agent_version_id:
                kept.append(doc)
            if len(kept) >= self.top_k:
                break
        return kept

    @staticmethod
    def _tag(docs: list[dict], source: str) -> list[dict]:
        return [{**doc, "source": source} for doc in docs]
