from unittest.mock import AsyncMock

import pytest

from prosales.engines.knowledge.chunker import chunk_document
from prosales.engines.knowledge.contextualizer import contextualize_chunks
from prosales.infrastructure.llm.provider import LLMMessage, LLMResponse


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
async def test_long_document_stores_context_from_each_chunk_section():
    """A long file still gets Anthropic-style context on every chunk. Each
    call sees that chunk's section, not a second copy of the whole file."""
    llm = AsyncMock()
    llm.complete = AsyncMock(
        return_value=LLMResponse(content="Situacion del fragmento.", model="test")
    )
    filler = "nota general del catalogo. " * 2500
    long_content = f"## Alpha\n\nAlpha vale 10.\n\n{filler}\n\n## Beta\n\nBeta vale 20.\n"
    chunks = chunk_document(long_content)
    beta = next(c for c in chunks if "Beta vale 20" in c)

    result = await contextualize_chunks(llm, "Catalogo", long_content, chunks)

    assert llm.complete.await_count == len(chunks)
    assert all(item.startswith("Situacion del fragmento.\n\n") for item in result)
    beta_call = next(
        call for call in llm.complete.await_args_list if "Beta vale 20" in _user_text(call)
    )
    beta_doc = _user_text(beta_call)
    assert "Beta vale 20" in beta_doc
    assert long_content not in beta_doc
    assert beta in result[chunks.index(beta)]


def _user_text(call) -> str:
    messages = call.args[0] if call.args else call.kwargs["messages"]
    user = next(m for m in messages if m.role == "user")
    assert isinstance(user, LLMMessage)
    return user.content


@pytest.mark.asyncio
async def test_contextualize_chunks_falls_back_to_plain_chunk_on_failure():
    llm = AsyncMock()
    llm.complete = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

    result = await contextualize_chunks(llm, "Title", "content", ["chunk one"])

    # Indexing must never fail just because context generation did.
    assert result == ["chunk one"]
