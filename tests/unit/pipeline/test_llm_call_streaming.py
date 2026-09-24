"""create_llm_call_node's streaming branch (state["stream_callback"]) must
produce the exact same `llm_response` a non-streaming call would, just
delivered via callback as it's generated — post_process/store/learn read
`llm_response` either way and must never know which path ran."""

from unittest.mock import AsyncMock

import pytest

from prosales.core.models.execution import PipelineExecution, Versions
from prosales.infrastructure.llm.provider import LLMMessage, LLMResponse
from prosales.pipeline.nodes import create_llm_call_node


class FakeLLM:
    def __init__(self, full_text="Hola, ¿en qué te ayudo?", chunks=None):
        self._full_text = full_text
        self._chunks = chunks or [full_text[:4], full_text[4:]]

    async def complete(self, messages, model=None, **kw):
        return LLMResponse(content=self._full_text, model="gpt-4o", usage={"prompt_tokens": 10, "completion_tokens": 5})

    async def stream(self, messages, model=None, usage_sink=None, **kw):
        if usage_sink is not None:
            usage_sink["model"] = "gpt-4o"
            usage_sink["usage"] = {"prompt_tokens": 10, "completion_tokens": 5}
        for c in self._chunks:
            yield c


def _execution():
    return PipelineExecution(versions=Versions())


@pytest.mark.asyncio
async def test_no_callback_uses_complete_unchanged():
    node = create_llm_call_node(FakeLLM())
    execution = _execution()
    state = {"prompt_messages": [LLMMessage(role="user", content="hola")], "execution": execution}

    result = await node(state)

    assert result["llm_response"] == "Hola, ¿en qué te ayudo?"
    assert execution.llm_calls[-1].model == "gpt-4o"
    assert execution.llm_calls[-1].prompt_tokens == 10


@pytest.mark.asyncio
async def test_with_callback_streams_and_assembles_same_text():
    node = create_llm_call_node(FakeLLM())
    execution = _execution()
    received: list[str] = []

    async def on_token(chunk: str) -> None:
        received.append(chunk)

    state = {
        "prompt_messages": [LLMMessage(role="user", content="hola")],
        "execution": execution,
        "stream_callback": on_token,
    }

    result = await node(state)

    assert result["llm_response"] == "Hola, ¿en qué te ayudo?"
    assert received == ["Hola", ", ¿en qué te ayudo?"]
    assert "".join(received) == result["llm_response"]
    # Usage trace still populated from the streaming path's usage_sink.
    assert execution.llm_calls[-1].model == "gpt-4o"
    assert execution.llm_calls[-1].prompt_tokens == 10


@pytest.mark.asyncio
async def test_no_messages_returns_empty_regardless_of_callback():
    node = create_llm_call_node(FakeLLM())
    on_token = AsyncMock()

    result = await node({"prompt_messages": [], "stream_callback": on_token})

    assert result == {"llm_response": ""}
    on_token.assert_not_called()
