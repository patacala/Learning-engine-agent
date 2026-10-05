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

The enriched context the CRM sends (contact profile, upcoming_appointments,
payment_services) is passed through to the pipeline as read-only reference
data via PipelineRunner.run(extra_context=...): the prompt injects it so the
agent doesn't re-ask for known data, and the tool loop uses it to ground
scheduling/payment actions.
"""

import asyncio
import json
import logging
import traceback
from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from sqlalchemy import select

from prosales.api.v1.dependencies import get_redis_cache, require_agent_context
from prosales.config import settings
from prosales.api.v1.schemas.crm_inbound import CRMInboundRequest
from prosales.core.models.agent import AgentContext
from prosales.infrastructure.database.connection import async_session_factory
from prosales.infrastructure.database.models import ConversationModel
from prosales.infrastructure.database.models_agent import OrganizationModel
from prosales.infrastructure.database.repositories.client import SQLClientRepository
from prosales.infrastructure.agent.providers import AgentQualificationProvider
from prosales.infrastructure.database.repositories.conversation import SQLConversationRepository
from prosales.services.crm_tools import CRMToolExecutor, qualification_to_contact_update
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


# Capability that unlocks the appointment/payment tools in the in-turn Action
# Layer. Reuses the existing org-level "appointment" capability from
# ORG_CAPABILITY_PRESETS rather than inventing a new vocabulary word.
# opt_out_contact is NOT gated by this — see CRMToolExecutor.actions_enabled.
ACTIONS_CAPABILITY = "appointment"


async def _load_org(organization_id: UUID) -> OrganizationModel | None:
    async with async_session_factory() as session:
        return (
            await session.execute(
                select(OrganizationModel).where(OrganizationModel.id == organization_id)
            )
        ).scalar_one_or_none()


def _org_has_crm(org: OrganizationModel | None) -> bool:
    return bool(org and org.crm_base_url and org.crm_api_key and org.crm_agent_id)


def _seed_known_fields(schema, contact: dict | None) -> set[str]:
    """Mark required fields the CRM already has for this contact as satisfied, so
    the scheduling gate doesn't ask for data we already know (name/email/phone)."""
    known: set[str] = set()
    if schema is None or not contact:
        return known
    for f in schema.required_for_scheduling():
        target = f.target()
        if target == "email" and contact.get("email"):
            known.add(f.key)
        elif target == "phone" and contact.get("phone"):
            known.add(f.key)
        elif target == "full_name" and contact.get("first_name"):
            known.add(f.key)
    return known


def _build_executor(
    org: OrganizationModel | None,
    conversation_id: UUID,
    contact_id: str | None,
    schema=None,
    contact: dict | None = None,
    actions_enabled: bool = True,
) -> CRMToolExecutor | None:
    """One executor for both the in-turn tool loop and the qualification push —
    needs only CRM connectivity. ``actions_enabled`` gates the appointment/
    payment tools (see ACTIONS_CAPABILITY below); opt_out_contact stays
    reachable regardless — the executor itself enforces that. The
    qualification push is always allowed when there's connectivity. When a
    schema is given, seeds the scheduling gate."""
    if not _org_has_crm(org):
        return None
    required = [f.key for f in schema.required_for_scheduling()] if schema is not None else []
    return CRMToolExecutor(
        base_url=org.crm_base_url,
        api_key=org.crm_api_key,
        agent_id=org.crm_agent_id,
        conversation_id=conversation_id,
        contact_id=contact_id,
        required_fields=required,
        known_fields=_seed_known_fields(schema, contact),
        actions_enabled=actions_enabled,
    )


async def _push_qualification(
    executor: CRMToolExecutor,
    cache,
    contact_id: str | None,
    qual_public: dict,
    schema=None,
    analysis_summary: dict | None = None,
    existing_tags: list[str] | None = None,
) -> None:
    """Push the cognitive qualification to the CRM via update_contact, but only
    when it changed since the last push for this contact (dedup via Redis) — the
    CRM is kept fresh without a redundant write every single turn."""
    if not contact_id or not qual_public:
        return
    update = qualification_to_contact_update(
        qual_public, schema=schema, analysis_summary=analysis_summary, existing_tags=existing_tags
    )
    signature = json.dumps(update, sort_keys=True, default=str)
    key = f"crm:qual:{contact_id}"
    try:
        if cache and await cache.get(key) == signature:
            return  # unchanged since last push
    except Exception:  # noqa: BLE001 — cache outage must not block the push
        pass

    result = await executor.execute("update_contact", update)
    if cache and not result.get("error"):
        try:
            await cache.set(key, signature, ttl=86400)
        except Exception:  # noqa: BLE001
            pass


async def _send_reply_to_crm(
    org: OrganizationModel | None, conversation_id: UUID, content: str
) -> None:
    """Deliver the generated reply via the CRM's own tool-execution contract
    (tool="send_message") — never a direct/special-cased HTTP call.
    """
    if not _org_has_crm(org):
        logger.warning(
            "CRM callback skipped — crm_base_url/crm_api_key/crm_agent_id not set for org %s",
            getattr(org, "id", None),
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
        logger.error("CRM send_message callback failed for org %s: %s", org.id, e)


async def _run_pipeline_and_reply(
    message: str,
    client_id: UUID,
    conversation_id: UUID,
    agent_context: AgentContext,
    organization_id: UUID,
    extra_context: dict | None = None,
    contact_id: str | None = None,
) -> None:
    contact = (extra_context or {}).get("contact") if isinstance(extra_context, dict) else None
    if contact and "opt-out" in (contact.get("tags") or []):
        # The contact already opted out (via this same tool, or the CRM's own
        # detection) — honor it by not sending anything further, not just by
        # skipping a redundant opt_out_contact call.
        logger.info("Contact %s is opted out — skipping pipeline run", contact_id)
        return

    cache = get_redis_cache()
    org = await _load_org(organization_id)

    # Resolve the qualification schema once; shared by the pipeline (extraction/
    # asking/gate) and the CRM push mapping.
    schema = None
    if agent_context.agent_version_id:
        try:
            schema = await AgentQualificationProvider(async_session_factory, cache=cache).get(
                agent_context.agent_version_id
            )
        except Exception as e:  # noqa: BLE001 — schema is best-effort
            logger.warning("Qualification schema resolve failed: %s", e)

    executor = _build_executor(
        org, conversation_id, contact_id, schema=schema, contact=contact,
        actions_enabled=agent_context.has_capability(ACTIONS_CAPABILITY),
    )
    # Opt-out stays reachable even without the appointment capability — the
    # executor itself gates the appointment/payment tools (actions_enabled).
    tool_executor = executor

    try:
        runner = PipelineRunner(async_session_factory, cache=cache)
        result = await runner.run(
            message=message,
            client_id=client_id,
            conversation_id=conversation_id,
            agent_context=agent_context,
            store_user_message=True,
            extra_context=extra_context,
            tool_executor=tool_executor,
            qualification_schema=schema,
        )
    except Exception as e:
        logger.error("CRM inbound pipeline error: %s\n%s", e, traceback.format_exc())
        return

    if result.qualification_terminal:
        spawn_live_learning(conversation_id)

    await _send_reply_to_crm(org, conversation_id, result.response)

    if executor:
        existing_tags = contact.get("tags") if isinstance(contact, dict) else None
        await _push_qualification(
            executor, cache, contact_id, result.contact_qualification,
            schema=schema, analysis_summary=result.analysis_summary, existing_tags=existing_tags,
        )


# --- Message debounce (coalesce rapid messages into one turn) ---------------
# In-process per-conversation timers; the message texts themselves live in Redis
# (durable, and atomically drained). Multi-worker caveat: timers are per-process
# so coalescing is best-effort across workers, but list_drain's atomicity still
# guarantees the same messages are never processed twice. A cross-worker Redis
# scheduler is the upgrade path if this proves insufficient.
_debounce_tasks: dict[str, asyncio.Task] = {}


def _buffer_key(conversation_id: UUID) -> str:
    return f"crm:buf:{conversation_id}"


async def _debounce_and_run(
    conversation_id: UUID,
    client_id: UUID,
    agent_context: AgentContext,
    organization_id: UUID,
    extra_context: dict | None,
    contact_id: str | None,
) -> None:
    """Wait out the quiet-window; a newer message cancels this task and starts
    its own. When the window elapses undisturbed, drain every buffered message
    for the conversation and run the pipeline once on the combined text."""
    try:
        await asyncio.sleep(settings.crm_debounce_seconds)
    except asyncio.CancelledError:
        return  # superseded by a newer message — it owns the buffer now
    _debounce_tasks.pop(str(conversation_id), None)
    try:
        cache = get_redis_cache()
        buffered = await cache.list_drain(_buffer_key(conversation_id))
        if not buffered:
            return
        combined = "\n".join(buffered)
        await _run_pipeline_and_reply(
            combined, client_id, conversation_id, agent_context,
            organization_id, extra_context, contact_id,
        )
    except Exception as e:  # noqa: BLE001 — a detached task must log, not vanish
        logger.error("CRM debounce run error: %s\n%s", e, traceback.format_exc())


@router.post("/inbound", status_code=202)
async def crm_inbound(
    body: CRMInboundRequest,
    background_tasks: BackgroundTasks,
    x_api_key: str | None = Header(None),
):
    """Fast-ACK webhook target — ACKs immediately, then (after a short
    debounce window that coalesces rapid messages) runs the pipeline in the
    background and delivers the reply via the CRM's own send_message tool.
    """
    async with async_session_factory() as session:
        agent_context = await require_agent_context(session, x_api_key)

    if agent_context.organization_id is None:
        raise HTTPException(status_code=400, detail="Agent has no organization")

    client_id, conversation_id = await _resolve_client_and_conversation(body, agent_context)

    extra_context = {
        "contact": body.contact.model_dump() if body.contact else None,
        "upcoming_appointments": [a.model_dump() for a in body.upcoming_appointments],
        "payment_services": [s.model_dump() for s in body.payment_services],
        "payment_currency": body.payment_currency,
        "channel": body.payload.channel,
    }

    if settings.crm_debounce_seconds <= 0:
        # Debounce disabled: one message = one run, immediately.
        background_tasks.add_task(
            _run_pipeline_and_reply,
            body.payload.message,
            client_id,
            conversation_id,
            agent_context,
            agent_context.organization_id,
            extra_context,
            body.contact_id,
        )
        return {"status": "accepted", "conversation_id": str(conversation_id)}

    # Buffer this message and (re)arm the quiet-window timer — a newer message
    # within the window cancels the pending run and restarts it, so the agent
    # answers the whole thought at once instead of each fragment.
    cache = get_redis_cache()
    key = str(conversation_id)
    await cache.list_push(_buffer_key(conversation_id), body.payload.message)

    existing = _debounce_tasks.get(key)
    if existing and not existing.done():
        existing.cancel()
    _debounce_tasks[key] = asyncio.create_task(
        _debounce_and_run(
            conversation_id,
            client_id,
            agent_context,
            agent_context.organization_id,
            extra_context,
            body.contact_id,
        )
    )

    return {"status": "accepted", "conversation_id": key}
