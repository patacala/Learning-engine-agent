from unittest.mock import AsyncMock

import pytest

from prosales.engines.knowledge.contextualizer import contextualize_chunks
from prosales.infrastructure.llm.provider import LLMResponse


@pytest.mark.asyncio
async def test_contextualize_chunks_prepends_context_per_chunk():
    llm = AsyncMock()
    llm.complete = AsyncMock(
        side_effect=[
            LLMResponse(content="Context A", model="test"),
            LLMResponse(content="Context B", model="test"),
        ]
    )

    result = await contextualize_chunks(
        llm, "Title", "full doc content", ["chunk one", "chunk two"]
    )

    assert result == ["Context A\n\nchunk one", "Context B\n\nchunk two"]
    assert llm.complete.await_count == 2


@pytest.mark.asyncio
async def test_contextualize_chunks_empty_input_returns_empty():
    llm = AsyncMock()
    result = await contextualize_chunks(llm, "Title", "content", [])
    assert result == []
    llm.complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_contextualize_chunks_falls_back_to_plain_chunk_on_failure():
    llm = AsyncMock()
    llm.complete = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

    result = await contextualize_chunks(llm, "Title", "content", ["chunk one"])

    # Indexing must never fail just because context generation did.
    assert result == ["chunk one"]
