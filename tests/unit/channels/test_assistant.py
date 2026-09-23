"""Tests for the neutral assistant channel."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from prosales.channels.assistant.engine import AssistantResponder
from prosales.channels.assistant.service import (
    AssistantService,
    AssistantSessionNotFound,
)
from prosales.infrastructure.llm.provider import LLMMessage, LLMResponse


# --- AssistantResponder: neutral coach, standard roles ---------------------


@pytest.mark.asyncio
async def test_responder_injects_system_prompt_and_returns_reply():
    llm = MagicMock()
    llm.complete = AsyncMock(
        return_value=LLMResponse(content="  Con gusto, practiquemos.  ", model="x")
    )
    responder = AssistantResponder(llm)

    history = [LLMMessage(role="assistant", content="Hola, ¿en qué te ayudo?")]
    reply = await responder.respond(history, "Quiero mejorar mi cierre")

    assert reply == "Con gusto, practiquemos."  # stripped
    sent = llm.complete.call_args.args[0]
    assert sent[0].role == "system"
    assert "coach" in sent[0].content.lower()  # neutral coach persona
    assert sent[-1].content == "Quiero mejorar mi cierre"  # user message last


# --- message(): standard role storage (assistant IS the assistant) ---------


@pytest.mark.asyncio
async def test_message_stores_user_then_assistant_roles():
    conv = MagicMock()
    conv.id = uuid4()
    conv.channel = "assistant"

    added = []
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=conv)
    repo.get_messages = AsyncMock(return_value=[])
    repo.add_message = AsyncMock(side_effect=lambda m: added.append(m) or m)

    @asynccontextmanager
    async def fake_factory():
        session = MagicMock()
        session.begin = _begin_cm
        yield session

    service = AssistantService()

    with patch(
        "prosales.channels.assistant.service.async_session_factory", fake_factory
    ), patch(
        "prosales.channels.assistant.service.SQLConversationRepository",
        return_value=repo,
    ), patch(
        "prosales.channels.assistant.service.create_llm_provider"
    ), patch(
        "prosales.channels.assistant.service.AssistantResponder"
    ) as mock_responder:
        mock_responder.return_value.respond = AsyncMock(return_value="Vamos a ello.")
        reply = await service.message(conv.id, "Ayúdame con objeciones", agent_context=None)

    assert reply == "Vamos a ello."
    assert [(m.role, m.content) for m in added] == [
        ("user", "Ayúdame con objeciones"),
        ("assistant", "Vamos a ello."),
    ]


@pytest.mark.asyncio
async def test_message_unknown_session_raises():
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=None)

    @asynccontextmanager
    async def fake_factory():
        session = MagicMock()
        session.begin = _begin_cm
        yield session

    service = AssistantService()

    with patch(
        "prosales.channels.assistant.service.async_session_factory", fake_factory
    ), patch(
        "prosales.channels.assistant.service.SQLConversationRepository",
        return_value=repo,
    ):
        with pytest.raises(AssistantSessionNotFound):
            await service.message(uuid4(), "hola", agent_context=None)


@pytest.mark.asyncio
async def test_message_rejects_non_assistant_channel():
    conv = MagicMock()
    conv.channel = "roleplay"
    repo = MagicMock()
    repo.get_by_id = AsyncMock(return_value=conv)

    @asynccontextmanager
    async def fake_factory():
        session = MagicMock()
        session.begin = _begin_cm
        yield session

    service = AssistantService()

    with patch(
        "prosales.channels.assistant.service.async_session_factory", fake_factory
    ), patch(
        "prosales.channels.assistant.service.SQLConversationRepository",
        return_value=repo,
    ):
        with pytest.raises(AssistantSessionNotFound):
            await service.message(uuid4(), "hola", agent_context=None)


def _begin_cm():
    @asynccontextmanager
    async def _cm():
        yield None

    return _cm()
