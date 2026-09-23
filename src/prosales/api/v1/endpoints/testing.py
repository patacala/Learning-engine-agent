"""Test Playground endpoints.

Lets a user mount external business context (a scenario) and chat with a
trained agent in full isolation: the real cognitive pipeline runs, but nothing
is persisted (no conversations, messages, events, or episodes). Saved scenarios
and Training drafts are the only things written, and only on explicit request.
"""

import logging
import traceback
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from prosales.api.v1.dependencies import get_db_session, get_redis_cache, verify_internal_token
from prosales.api.v1.schemas.testing import (
    HandoffRequest,
    HandoffResponse,
    RetrievedDocument,
    ScenarioCreate,
    ScenarioResponse,
    TemporaryDocument,
    TestDebugInfo,
    TestMessageRequest,
    TestMessageResponse,
)
from prosales.config import settings
from prosales.core.models.agent import AgentContext
from prosales.core.models.execution import PipelineExecution, Versions
from prosales.di.container import create_analyzer_llm, create_llm_provider
from prosales.engines.knowledge.hybrid_engine import HybridKnowledgeEngine
from prosales.engines.knowledge.temporary_store import TemporaryVectorStore
from prosales.engines.memory.ephemeral import EphemeralMemoryEngine
from prosales.infrastructure.agent.providers import (
    AgentIdentityProvider,
    AgentPersonalityProvider,
    AgentPromptProvider,
    AgentRuleProvider,
    AgentStrategyProvider,
    AgentVoiceProvider,
)
from prosales.infrastructure.database.connection import live_session_factory
from prosales.infrastructure.database.models_agent import (
    AgentModel,
    AgentVersionModel,
    OrganizationAgentModel,
    OrganizationModel,
)
from prosales.infrastructure.database.models_testing import TestScenarioModel
from prosales.infrastructure.database.models_learning_session import LearningSessionModel
from prosales.infrastructure.database.repositories.testing import SQLScenarioRepository
from prosales.infrastructure.vector_store.pgvector import PGVectorStore
from prosales.pipeline.graph import build_cognitive_graph
from prosales.pipeline.state import CognitivePipelineState  # noqa: F401 (typing ref)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["testing"], dependencies=[Depends(verify_internal_token)])


# --------------------------------------------------------------------------- #
# Scenario CRUD (persisted)
# --------------------------------------------------------------------------- #

def _scenario_to_response(model: TestScenarioModel) -> ScenarioResponse:
    return ScenarioResponse(
        id=model.id,
        agent_version_id=model.agent_version_id,
        name=model.name,
        company_name=model.company_name or "",
        documents=[TemporaryDocument(**d) for d in (model.documents or [])],
        quick_facts=model.quick_facts or {},
        created_at=model.created_at,
    )


@router.post("/testing/scenarios", response_model=ScenarioResponse)
async def create_scenario(
    body: ScenarioCreate,
    session: AsyncSession = Depends(get_db_session),
):
    repo = SQLScenarioRepository(session)
    model = TestScenarioModel(
        id=uuid4(),
        agent_version_id=body.agent_version_id,
        name=body.name,
        company_name=body.company_name,
        documents=[d.model_dump() for d in body.documents],
        quick_facts=body.quick_facts,
    )
    await repo.save(model)
    return _scenario_to_response(model)


@router.get("/testing/scenarios", response_model=list[ScenarioResponse])
async def list_scenarios(
    agent_version_id: UUID,
    session: AsyncSession = Depends(get_db_session),
):
    repo = SQLScenarioRepository(session)
    scenarios = await repo.list_for_agent(agent_version_id)
    return [_scenario_to_response(s) for s in scenarios]


@router.put("/testing/scenarios/{scenario_id}", response_model=ScenarioResponse)
async def update_scenario(
    scenario_id: UUID,
    body: ScenarioCreate,
    session: AsyncSession = Depends(get_db_session),
):
    repo = SQLScenarioRepository(session)
    model = await repo.update(
        scenario_id,
        name=body.name,
        company_name=body.company_name,
        documents=[d.model_dump() for d in body.documents],
        quick_facts=body.quick_facts,
    )
    if model is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return _scenario_to_response(model)


@router.delete("/testing/scenarios/{scenario_id}")
async def delete_scenario(
    scenario_id: UUID,
    session: AsyncSession = Depends(get_db_session),
):
    repo = SQLScenarioRepository(session)
    deleted = await repo.delete(scenario_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {"deleted": True}


# --------------------------------------------------------------------------- #
# Isolated test conversation
# --------------------------------------------------------------------------- #

async def _load_test_agent_context(
    session: AsyncSession, agent_version_id: UUID
) -> AgentContext:
    """Build an AgentContext for a version, read-only, for test runs."""
    version = (
        await session.execute(
            select(AgentVersionModel).where(AgentVersionModel.id == agent_version_id)
        )
    ).scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="Agent version not found")

    agent = (
        await session.execute(select(AgentModel).where(AgentModel.id == version.agent_id))
    ).scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    assignment = (
        await session.execute(
            select(OrganizationAgentModel).where(
                OrganizationAgentModel.agent_version_id == agent_version_id,
                OrganizationAgentModel.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()

    org = None
    if assignment is not None:
        org = (
            await session.execute(
                select(OrganizationModel).where(OrganizationModel.id == assignment.organization_id)
            )
        ).scalar_one_or_none()

    # Capabilities are permissive in test mode so no engine gates retrieval.
    org_caps = list(org.capabilities or []) if org else []
    for cap in ("knowledge", "voice"):
        if cap not in org_caps:
            org_caps.append(cap)

    return AgentContext(
        organization_id=org.id if org else uuid4(),
        organization_name=org.name if org else "Test Sandbox",
        org_capabilities=org_caps,
        agent_id=agent.id,
        agent_version_id=version.id,
        agent_name=agent.name,
        agent_type=agent.agent_type,
        agent_capabilities=version.capabilities or [],
    )


async def _build_temporary_store(
    embedder: PGVectorStore,
    company_name: str,
    documents: list[TemporaryDocument],
    quick_facts: dict[str, str],
) -> TemporaryVectorStore:
    store = TemporaryVectorStore()

    for doc in documents:
        text = f"{doc.title}\n{doc.content}".strip()
        if not text:
            continue
        embedding = await embedder.embed(text[:8000])
        store.add_document(
            doc_id=doc.id or str(uuid4()),
            title=doc.title,
            content=doc.content,
            category=doc.category or "general",
            embedding=embedding,
        )

    # Quick facts become one synthetic, always-relevant scenario document.
    facts_lines = [f"- {k}: {v}" for k, v in quick_facts.items() if str(v).strip()]
    if facts_lines:
        title = f"{company_name} — datos clave" if company_name else "Datos clave"
        content = "\n".join(facts_lines)
        embedding = await embedder.embed(f"{title}\n{content}"[:8000])
        store.add_document(
            doc_id=str(uuid4()),
            title=title,
            content=content,
            category="quick_facts",
            embedding=embedding,
        )

    return store


def _learning_context_for_debug(result: dict) -> dict:
    """Surface what PromptBuilder actually retrieved/injected for this turn.

    PromptBuilder now returns ``learning_context`` in its node output (see
    prompt_builder.py), so this reads the real thing straight from pipeline
    state — no second, independent PatternRetriever call (which used to cost
    an extra embedding request and could theoretically disagree with reality).
    """
    learning_ctx = result.get("learning_context")
    if learning_ctx is None:
        return {}
    return {
        "would_inject": not learning_ctx.is_empty(),
        "proven_plays": learning_ctx.proven_plays,
        "winning_expressions": learning_ctx.winning_expressions,
        "anti_expressions": learning_ctx.anti_expressions,
        "behavior_rules": learning_ctx.behavior_rules,
        "prompt_block_preview": learning_ctx.to_prompt_block(),
    }


def _build_debug(result: dict) -> TestDebugInfo:
    debug = TestDebugInfo()

    knowledge = result.get("knowledge")
    if knowledge and getattr(knowledge, "documents", None):
        for doc in knowledge.documents:
            debug.knowledge_retrieved.append(
                RetrievedDocument(
                    title=doc.get("title", ""),
                    excerpt=(doc.get("content", "") or "")[:200],
                    category=doc.get("category", ""),
                    source=doc.get("source", "permanent"),
                    distance=doc.get("distance"),
                )
            )

    response_plan = result.get("response_plan")
    if response_plan and getattr(response_plan, "supporting_points", None):
        debug.knowledge_injected = list(response_plan.supporting_points)

    identity = result.get("identity")
    if identity is not None:
        debug.identity_loaded = {
            "name": identity.name,
            "communication_style": identity.communication_style,
            "principles": identity.principles,
            "beliefs": identity.beliefs,
            "values": identity.values,
            "words_never_use": identity.words_never_use,
            "words_prefer": identity.words_prefer,
        }

    strategy = result.get("strategy")
    if strategy is not None:
        stype = getattr(strategy, "strategy_type", None)
        debug.strategy = {
            "strategy_type": stype.value if hasattr(stype, "value") else str(stype or ""),
            "tactic_instruction": getattr(strategy, "tactic_instruction", ""),
            "reasoning": getattr(strategy, "reasoning", ""),
            "scores": getattr(strategy, "scores", {}) or {},
        }

    analysis = result.get("analysis")
    if analysis is not None and hasattr(analysis, "intent"):
        debug.analysis = {
            "intent": str(analysis.intent.intent),
            "sentiment": str(analysis.sentiment.sentiment),
            "language": str(analysis.language.language),
            "stage": str(analysis.stage.stage),
            "urgency": str(analysis.urgency.level),
        }

    route = result.get("route")
    if route is not None and hasattr(route, "path"):
        debug.route = str(route.path)

    execution: PipelineExecution | None = result.get("execution")
    if execution is not None:
        total_tokens = sum(c.total_tokens for c in execution.llm_calls)
        debug.execution = {
            "nodes": len(execution.nodes),
            "total_ms": execution.total_ms,
            "llm_calls": len(execution.llm_calls),
            "total_tokens": total_tokens,
        }

    return debug


@router.post("/agents/{agent_version_id}/test-conversation", response_model=TestMessageResponse)
async def test_conversation(
    agent_version_id: UUID,
    body: TestMessageRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Run one isolated test turn. Persists nothing about the conversation."""
    agent_context = await _load_test_agent_context(session, agent_version_id)

    cache = get_redis_cache()
    # Reuse the request session (so the pipeline sees the uncommitted temp docs).
    sf = live_session_factory(session)
    personality_provider = AgentPersonalityProvider(sf, cache)
    rule_provider = AgentRuleProvider(sf, cache)
    strategy_provider = AgentStrategyProvider(sf, cache)
    prompt_provider = AgentPromptProvider(sf, cache)
    voice_provider = AgentVoiceProvider(sf, cache)
    identity_provider = AgentIdentityProvider(sf, cache)

    # Unscoped permanent store so the agent's training docs (organization_id
    # NULL) are retrievable; hybrid engine filters by agent afterwards.
    permanent_store = PGVectorStore(session)
    temporary_store = await _build_temporary_store(
        permanent_store, body.company_name, body.documents, body.quick_facts
    )
    hybrid_engine = HybridKnowledgeEngine(
        permanent_store=permanent_store,
        temporary_store=temporary_store,
        agent_version_id=agent_version_id,
    )

    ephemeral_memory = EphemeralMemoryEngine(
        history=[t.model_dump() for t in body.history],
        quick_facts={},  # exposed via RAG synthetic doc, not as client facts
    )

    primary_llm = create_llm_provider()
    analyzer_llm = create_analyzer_llm()

    # Trained plays/expressions/behavior rules DO apply here: the Test
    # Playground is meant to chat with the trained agent, just without
    # persisting anything (see module docstring).
    from prosales.engines.knowledge.pattern_retriever import PatternRetriever

    pattern_retriever = PatternRetriever(sf)

    try:
        graph = build_cognitive_graph(
            primary_llm=primary_llm,
            analyzer_llm=analyzer_llm,
            session_factory=sf,
            analyzer_model=settings.analyzer_llm_model,
            event_store=None,
            personality_provider=personality_provider,
            rule_provider=rule_provider,
            strategy_provider=strategy_provider,
            prompt_provider=prompt_provider,
            voice_provider=voice_provider,
            identity_provider=identity_provider,
            use_episodic=False,
            pattern_retriever=pattern_retriever,
            knowledge_engine=hybrid_engine,
            memory_engine=ephemeral_memory,
            persist_messages=False,
        )
        compiled = graph.compile()

        execution = PipelineExecution(
            conversation_id=uuid4(),
            client_id=uuid4(),
            started_at=datetime.now(timezone.utc),
            versions=Versions(
                pipeline=settings.pipeline_version,
                prompt=settings.prompt_version,
            ),
        )

        initial_state = {
            "conversation_id": execution.conversation_id,
            "client_id": execution.client_id,
            "current_message": body.message,
            "execution": execution,
            "agent_context": agent_context,
        }

        result = await compiled.ainvoke(initial_state)
    except Exception as e:
        logger.error("Test pipeline error: %s\n%s", e, traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Test pipeline error: {e}")

    voice_output = result.get("voice_output")
    debug = _build_debug(result)
    debug.learning_context = _learning_context_for_debug(result)
    return TestMessageResponse(
        response=result.get("response", ""),
        voice_ssml=voice_output.ssml if voice_output else None,
        debug=debug,
    )


# --------------------------------------------------------------------------- #
# Handoff to Training (creates an unprocessed draft)
# --------------------------------------------------------------------------- #

@router.post("/testing/handoff", response_model=HandoffResponse)
async def handoff_to_training(
    body: HandoffRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """Create a Training draft from a test conversation without extracting."""
    if not body.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript is empty")

    session_id = uuid4()
    label = body.source_label or f"Test playground {datetime.utcnow():%Y-%m-%d %H:%M}"
    draft = LearningSessionModel(
        id=session_id,
        agent_version_id=body.agent_version_id,
        source_label=label,
        transcript=body.transcript,
        source_type="text",
        status="draft",
    )
    session.add(draft)
    await session.flush()
    return HandoffResponse(session_id=session_id, status="draft")
