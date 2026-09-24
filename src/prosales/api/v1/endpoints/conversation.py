import asyncio
import logging
import traceback
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from fastapi.responses import StreamingResponse

from prosales.api.v1.dependencies import get_redis_cache, require_agent_context
from prosales.api.v1.endpoints._sse import _sse_event
from prosales.api.v1.schemas.conversation import MessageRequest, MessageResponse
from prosales.core.models.agent import AgentContext
from prosales.infrastructure.database.connection import async_session_factory
from prosales.infrastructure.database.models import ConversationModel
from prosales.infrastructure.database.repositories.client import SQLClientRepository
from prosales.infrastructure.database.repositories.conversation import SQLConversationRepository
from prosales.services.live_learning import run_live_learning, spawn_live_learning
from prosales.services.pipeline_runner import PipelineRunner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversation", tags=["conversation"])


async def _resolve_client_and_conversation(
    request: MessageRequest, agent_context: AgentContext
) -> tuple[UUID, UUID]:
    """Short setup session: resolve/create client + conversation, then release
    the connection — the pipeline itself runs with no connection held across
    the LLM calls. Shared by both /message and /message/stream."""
    organization_id = agent_context.organization_id
    async with async_session_factory() as session:
        async with session.begin():
            conversation_repo = SQLConversationRepository(session)
            client_repo = SQLClientRepository(session)

            client = await client_repo.get_or_create(
                request.client_id, organization_id=organization_id
            )

            if request.conversation_id:
                conversation = await conversation_repo.get_by_id(request.conversation_id)
                if not conversation:
                    raise HTTPException(status_code=404, detail="Conversation not found")
            else:
                conversation = ConversationModel(
                    id=uuid4(),
                    client_id=client.id,
                    organization_id=organization_id,
                    agent_version_id=agent_context.agent_version_id,
                )
                await conversation_repo.save(conversation)

            return client.id, conversation.id


@router.post("/message", response_model=MessageResponse)
async def process_message(
    request: MessageRequest,
    background_tasks: BackgroundTasks,
    x_api_key: str | None = Header(None),
):
    """Process a client message through the cognitive pipeline.

    This endpoint does NOT depend on ``get_db_session`` (which would hold one
    connection for the whole request, including the LLM calls). Instead it opens
    a SHORT session only for setup (resolve context + get-or-create client and
    conversation), closes it, then runs the pipeline with the session_factory so
    no connection is held while the LLM is working.
    """
    cache = get_redis_cache()

    async with async_session_factory() as session:
        agent_context = await require_agent_context(session, x_api_key)
    client_id, conversation_id = await _resolve_client_and_conversation(request, agent_context)
    # Connection returned to the pool here — the pipeline runs without holding one.

    # Run pipeline via PipelineRunner (short sessions per DB operation).
    try:
        runner = PipelineRunner(async_session_factory, cache=cache)
        result = await runner.run(
            message=request.message,
            client_id=client_id,
            conversation_id=conversation_id,
            agent_context=agent_context,
            store_user_message=True,
        )
    except Exception as e:
        logger.error("Pipeline error: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Pipeline error: {e}")

    # Cognition marked the conversation terminal → learn from it in the background.
    if result.qualification_terminal:
        background_tasks.add_task(run_live_learning, conversation_id)

    return MessageResponse(
        conversation_id=conversation_id,
        response=result.response,
        voice_ssml=result.voice_ssml,
        analysis=result.analysis_summary,
        route=result.route,
        contact_qualification=result.contact_qualification,
    )


@router.post("/message/stream")
async def process_message_stream(
    request: MessageRequest,
    x_api_key: str | None = Header(None),
):
    """Same pipeline as POST /message, but the main response streams token by
    token via SSE instead of waiting ~4s for the full reply. Additive — the
    plain-JSON /message endpoint above is unchanged, existing callers are
    unaffected.

    Stages: {"stage":"token","text":...} per chunk, then
    {"stage":"completed","result":{...same fields as MessageResponse...}}, or
    {"stage":"error","message":...} if the pipeline fails (can't raise an
    HTTPException — headers are already flushed once the stream starts).
    """
    cache = get_redis_cache()

    async with async_session_factory() as session:
        agent_context = await require_agent_context(session, x_api_key)
    client_id, conversation_id = await _resolve_client_and_conversation(request, agent_context)

    async def event_stream():
        queue: asyncio.Queue[str] = asyncio.Queue()

        async def on_token(text: str) -> None:
            await queue.put(text)

        runner = PipelineRunner(async_session_factory, cache=cache)
        task = asyncio.create_task(
            runner.run(
                message=request.message,
                client_id=client_id,
                conversation_id=conversation_id,
                agent_context=agent_context,
                store_user_message=True,
                on_token=on_token,
            )
        )

        try:
            while not task.done():
                try:
                    chunk = await asyncio.wait_for(queue.get(), timeout=0.1)
                    yield _sse_event({"stage": "token", "text": chunk})
                except asyncio.TimeoutError:
                    continue
            # Drain anything queued after the task finished but before the
            # last wait_for picked it up.
            while not queue.empty():
                yield _sse_event({"stage": "token", "text": queue.get_nowait()})

            result = await task  # re-raises if the pipeline errored
        except Exception as e:
            logger.error("Pipeline error (stream): %s\n%s", e, traceback.format_exc())
            yield _sse_event({"stage": "error", "message": str(e)})
            return

        if result.qualification_terminal:
            spawn_live_learning(conversation_id)

        yield _sse_event({
            "stage": "completed",
            "result": {
                "conversation_id": str(conversation_id),
                "response": result.response,
                "voice_ssml": result.voice_ssml,
                "analysis": result.analysis_summary,
                "route": result.route,
                "contact_qualification": result.contact_qualification,
            },
        })

    return StreamingResponse(event_stream(), media_type="text/event-stream")
