"""LLMProvider.stream() — additive to complete()/complete_json(), same call
shape, yields text incrementally and reports usage via `usage_sink` (an async
generator can't also return a value the caller reads before it's exhausted)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from prosales.infrastructure.llm.anthropic import AnthropicProvider
from prosales.infrastructure.llm.openai import OpenAIProvider
from prosales.infrastructure.llm.provider import LLMMessage


def _openai_chunk(delta_content=None, usage=None, model="gpt-4o-mini-2024-07-18"):
    choice = SimpleNamespace(delta=SimpleNamespace(content=delta_content)) if delta_content is not None else None
    return SimpleNamespace(
        choices=[choice] if choice else [],
        usage=SimpleNamespace(prompt_tokens=usage[0], completion_tokens=usage[1]) if usage else None,
        model=model,
    )


async def _fake_openai_stream(chunks):
    for c in chunks:
        yield c


@pytest.mark.asyncio
async def test_openai_stream_yields_text_and_reports_usage():
    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=AsyncMock())))
    provider.default_model = "gpt-4o-mini"

    chunks = [
        _openai_chunk(delta_content="Hola"),
        _openai_chunk(delta_content=" mundo"),
        _openai_chunk(delta_content=None, usage=(12, 3)),  # final usage-only chunk, no choices
    ]
    provider.client.chat.completions.create.return_value = _fake_openai_stream(chunks)

    usage_sink: dict = {}
    out = []
    async for piece in provider.stream([LLMMessage(role="user", content="hola")], usage_sink=usage_sink):
        out.append(piece)

    assert "".join(out) == "Hola mundo"
    assert usage_sink["usage"] == {"prompt_tokens": 12, "completion_tokens": 3}
    assert usage_sink["model"] == "gpt-4o-mini-2024-07-18"
    provider.client.chat.completions.create.assert_awaited_once()
    assert provider.client.chat.completions.create.call_args.kwargs["stream"] is True


@pytest.mark.asyncio
async def test_openai_stream_wraps_errors():
    from prosales.core.exceptions import LLMError

    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=AsyncMock(side_effect=RuntimeError("boom"))
    )))
    provider.default_model = "gpt-4o-mini"

    with pytest.raises(LLMError):
        async for _ in provider.stream([LLMMessage(role="user", content="hola")]):
            pass


class _FakeAnthropicStreamCtx:
    """Mimics client.messages.stream(...)'s async context manager."""

    def __init__(self, pieces, final_message):
        self.text_stream = self._gen(pieces)
        self._final = final_message

    @staticmethod
    async def _gen(pieces):
        for p in pieces:
            yield p

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get_final_message(self):
        return self._final


@pytest.mark.asyncio
async def test_anthropic_stream_yields_text_and_reports_usage():
    ctx = _FakeAnthropicStreamCtx(
        pieces=["Hola", " mundo"],
        final_message=SimpleNamespace(
            model="claude-haiku-4-5-20251001",
            usage=SimpleNamespace(input_tokens=10, output_tokens=4),
        ),
    )

    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider.client = SimpleNamespace(messages=SimpleNamespace(stream=lambda **kw: ctx))
    provider.default_model = "claude-sonnet-4-20250514"

    usage_sink: dict = {}
    out = []
    async for piece in provider.stream([LLMMessage(role="user", content="hola")], usage_sink=usage_sink):
        out.append(piece)

    assert "".join(out) == "Hola mundo"
    assert usage_sink["usage"] == {"prompt_tokens": 10, "completion_tokens": 4}
    assert usage_sink["model"] == "claude-haiku-4-5-20251001"
