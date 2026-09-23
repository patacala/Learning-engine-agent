"""Neutral assistant channel — the app's default conversational state.

A thin LLM chat with per-session memory and a neutral sales-training coach persona.
It does NOT run the sales pipeline and never learns; it just converses.
"""

import logging
import traceback

from fastapi import APIRouter, Header, HTTPException

from prosales.api.v1.dependencies import get_agent_context
from prosales.api.v1.schemas.assistant import (
    AssistantMessageRequest,
    AssistantMessageResponse,
)
from prosales.channels.assistant.service import (
    AssistantService,
    AssistantSessionNotFound,
)
from prosales.infrastructure.database.connection import async_session_factory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["assistant"])


async def _resolve_context(x_api_key: str | None):
    async with async_session_factory() as session:
        return await get_agent_context(session, x_api_key)


@router.post("/message", response_model=AssistantMessageResponse)
async def send_message(
    request: AssistantMessageRequest,
    x_api_key: str | None = Header(None),
):
    """Send a message to the assistant; create a session if none is provided."""
    agent_context = await _resolve_context(x_api_key)
    service = AssistantService()

    session_id = request.session_id
    if session_id is None:
        conv = await service.start(agent_context)
        session_id = conv.id

    try:
        reply = await service.message(session_id, request.text, agent_context)
    except AssistantSessionNotFound:
        raise HTTPException(status_code=404, detail="Assistant session not found")
    except Exception as e:
        logger.error("Assistant message error: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Assistant error: {e}")

    return AssistantMessageResponse(session_id=session_id, reply=reply)
