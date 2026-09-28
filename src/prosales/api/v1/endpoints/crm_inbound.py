"""Inbound webhook target for the CRM's agent_trigger (event_type=message.received).

ProSales is one of two possible targets the CRM can point this webhook at
(the other being an n8n workflow) — only one is ever active per organization
at a time, switched manually from the CRM's web UI. See CLAUDE.md / the
plan discussed in-session for the full architecture.

Contract:
  - Auth: same X-API-Key as /conversation/message (the org's ProSales API key,
    configured as `auth_header_value` on the CRM's automation-agent row).
  - Fast ACK: returns 200 immediately: the CRM's fetch has a 30s timeout and
    this is a fire-and-forget BullMQ job on their side — we must not make it
    wait for the full pipeline (which can take several seconds).
  - The actual reply is delivered asynchronously by calling the CRM's own
    POST /ai/tools/execute with tool="send_message" — same mechanism any
    other tool call uses, so it goes through the CRM's normal audit/event
    path (agent_tool_executions row, `agent.tool.executed` event) instead of
    a special-cased direct send.

Known limitation (not yet wired): the enriched context the CRM sends
(contact profile, upcoming_appointments, payment_services) isn't fed into
the pipeline yet — PipelineRunner.run() has no extra-context parameter today.
For now it's available in the request for whoever needs it later; the
pipeline runs off the message text alone, same as /conversation/message.
"""

import logging
import traceback
from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from sqlalchemy import select

from prosales.api.v1.dependencies import get_redis_cache, require_agent_context
from prosales.api.v1.schemas.crm_inbound import CRMInboundRequest
from prosales.core.models.agent import AgentContext
from prosales.infrastructure.database.connection import async_session_factory
from prosales.infrastructure.database.models import ConversationModel
from prosales.infrastructure.database.models_agent import OrganizationModel
from prosales.infrastructure.database.repositories.client import SQLClientRepository
from prosales.infrastructure.database.repositories.conversation import SQLConversationRepository
from prosales.services.live_learning import spawn_live_learning
from prosales.services.pipeline_runner import PipelineRunner

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/crm", tags=["crm"])


async def _resolve_client_and_conversation(
    body: CRMInboundRequest, agent_context: AgentContext
) -> tuple[UUID, UUID]:
    """Same short-setup-session pattern as conversation.py, but keyed by the
    CRM's own IDs: contact_id becomes the client's external_id (ClientModel
    is already designed for this — see SQLClientRepository.get_or_create),
    and conversation_id is reused AS ProSales' own conversation id (both
    sides are UUIDs; treating them as the same identity avoids a separate
    mapping table and keeps cross-system debugging simple).
    """
    organization_id = agent_context.organization_id
    async with async_session_factory() as session:
        async with session.begin():
            conversation_repo = SQLConversationRepository(session)
            client_repo = SQLClientRepository(session)

            client = await client_repo.get_or_create(
                body.contact_id or str(body.conversation_id), organization_id=organization_id
            )

            conversation = await conversation_repo.get_by_id(body.conversation_id)
            if not conversation:
                conversation = ConversationModel(
                    id=body.conversation_id,
                    client_id=client.id,
                    organization_id=organization_id,
                    agent_version_id=agent_context.agent_version_id,
                )
                await conversation_repo.save(conversation)

            return client.id, conversation.id


async def _send_reply_to_crm(organization_id: UUID, conversation_id: UUID, content: str) -> None:
    """Deliver the generated reply via the CRM's own tool-execution contract
    (tool="send_message") — never a direct/special-cased HTTP call.
    """
    async with async_session_factory() as session:
        org = (
            await session.execute(
                select(OrganizationModel).where(OrganizationModel.id == organization_id)
            )
        ).scalar_one_or_none()

    if not org or not org.crm_base_url or not org.crm_api_key or not org.crm_agent_id:
        logger.warning(
            "CRM callback skipped for org %s — crm_base_url/crm_api_key/crm_agent_id not set",
            organization_id,
        )
        return

    url = org.crm_base_url.rstrip("/") + "/api/v1/ai/tools/execute"
    body = {
        "agent_id": org.crm_agent_id,
        "tool": "send_message",
        "input": {"conversation_id": str(conversation_id), "content": content},
        "conversation_id": str(conversation_id),
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                url, json=body, headers={"x-api-key": org.crm_api_key}
            )
            resp.raise_for_status()
    except Exception as e:
        logger.error("CRM send_message callback failed for org %s: %s", organization_id, e)


async def _run_pipeline_and_reply(
    message: str,
    client_id: UUID,
    conversation_id: UUID,
    agent_context: AgentContext,
    organization_id: UUID,
) -> None:
    cache = get_redis_cache()
    try:
        runner = PipelineRunner(async_session_factory, cache=cache)
        result = await runner.run(
            message=message,
            client_id=client_id,
            conversation_id=conversation_id,
            agent_context=agent_context,
            store_user_message=True,
        )
    except Exception as e:
        logger.error("CRM inbound pipeline error: %s\n%s", e, traceback.format_exc())
        return

    if result.qualification_terminal:
        spawn_live_learning(conversation_id)

    await _send_reply_to_crm(organization_id, conversation_id, result.response)


@router.post("/inbound", status_code=202)
async def crm_inbound(
    body: CRMInboundRequest,
    background_tasks: BackgroundTasks,
    x_api_key: str | None = Header(None),
):
    """Fast-ACK webhook target — runs the pipeline in the background and
    delivers the reply via the CRM's own send_message tool when it's ready.
    """
    async with async_session_factory() as session:
        agent_context = await require_agent_context(session, x_api_key)

    if agent_context.organization_id is None:
        raise HTTPException(status_code=400, detail="Agent has no organization")

    client_id, conversation_id = await _resolve_client_and_conversation(body, agent_context)

    background_tasks.add_task(
        _run_pipeline_and_reply,
        body.payload.message,
        client_id,
        conversation_id,
        agent_context,
        agent_context.organization_id,
    )

    return {"status": "accepted", "conversation_id": str(conversation_id)}
