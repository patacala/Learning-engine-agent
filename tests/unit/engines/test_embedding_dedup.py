"""A turn embeds `current_message` at most once, reused across KnowledgeEngine
(RAG retrieval) and PatternRetriever (behavior-rule scoping) — previously each
called OpenAI's embeddings API independently for the same text. Measured
2026-09-24: each embedding call has the same latency variance as any other
OpenAI call (~200ms-2s), so this was silently doubling that cost every turn
on full_path."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from learning_engine.engines.knowledge.engine import KnowledgeEngine
from learning_engine.engines.knowledge.pattern_retriever import PatternRetriever

AGENT = uuid4()


# --- KnowledgeEngine: computes + surfaces the embedding when state has none ---


@pytest.mark.asyncio
async def test_knowledge_engine_embeds_once_and_surfaces_it_in_state():
    session = MagicMock()

    @asynccontextmanager
    async def fake_factory():
        yield session

    engine = KnowledgeEngine(fake_factory)

    with patch("learning_engine.engines.knowledge.engine.PGVectorStore") as MockStore:
        store = MockStore.return_value
        store.embed = AsyncMock(return_value=[0.1, 0.2, 0.3])
        store.search_hybrid = AsyncMock(return_value=[])

        result = await engine.process({"current_message": "hola", "agent_context": None})

    store.embed.assert_awaited_once_with("hola")
    assert result["message_embedding"] == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_knowledge_engine_reuses_embedding_already_in_state():
    session = MagicMock()

    @asynccontextmanager
    async def fake_factory():
        yield session

    engine = KnowledgeEngine(fake_factory)

    with patch("learning_engine.engines.knowledge.engine.PGVectorStore") as MockStore:
        store = MockStore.return_value
        store.embed = AsyncMock(side_effect=AssertionError("must not re-embed"))
        store.search_hybrid = AsyncMock(return_value=[])

        result = await engine.process({
            "current_message": "hola",
            "agent_context": None,
            "message_embedding": [0.9, 0.9, 0.9],
        })

    store.embed.assert_not_called()
    store.search_hybrid.assert_awaited_once_with("hola", [0.9, 0.9, 0.9], top_k=18)
    # Didn't compute a new one, so it shouldn't re-announce it either.
    assert "message_embedding" not in result


# --- PatternRetriever: skips _embed_message when a precomputed vector is given ---


@pytest.mark.asyncio
async def test_pattern_retriever_reuses_precomputed_embedding():
    @asynccontextmanager
    async def fake_factory():
        yield MagicMock()

    retriever = PatternRetriever(fake_factory)
    retriever._embed_message = AsyncMock(side_effect=AssertionError("must not re-embed"))

    with (
        patch("learning_engine.engines.knowledge.pattern_retriever.SQLPerformanceRepository") as MockPerf,
        patch("learning_engine.engines.knowledge.pattern_retriever.SQLExpressionsRepository") as MockExpr,
        patch("learning_engine.engines.knowledge.pattern_retriever.SQLInsightsRepository") as MockInsights,
    ):
        MockPerf.return_value.list_clusters = AsyncMock(return_value=[])
        MockExpr.return_value.list_by_agent = AsyncMock(return_value=[])
        MockInsights.return_value.behavior_rules = AsyncMock(return_value=[])

        await retriever.retrieve(AGENT, message="hola", message_embedding=[0.1, 0.2, 0.3])

    retriever._embed_message.assert_not_called()
    MockInsights.return_value.behavior_rules.assert_awaited_once_with(
        AGENT, query_embedding=[0.1, 0.2, 0.3]
    )


@pytest.mark.asyncio
async def test_pattern_retriever_embeds_when_none_given():
    """Fast_path never runs KnowledgeEngine, so build_prompt is the first (and
    only) node needing an embedding — this fallback path must still work."""

    @asynccontextmanager
    async def fake_factory():
        yield MagicMock()

    retriever = PatternRetriever(fake_factory)
    retriever._embed_message = AsyncMock(return_value=[0.4, 0.5, 0.6])

    with (
        patch("learning_engine.engines.knowledge.pattern_retriever.SQLPerformanceRepository") as MockPerf,
        patch("learning_engine.engines.knowledge.pattern_retriever.SQLExpressionsRepository") as MockExpr,
        patch("learning_engine.engines.knowledge.pattern_retriever.SQLInsightsRepository") as MockInsights,
    ):
        MockPerf.return_value.list_clusters = AsyncMock(return_value=[])
        MockExpr.return_value.list_by_agent = AsyncMock(return_value=[])
        MockInsights.return_value.behavior_rules = AsyncMock(return_value=[])

        await retriever.retrieve(AGENT, message="hola")

    retriever._embed_message.assert_awaited_once()
