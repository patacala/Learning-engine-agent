import logging
import traceback
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

from prosales.api.v1.dependencies import get_agent_context, get_redis_cache
from prosales.api.v1.schemas.conversation import MessageRequest, MessageResponse
from prosales.infrastructure.database.connection import async_session_factory
from prosales.infrastructure.database.models import ConversationModel
from prosales.infrastructure.database.repositories.client import SQLClientRepository
from prosales.infrastructure.database.repositories.conversation import SQLConversationRepository
from prosales.services.live_learning import run_live_learning
from prosales.services.pipeline_runner import PipelineRunner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversation", tags=["conversation"])


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

    # --- Short setup session: resolve context + get-or-create client/conversation.
    async with async_session_factory() as session:
        async with session.begin():
            agent_context = await get_agent_context(session, x_api_key)
            organization_id = agent_context.organization_id if agent_context else None

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
                    agent_version_id=agent_context.agent_version_id if agent_context else None,
                )
                await conversation_repo.save(conversation)

            client_id = client.id
            conversation_id = conversation.id
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
