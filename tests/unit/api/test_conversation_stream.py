"""POST /conversation/message/stream — SSE shape: token events as the
callback fires, then one completed event with the same fields /message
returns. The plain-JSON /message endpoint must stay byte-identical to before
(no change to its route, just where the setup code now lives)."""

import json
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from prosales.api.v1.endpoints.conversation import router as conversation_router
from prosales.core.models.agent import AgentContext
from prosales.services.pipeline_runner import PipelineResult

app = FastAPI()
app.include_router(conversation_router, prefix="/api/v1")


def _agent_context():
    return AgentContext(
        organization_id=uuid4(),
        organization_name="Test Org",
        org_capabilities=["knowledge"],
        agent_id=uuid4(),
        agent_version_id=uuid4(),
        agent_name="Sales Bot",
        agent_type="sales",
        agent_capabilities=[],
    )


def _parse_sse(raw: str) -> list[dict]:
    events = []
    for block in raw.strip().split("\n\n"):
        if block.startswith("data: "):
            events.append(json.loads(block[len("data: "):]))
    return events


@pytest.mark.asyncio
async def test_stream_emits_tokens_then_completed():
    ctx = _agent_context()
    client_id, conversation_id = uuid4(), uuid4()

    async def fake_run(*args, on_token=None, **kwargs):
        for chunk in ["Hola", ", ¿en qué", " te ayudo?"]:
            await on_token(chunk)
        return PipelineResult(
            response="Hola, ¿en qué te ayudo?",
            voice_text="Hola, ¿en qué te ayudo?",
            analysis_summary={"intent": "greeting"},
            route="fast_path",
        )

    with (
        patch("prosales.api.v1.endpoints.conversation.require_agent_context", AsyncMock(return_value=ctx)),
        patch(
            "prosales.api.v1.endpoints.conversation._resolve_client_and_conversation",
            AsyncMock(return_value=(client_id, conversation_id)),
        ),
        patch("prosales.api.v1.endpoints.conversation.PipelineRunner") as MockRunner,
        patch("prosales.api.v1.endpoints.conversation.spawn_live_learning") as mock_spawn,
    ):
        MockRunner.return_value.run = fake_run

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            async with client.stream(
                "POST",
                "/api/v1/conversation/message/stream",
                json={"message": "hola", "client_id": "ext-1"},
                headers={"x-api-key": "sk-whatever"},
            ) as response:
                raw = ""
                async for chunk in response.aiter_text():
                    raw += chunk

    events = _parse_sse(raw)
    token_events = [e for e in events if e["stage"] == "token"]
    assert [e["text"] for e in token_events] == ["Hola", ", ¿en qué", " te ayudo?"]

    completed = [e for e in events if e["stage"] == "completed"]
    assert len(completed) == 1
    assert completed[0]["result"]["response"] == "Hola, ¿en qué te ayudo?"
    assert completed[0]["result"]["conversation_id"] == str(conversation_id)

    mock_spawn.assert_not_called()  # qualification_terminal defaults False


@pytest.mark.asyncio
async def test_stream_emits_error_event_on_pipeline_failure():
    ctx = _agent_context()
    client_id, conversation_id = uuid4(), uuid4()

    async def failing_run(*args, on_token=None, **kwargs):
        await on_token("partial")
        raise RuntimeError("pipeline blew up")

    with (
        patch("prosales.api.v1.endpoints.conversation.require_agent_context", AsyncMock(return_value=ctx)),
        patch(
            "prosales.api.v1.endpoints.conversation._resolve_client_and_conversation",
            AsyncMock(return_value=(client_id, conversation_id)),
        ),
        patch("prosales.api.v1.endpoints.conversation.PipelineRunner") as MockRunner,
    ):
        MockRunner.return_value.run = failing_run

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            async with client.stream(
                "POST",
                "/api/v1/conversation/message/stream",
                json={"message": "hola", "client_id": "ext-1"},
                headers={"x-api-key": "sk-whatever"},
            ) as response:
                raw = ""
                async for chunk in response.aiter_text():
                    raw += chunk

    events = _parse_sse(raw)
    assert events[-1]["stage"] == "error"
    assert "pipeline blew up" in events[-1]["message"]
