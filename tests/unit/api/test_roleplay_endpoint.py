"""Tests for the roleplay endpoint's training-agent resolution and SSE turn stream."""

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from learning_engine.api.v1.endpoints import roleplay as roleplay_ep
from learning_engine.api.v1.schemas.roleplay import RoleplayTurnRequest
from learning_engine.channels.roleplay.service import RoleplayClosedError, RoleplaySessionNotFound
from learning_engine.core.models.agent import AgentContext


def _training_ctx(version_id):
    return AgentContext(
        organization_id=None,
        organization_name="Cognition",
        org_capabilities=["knowledge", "voice"],
        agent_id=uuid4(),
        agent_version_id=version_id,
        agent_name="Cognition Agent",
        agent_type="sales",
        agent_capabilities=[],
    )


def _factory_yielding(session):
    @asynccontextmanager
    async def factory():
        yield session

    return factory


@pytest.mark.asyncio
async def test_training_agent_resolves_without_api_key():
    target_version = uuid4()
    resolved = _training_ctx(target_version)
    session = MagicMock()

    with patch.object(
        roleplay_ep, "async_session_factory", _factory_yielding(session)
    ), patch.object(
        roleplay_ep, "resolve_published_version", AsyncMock(return_value=resolved)
    ) as mock_resolve:
        ctx = await roleplay_ep._resolve_training_agent(target_version)

    assert ctx.agent_version_id == target_version
    assert ctx.organization_id is None
    mock_resolve.assert_awaited_once()


@pytest.mark.asyncio
async def test_training_agent_404_when_version_not_published():
    session = MagicMock()

    with patch.object(
        roleplay_ep, "async_session_factory", _factory_yielding(session)
    ), patch.object(
        roleplay_ep, "resolve_published_version", AsyncMock(return_value=None)
    ):
        with pytest.raises(HTTPException) as exc:
            await roleplay_ep._resolve_training_agent(uuid4())

    assert exc.value.status_code == 404


async def _drain_frames(response) -> list[dict]:
    frames = []
    async for chunk in response.body_iterator:
        for line in chunk.strip().split("\n"):
            if line.startswith("data: "):
                frames.append(json.loads(line.removeprefix("data: ")))
    return frames


def _stream_patches(turn_result=None, turn_side_effect=None):
    return (
        patch.object(roleplay_ep, "_resolve_context", AsyncMock(return_value=None)),
        patch.object(roleplay_ep, "_resolve_session_agent", AsyncMock(return_value=None)),
        patch.object(roleplay_ep, "get_redis_cache", MagicMock(return_value=None)),
        patch.object(
            roleplay_ep.RoleplayService,
            "turn",
            AsyncMock(return_value=turn_result, side_effect=turn_side_effect),
        ),
    )


@pytest.mark.asyncio
async def test_turn_stream_emits_thinking_then_completed():
    session_id = uuid4()
    p1, p2, p3, p4 = _stream_patches(turn_result="reply text")
    with p1, p2, p3, p4:
        response = await roleplay_ep.take_turn_stream(
            session_id, RoleplayTurnRequest(text="hola")
        )
        frames = await _drain_frames(response)

    assert frames[0] == {"stage": "thinking"}
    assert frames[-1] == {
        "stage": "completed",
        "session_id": str(session_id),
        "reply": "reply text",
    }


@pytest.mark.asyncio
async def test_turn_stream_session_not_found_emits_error_stage():
    session_id = uuid4()
    p1, p2, p3, p4 = _stream_patches(turn_side_effect=RoleplaySessionNotFound())
    with p1, p2, p3, p4:
        response = await roleplay_ep.take_turn_stream(
            session_id, RoleplayTurnRequest(text="hola")
        )
        frames = await _drain_frames(response)

    assert frames[-1]["stage"] == "error"
    assert frames[-1]["code"] == "session_not_found"


@pytest.mark.asyncio
async def test_turn_stream_closed_session_emits_error_stage():
    session_id = uuid4()
    p1, p2, p3, p4 = _stream_patches(turn_side_effect=RoleplayClosedError(str(session_id)))
    with p1, p2, p3, p4:
        response = await roleplay_ep.take_turn_stream(
            session_id, RoleplayTurnRequest(text="hola")
        )
        frames = await _drain_frames(response)

    assert frames[-1]["stage"] == "error"
    assert frames[-1]["code"] == "session_closed"
