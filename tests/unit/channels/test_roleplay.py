"""Tests for the roleplay training channel."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from prosales.channels.roleplay.engine import ClientPersonaResponder
from prosales.channels.roleplay.service import (
    RoleplayClosedError,
    RoleplayOutcomeError,
    RoleplayService,
    learns_from_outcome,
    speaker_for,
)
from prosales.infrastructure.llm.provider import LLMMessage, LLMResponse


# --- speaker_for: real speaker depends on mode -----------------------------


def test_speaker_agent_mode():
    # Cognition = seller (assistant); human = client (user).
    assert speaker_for("user", "agent") == "trainer"
    assert speaker_for("assistant", "agent") == "cognition"


def test_speaker_client_mode():
    # Cognition = client (user); human = seller (assistant).
    assert speaker_for("assistant", "client") == "trainer"
    assert speaker_for("user", "client") == "cognition"


# --- ClientPersonaResponder: stays in character ----------------------------


@pytest.mark.asyncio
async def test_persona_builds_scenario_prompt_and_returns_reply():
    llm = MagicMock()
    llm.complete = AsyncMock(
        return_value=LLMResponse(content="  Está muy caro para mí.  ", model="x")
    )
    responder = ClientPersonaResponder(llm)

    history = [LLMMessage(role="user", content="Hola, ¿cómo está?")]
    reply = await responder.respond(
        scenario="Cliente que cree que está muy caro",
        history=history,
        seller_message="Le tengo una oferta",
    )

    assert reply == "Está muy caro para mí."  # stripped
    sent = llm.complete.call_args.args[0]
    assert sent[0].role == "system"
    assert "muy caro" in sent[0].content  # scenario injected
    assert sent[-1].content == "Le tengo una oferta"  # seller message last


# --- client-mode turn stores SALES roles so learning is correct ------------


@pytest.mark.asyncio
async def test_client_turn_stores_seller_as_agent_role():
    """In client mode the human is the seller → stored as role='assistant'
    (evidence maps assistant→agent), Cognition's client reply → role='user'."""
    conv = MagicMock()
    conv.id = uuid4()
    conv.channel = "roleplay"
    conv.roleplay_mode = "client"
    conv.scenario = "Cliente escéptico con el precio"

    added = []
    repo = MagicMock()
    repo.get_messages = AsyncMock(return_value=[])
    repo.add_message = AsyncMock(side_effect=lambda m: added.append(m) or m)

    @asynccontextmanager
    async def fake_factory():
        session = MagicMock()
        session.begin = _begin_cm
        session.get = AsyncMock(return_value=conv)  # FOR UPDATE row lock
        yield session

    service = RoleplayService()

    with patch.object(service, "_load", AsyncMock(return_value=conv)), patch(
        "prosales.channels.roleplay.service.async_session_factory", fake_factory
    ), patch(
        "prosales.channels.roleplay.service.SQLConversationRepository",
        return_value=repo,
    ), patch(
        "prosales.channels.roleplay.service.create_llm_provider"
    ), patch(
        "prosales.channels.roleplay.service.ClientPersonaResponder"
    ) as mock_responder:
        mock_responder.return_value.respond = AsyncMock(return_value="Sigue caro.")
        reply = await service.turn(conv.id, "Tenemos financiamiento", agent_context=None)

    assert reply == "Sigue caro."
    assert [(m.role, m.content) for m in added] == [
        ("assistant", "Tenemos financiamiento"),  # seller (human) → agent
        ("user", "Sigue caro."),  # client (Cognition) → client
    ]


def _begin_cm():
    @asynccontextmanager
    async def _cm():
        yield None

    return _cm()


# --- guards: closed session + outcome validation ---------------------------


@pytest.mark.asyncio
async def test_turn_rejected_when_session_closed():
    """A turn on a closed session must raise instead of silently not learning."""
    conv = MagicMock()
    conv.id = uuid4()
    conv.channel = "roleplay"
    conv.roleplay_mode = "client"
    conv.is_active = False

    service = RoleplayService()
    with patch.object(service, "_load", AsyncMock(return_value=conv)):
        with pytest.raises(RoleplayClosedError):
            await service.turn(conv.id, "hola", agent_context=None)


@pytest.mark.asyncio
async def test_end_invalid_outcome_raises():
    service = RoleplayService()
    with pytest.raises(RoleplayOutcomeError):
        await service.end(uuid4(), outcome="banana")


@pytest.mark.asyncio
async def test_end_invalid_sub_outcome_raises():
    service = RoleplayService()
    with pytest.raises(RoleplayOutcomeError):
        await service.end(uuid4(), outcome="scheduled", sub_outcome="banana")


@pytest.mark.asyncio
async def test_end_with_sub_outcome_derives_terminal_outcome():
    """sub_outcome overrides outcome via SUB_OUTCOME_TO_OUTCOME and is persisted."""
    conv = MagicMock()
    conv.channel = "roleplay"

    @asynccontextmanager
    async def fake_factory():
        session = MagicMock()
        session.begin = _begin_cm
        session.get = AsyncMock(return_value=conv)
        yield session

    service = RoleplayService()
    with patch(
        "prosales.channels.roleplay.service.async_session_factory", fake_factory
    ):
        conversation_id, effective_outcome = await service.end(
            uuid4(), outcome="open", sub_outcome="objection_handled"
        )

    assert effective_outcome == "scheduled"  # objection_handled → scheduled
    assert conv.outcome == "scheduled"
    assert conv.sub_outcome == "objection_handled"


@pytest.mark.asyncio
async def test_end_without_sub_outcome_keeps_back_compat():
    """No sub_outcome → outcome is used as-is, sub_outcome stays None."""
    conv = MagicMock()
    conv.channel = "roleplay"

    @asynccontextmanager
    async def fake_factory():
        session = MagicMock()
        session.begin = _begin_cm
        session.get = AsyncMock(return_value=conv)
        yield session

    service = RoleplayService()
    with patch(
        "prosales.channels.roleplay.service.async_session_factory", fake_factory
    ):
        conversation_id, effective_outcome = await service.end(
            uuid4(), outcome="lost"
        )

    assert effective_outcome == "lost"
    assert conv.outcome == "lost"
    assert conv.sub_outcome is None


def test_learns_only_from_terminal_outcomes():
    # Terminal outcomes drive learning; non-terminal ones close but don't learn.
    assert learns_from_outcome("scheduled") is True
    assert learns_from_outcome("lost") is True
    assert learns_from_outcome("abandoned") is True
    assert learns_from_outcome("open") is False
    assert learns_from_outcome("resolved") is False
    assert learns_from_outcome("banana") is False


# --- per-session learned inspection ----------------------------------------


@pytest.mark.asyncio
async def test_session_response_includes_learned_moves():
    """GET /roleplay/sessions/{id} surfaces moves learned from THIS session."""
    from prosales.api.v1.endpoints import roleplay as ep

    session_id = uuid4()

    agent_version_id = uuid4()
    conv = MagicMock()
    conv.id = session_id
    conv.roleplay_mode = "client"
    conv.scenario = "Cliente escéptico"
    conv.outcome = "scheduled"
    conv.sub_outcome = "objection_handled"
    conv.is_active = False
    conv.learned_at = None
    conv.agent_version_id = agent_version_id
    conv.messages = []

    move = MagicMock(
        move_kind="objection_handling",
        polarity="positive",
        transcript_excerpt="Le tengo financiamiento",
        score=0.8,
        status="approved",
    )
    expr = MagicMock(
        exact_phrase="Le tengo financiamiento",
        polarity="positive",
        success_rate=1.0,
        times_used=1,
    )

    @asynccontextmanager
    async def fake_factory():
        yield MagicMock()

    with patch.object(
        ep.RoleplayService, "transcript", AsyncMock(return_value=conv)
    ), patch.object(ep, "async_session_factory", fake_factory), patch.object(
        ep.SQLMovesRepository,
        "list_by_conversation",
        AsyncMock(return_value=[move]),
    ), patch.object(
        ep.SQLExpressionsRepository,
        "list_by_conversation",
        AsyncMock(return_value=[expr]),
    ):
        resp = await ep.get_session(session_id)

    assert resp.agent_version_id == agent_version_id  # scoping is auditable
    assert resp.sub_outcome == "objection_handled"
    assert resp.learned_detail.moves_total == 1
    assert resp.learned_detail.moves_approved == 1
    assert resp.learned_detail.moves[0].move_kind == "objection_handling"
    assert resp.learned_detail.expressions[0].exact_phrase == "Le tengo financiamiento"
