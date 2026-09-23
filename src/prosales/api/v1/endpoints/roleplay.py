"""Roleplay training channel — REST endpoints.

A companion app (voice-driven, does its own STT/TTS) drives a scenario-based
practice session turn by turn with plain text. On end, the transcript is fed to
the learning engine exactly like a pasted transcript.
"""

import logging
import traceback
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Header
from fastapi.responses import StreamingResponse

from prosales.api.v1.dependencies import get_agent_context, get_redis_cache, verify_internal_or_api_key
from prosales.api.v1.endpoints._sse import _sse_event
from prosales.api.v1.schemas.roleplay import (
    EndRoleplayRequest,
    EndRoleplayResponse,
    LearnedExpression,
    LearnedMove,
    RoleplayLearned,
    RoleplaySessionResponse,
    RoleplayTurn,
    RoleplayTurnRequest,
    RoleplayTurnResponse,
    StartRoleplayRequest,
    StartRoleplayResponse,
)
from prosales.channels.roleplay.service import (
    RoleplayClosedError,
    RoleplayModeError,
    RoleplayOutcomeError,
    RoleplayService,
    RoleplaySessionNotFound,
    learns_from_outcome,
    speaker_for,
)
from prosales.core.models.agent import AgentContext
from prosales.infrastructure.agent.resolver import resolve_published_version
from prosales.infrastructure.database.connection import async_session_factory
from prosales.infrastructure.database.models import ConversationModel
from prosales.infrastructure.database.repositories.expressions import (
    SQLExpressionsRepository,
)
from prosales.infrastructure.database.repositories.moves import SQLMovesRepository
from prosales.services.live_learning import run_live_learning

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/roleplay", tags=["roleplay"], dependencies=[Depends(verify_internal_or_api_key)])


async def _resolve_context(x_api_key: str | None):
    async with async_session_factory() as session:
        return await get_agent_context(session, x_api_key)


async def _resolve_training_agent(agent_version_id: UUID) -> AgentContext:
    """Resolve a published Cognition agent for training. No org API key required."""
    async with async_session_factory() as session:
        ctx = await resolve_published_version(session, agent_version_id)
        if ctx is None:
            raise HTTPException(status_code=404, detail="Published agent version not found")
        return ctx


async def _resolve_session_agent(session_id: UUID) -> AgentContext | None:
    """Fall back to the agent stored on the roleplay conversation."""
    async with async_session_factory() as session:
        conv = await session.get(ConversationModel, session_id)
        if conv is None or conv.agent_version_id is None:
            return None
        return await resolve_published_version(session, conv.agent_version_id)


@router.post("/sessions", response_model=StartRoleplayResponse)
async def start_session(
    request: StartRoleplayRequest,
    x_api_key: str | None = Header(None),
):
    """Create a roleplay session for a scenario. Training agents are Cognition-owned."""
    if request.agent_version_id is not None:
        agent_context = await _resolve_training_agent(request.agent_version_id)
    else:
        agent_context = await _resolve_context(x_api_key)
    service = RoleplayService(cache=get_redis_cache())
    try:
        conv = await service.start(request.scenario, request.mode, agent_context)
    except RoleplayModeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return StartRoleplayResponse(
        session_id=conv.id,
        mode=request.mode,
        scenario=request.scenario,
        agent_version_id=conv.agent_version_id,
    )


@router.post("/sessions/{session_id}/turn", response_model=RoleplayTurnResponse)
async def take_turn(
    session_id: UUID,
    request: RoleplayTurnRequest,
    x_api_key: str | None = Header(None),
):
    """Send what the human just said; get Cognition's reply in its role."""
    agent_context = await _resolve_context(x_api_key)
    if agent_context is None:
        agent_context = await _resolve_session_agent(session_id)
    service = RoleplayService(cache=get_redis_cache())
    try:
        reply = await service.turn(session_id, request.text, agent_context)
    except RoleplaySessionNotFound:
        raise HTTPException(status_code=404, detail="Roleplay session not found")
    except RoleplayClosedError:
        raise HTTPException(status_code=409, detail="Roleplay session is already closed")
    except RoleplayModeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Roleplay turn error: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Roleplay error: {e}")
    return RoleplayTurnResponse(session_id=session_id, reply=reply)


@router.post("/sessions/{session_id}/turn/stream")
async def take_turn_stream(
    session_id: UUID,
    request: RoleplayTurnRequest,
    x_api_key: str | None = Header(None),
):
    """Same as /turn, but streamed as SSE stages so a slow reply (the full sales
    pipeline in mode='agent') doesn't leave the client hanging silently."""
    agent_context = await _resolve_context(x_api_key)
    if agent_context is None:
        agent_context = await _resolve_session_agent(session_id)
    service = RoleplayService(cache=get_redis_cache())

    async def event_stream():
        yield _sse_event({"stage": "thinking"})
        try:
            reply = await service.turn(session_id, request.text, agent_context)
        except RoleplaySessionNotFound:
            yield _sse_event(
                {"stage": "error", "code": "session_not_found",
                 "message": "Roleplay session not found"}
            )
            return
        except RoleplayClosedError:
            yield _sse_event(
                {"stage": "error", "code": "session_closed",
                 "message": "Roleplay session is already closed"}
            )
            return
        except RoleplayModeError as e:
            yield _sse_event({"stage": "error", "code": "invalid_mode", "message": str(e)})
            return
        except Exception as e:  # noqa: BLE001 — response already started, can't raise
            logger.error("Roleplay turn (stream) error: %s\n%s", e, traceback.format_exc())
            yield _sse_event(
                {"stage": "error", "code": "error", "message": f"Roleplay error: {e}"}
            )
            return
        yield _sse_event(
            {"stage": "completed", "session_id": str(session_id), "reply": reply}
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/sessions/{session_id}/end", response_model=EndRoleplayResponse)
async def end_session(
    session_id: UUID,
    request: EndRoleplayRequest,
    background_tasks: BackgroundTasks,
    x_api_key: str | None = Header(None),
):
    """Close the session and learn from the transcript in the background."""
    service = RoleplayService()
    try:
        _, effective_outcome = await service.end(
            session_id, request.outcome, request.sub_outcome
        )
    except RoleplaySessionNotFound:
        raise HTTPException(status_code=404, detail="Roleplay session not found")
    except RoleplayOutcomeError as e:
        raise HTTPException(status_code=422, detail=str(e))
    # Only terminal outcomes drive learning; a non-terminal close learns nothing.
    learning = learns_from_outcome(effective_outcome)
    if learning:
        background_tasks.add_task(run_live_learning, session_id)
    return EndRoleplayResponse(session_id=session_id, learning=learning)


@router.get("/sessions/{session_id}", response_model=RoleplaySessionResponse)
async def get_session(session_id: UUID):
    """Fetch a roleplay session's state, transcript, and what it taught Cognition."""
    service = RoleplayService()
    try:
        conv = await service.transcript(session_id)
    except RoleplaySessionNotFound:
        raise HTTPException(status_code=404, detail="Roleplay session not found")
    ordered = sorted(conv.messages, key=lambda m: (m.turn_index or 0, m.created_at))

    # What Cognition learned specifically from THIS session (not the whole brain).
    async with async_session_factory() as session:
        moves = await SQLMovesRepository(session).list_by_conversation(session_id)
        expressions = await SQLExpressionsRepository(session).list_by_conversation(session_id)

    learned_detail = RoleplayLearned(
        learned=conv.learned_at is not None,
        learned_at=conv.learned_at.isoformat() if conv.learned_at else None,
        moves_total=len(moves),
        moves_approved=sum(1 for m in moves if m.status == "approved"),
        moves=[
            LearnedMove(
                move_kind=m.move_kind,
                polarity=m.polarity,
                transcript_excerpt=m.transcript_excerpt,
                score=m.score,
                status=m.status,
            )
            for m in moves
        ],
        expressions=[
            LearnedExpression(
                exact_phrase=e.exact_phrase,
                polarity=e.polarity,
                success_rate=e.success_rate,
                times_used=e.times_used,
            )
            for e in expressions
        ],
    )

    return RoleplaySessionResponse(
        session_id=conv.id,
        mode=conv.roleplay_mode,
        scenario=conv.scenario,
        outcome=conv.outcome,
        sub_outcome=conv.sub_outcome,
        is_active=conv.is_active,
        learned=conv.learned_at is not None,
        agent_version_id=conv.agent_version_id,
        transcript=[
            RoleplayTurn(speaker=speaker_for(m.role, conv.roleplay_mode), text=m.content)
            for m in ordered
        ],
        learned_detail=learned_detail,
    )
