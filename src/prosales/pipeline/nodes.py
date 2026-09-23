"""Node wrappers that connect engines to the LangGraph pipeline."""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine

from prosales.core.enums import ConversationPath, MessageRole
from prosales.core.models.events import (
    AnalyzerCompleted,
    DecisionMade,
    DomainEvent,
    KnowledgeRetrieved,
    PipelineCompleted,
    ResponseGenerated,
    StrategyEvaluated,
    StrategySelected,
)
from prosales.core.models.execution import (
    DecisionTrace,
    LLMCall,
    NodeTrace,
    PipelineExecution,
    StrategyTrace,
    Versions,
)
from prosales.engines.learning.event_store import EventStore
from prosales.infrastructure.database.models import MessageModel
from prosales.infrastructure.database.repositories.conversation import SQLConversationRepository
from prosales.infrastructure.llm.provider import LLMProvider
from prosales.pipeline.state import CognitivePipelineState

logger = logging.getLogger(__name__)


def _make_timed_node(
    node_id: str,
    fn: Callable[[CognitivePipelineState], Coroutine[Any, Any, dict]],
    event_store: EventStore | None = None,
    event_factory: Callable[[CognitivePipelineState, dict], DomainEvent | None] | None = None,
):
    """Wrap a node function with timing and event emission."""

    async def timed_node(state: CognitivePipelineState) -> dict:
        execution: PipelineExecution | None = state.get("execution")
        start = time.monotonic()
        started_at = datetime.now(timezone.utc)
        error_msg = None
        status = "success"

        try:
            result = await fn(state)
        except Exception as e:
            error_msg = str(e)
            status = "error"
            raise
        finally:
            end = time.monotonic()
            duration_ms = (end - start) * 1000
            finished_at = datetime.now(timezone.utc)

            node_trace = NodeTrace(
                node_id=node_id,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=round(duration_ms, 2),
                status=status,
                error=error_msg,
            )

            if execution:
                execution.nodes.append(node_trace)

        # Buffer the event (enriched now); PipelineRunner flushes them all once at
        # the end in a single short transaction — no per-node DB write during the
        # LLM-heavy pipeline. Falls back to immediate store only if a live
        # event_store was passed and there is no execution buffer.
        if event_factory and status == "success":
            try:
                event = event_factory(state, result)
                if event:
                    if execution:
                        event.conversation_id = execution.conversation_id
                        event.client_id = execution.client_id
                        event.data["trace_id"] = str(execution.trace_id)
                        event.data["versions"] = execution.versions.model_dump()
                        execution.events_emitted.append(event.event_type)
                        execution.pending_events.append(event)
                    elif event_store is not None:
                        await event_store.store(event)
            except Exception as e:
                logger.warning("Failed to emit event for node %s: %s", node_id, e)

        return result

    return timed_node


def _analyzer_event_factory(state: CognitivePipelineState, result: dict) -> DomainEvent | None:
    analysis = result.get("analysis")
    if not analysis:
        return None
    return AnalyzerCompleted(data={
        "intent": str(analysis.intent.intent),
        "intent_confidence": analysis.intent.confidence,
        "sentiment": str(analysis.sentiment.sentiment),
        "sentiment_score": analysis.sentiment.score,
        "language": str(analysis.language.language),
        "stage": str(analysis.stage.stage),
        "urgency": str(analysis.urgency.level),
    })


def _knowledge_event_factory(state: CognitivePipelineState, result: dict) -> DomainEvent | None:
    knowledge = result.get("knowledge")
    if not knowledge:
        return None
    docs = knowledge.documents if hasattr(knowledge, "documents") else []
    top_distance = None
    if docs:
        first = docs[0]
        top_distance = first.get("distance") if isinstance(first, dict) else getattr(first, "distance", None)
    return KnowledgeRetrieved(data={
        "query": knowledge.query_used if hasattr(knowledge, "query_used") else "",
        "num_documents": len(docs),
        "top_distance": top_distance,
    })


def _decision_event_factory(state: CognitivePipelineState, result: dict) -> DomainEvent | None:
    decision = result.get("decision")
    if not decision:
        return None
    trace = DecisionTrace(
        actions=[a.type for a in decision.actions],
        evaluations=decision.evaluations,
        total_rules_evaluated=len(decision.evaluations),
    )
    # Also set on execution
    execution: PipelineExecution | None = state.get("execution")
    if execution:
        execution.decision = trace
    return DecisionMade(data=trace.model_dump())


def _strategy_event_factory(state: CognitivePipelineState, result: dict) -> DomainEvent | None:
    strategy = result.get("strategy")
    if not strategy:
        return None
    trace = StrategyTrace(
        selected=strategy.strategy_type.value,
        candidates=strategy.candidates,
        scores=strategy.scores,
        reason=strategy.reasoning,
        switched=strategy.switched,
    )
    # Also set on execution
    execution: PipelineExecution | None = state.get("execution")
    if execution:
        execution.strategy = trace
    return StrategySelected(data=trace.model_dump())


def create_remember_node(engine, event_store: EventStore | None = None):
    async def remember(state: CognitivePipelineState) -> dict:
        return await engine.process(state)
    return _make_timed_node("remember", remember, event_store)


def create_context_build_node(engine, event_store: EventStore | None = None):
    async def context_build(state: CognitivePipelineState) -> dict:
        return await engine.process(state)
    return _make_timed_node("context_build", context_build, event_store)


def create_analyze_node(orchestrator, event_store: EventStore | None = None):
    async def analyze(state: CognitivePipelineState) -> dict:
        result = await orchestrator.process(state)
        # Capture initial_sentiment for LearningEngine (only on first analysis)
        if "initial_sentiment" not in state:
            analysis = result.get("analysis")
            if analysis and hasattr(analysis, "sentiment"):
                result["initial_sentiment"] = analysis.sentiment.sentiment.value
        return result
    return _make_timed_node("analyze", analyze, event_store, _analyzer_event_factory)


def create_route_node(engine, event_store: EventStore | None = None):
    async def route(state: CognitivePipelineState) -> dict:
        return await engine.process(state)
    return _make_timed_node("route", route, event_store)


def create_identity_node(engine, event_store: EventStore | None = None):
    async def identify(state: CognitivePipelineState) -> dict:
        return await engine.process(state)
    return _make_timed_node("identify", identify, event_store)


def create_knowledge_node(engine, event_store: EventStore | None = None):
    async def retrieve(state: CognitivePipelineState) -> dict:
        return await engine.process(state)
    return _make_timed_node("retrieve", retrieve, event_store, _knowledge_event_factory)


def create_decision_node(engine, event_store: EventStore | None = None):
    async def decide(state: CognitivePipelineState) -> dict:
        return await engine.process(state)
    return _make_timed_node("decide", decide, event_store, _decision_event_factory)


def create_strategy_node(engine, event_store: EventStore | None = None):
    async def strategize(state: CognitivePipelineState) -> dict:
        return await engine.process(state)
    return _make_timed_node("strategize", strategize, event_store, _strategy_event_factory)


def create_plan_node(engine, event_store: EventStore | None = None):
    async def plan(state: CognitivePipelineState) -> dict:
        return await engine.process(state)
    return _make_timed_node("plan", plan, event_store)


def create_personality_node(engine, event_store: EventStore | None = None):
    async def personify(state: CognitivePipelineState) -> dict:
        return await engine.process(state)
    return _make_timed_node("personify", personify, event_store)


def create_response_planner_node(engine, event_store: EventStore | None = None):
    async def response_plan(state: CognitivePipelineState) -> dict:
        return await engine.process(state)
    return _make_timed_node("response_plan", response_plan, event_store)


def create_prompt_builder_node(engine, event_store: EventStore | None = None):
    async def build_prompt(state: CognitivePipelineState) -> dict:
        return await engine.process(state)
    return _make_timed_node("build_prompt", build_prompt, event_store)


def create_llm_call_node(llm: LLMProvider, model: str | None = None, event_store: EventStore | None = None):
    async def llm_call(state: CognitivePipelineState) -> dict:
        messages = state.get("prompt_messages", [])
        if not messages:
            return {"llm_response": ""}

        start = time.monotonic()
        response = await llm.complete(messages, model=model)
        duration_ms = (time.monotonic() - start) * 1000

        # Record LLM call in execution
        execution: PipelineExecution | None = state.get("execution")
        usage = response.usage or {}
        llm_call_trace = LLMCall(
            provider="openai",  # TODO: detect from provider
            model=response.model,
            temperature=0.7,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            duration_ms=round(duration_ms, 2),
        )
        if execution:
            execution.llm_calls.append(llm_call_trace)
            execution.versions.model = response.model

        return {"llm_response": response.content}

    def _llm_event_factory(state: CognitivePipelineState, result: dict) -> DomainEvent | None:
        execution: PipelineExecution | None = state.get("execution")
        if not execution or not execution.llm_calls:
            return None
        last_call = execution.llm_calls[-1]
        return ResponseGenerated(data={
            "provider": last_call.provider,
            "model": last_call.model,
            "prompt_tokens": last_call.prompt_tokens,
            "completion_tokens": last_call.completion_tokens,
            "total_tokens": last_call.total_tokens,
            "duration_ms": last_call.duration_ms,
        })

    return _make_timed_node("llm_call", llm_call, event_store, _llm_event_factory)


def create_post_processor_node(engine, event_store: EventStore | None = None):
    async def post_process(state: CognitivePipelineState) -> dict:
        return await engine.process(state)
    return _make_timed_node("post_process", post_process, event_store)


def create_voice_node(engine, event_store: EventStore | None = None):
    async def voice_layer(state: CognitivePipelineState) -> dict:
        return await engine.process(state)
    return _make_timed_node("voice_layer", voice_layer, event_store)


async def _qualify_contact(conversation, analysis, session) -> dict:
    """Per-contact qualification (universal signals) + persist facts to memory."""
    from prosales.engines.contact_qualification.engine import ContactQualificationEngine
    from prosales.engines.contact_qualification.models import ContactQualification
    from prosales.infrastructure.database.repositories.client import SQLClientRepository
    from prosales.infrastructure.database.repositories.contact_qualification import (
        SQLContactQualificationRepository,
    )

    repo = SQLContactQualificationRepository(session)
    prior = await repo.get_by_client(conversation.client_id) or ContactQualification()
    prior.client_id = conversation.client_id
    prior.organization_id = conversation.organization_id

    qual = ContactQualificationEngine().qualify(prior, analysis, conversation.outcome)
    qual.last_conversation_id = conversation.id
    await repo.upsert(qual)

    # Extracted facts → ClientMemory (feeds the agent's critical_facts too).
    facts = analysis.contact_signals.facts or {}
    if facts:
        client_repo = SQLClientRepository(session)
        for key, value in facts.items():
            if value:
                await client_repo.save_memory(conversation.client_id, key, str(value))

    return qual.to_public()


def create_store_node(
    session_factory=None,
    event_store: EventStore | None = None,
    persist: bool = True,
):
    """Final node: applies ALL deferred writes for the turn in ONE short
    transactional session (user message + assistant message + qualification).

    No DB connection is held during the earlier LLM-heavy nodes; the connection
    is only acquired here, at the end, for a single all-or-nothing commit.
    ``persist=False`` (Test Playground) skips every write. ``session_factory``
    None also skips writes (defensive).
    """

    async def store(state: CognitivePipelineState) -> dict:
        conversation_id = state["conversation_id"]
        response = state.get("response", "")
        analysis = state.get("analysis")

        # Get language from analysis safely
        language = "es"
        if analysis and hasattr(analysis, "language"):
            language = str(analysis.language.language)

        # Finalize execution timing (in-memory only).
        execution: PipelineExecution | None = state.get("execution")
        if execution:
            execution.finished_at = datetime.now(timezone.utc)
            if execution.started_at:
                execution.total_ms = round(
                    (execution.finished_at - execution.started_at).total_seconds() * 1000, 2
                )

        if not persist or session_factory is None:
            return {}

        from prosales.core.enums import Outcome
        from prosales.engines.qualification.engine import QualificationEngine

        out: dict = {}
        # One short transaction for every write of this turn (all-or-nothing).
        async with session_factory() as s:
            async with s.begin():
                conversation_repo = SQLConversationRepository(s)

                # Deferred user message (added first → earlier utcnow timestamp,
                # preserving user→assistant ordering). Skipped for synthetic
                # turns (voice greeting/silence) via store_user_message=False.
                if state.get("store_user_message", True):
                    user_msg = MessageModel(
                        conversation_id=conversation_id,
                        role=MessageRole.USER.value,
                        content=state.get("current_message", ""),
                    )
                    await conversation_repo.add_message(user_msg)

                assistant_msg = MessageModel(
                    conversation_id=conversation_id,
                    role=MessageRole.ASSISTANT.value,
                    content=response,
                    language=language,
                )
                await conversation_repo.add_message(assistant_msg)

                # Cognition qualification: infer the conversation outcome.
                if analysis is not None:
                    conversation = await conversation_repo.get_by_id(conversation_id)
                    if conversation is not None:
                        prior = conversation.outcome or "open"
                        result = QualificationEngine().qualify(analysis, prior)
                        conversation.outcome = result.outcome.value
                        conversation.outcome_confidence = result.confidence
                        conversation.updated_at = datetime.utcnow()  # naive column

                        # Per-contact qualification (funnel-agnostic) for the CRM.
                        contact_public = await _qualify_contact(conversation, analysis, s)

                        out = {
                            "outcome": result.outcome.value,
                            "contact_qualification": contact_public,
                        }
                        terminal_values = {o.value for o in Outcome.terminal()}
                        # Learn on the FIRST transition into a terminal state.
                        if (
                            result.is_terminal
                            and prior not in terminal_values
                            and conversation.learned_at is None
                        ):
                            out["qualification_terminal"] = True

        return out

    def _pipeline_event_factory(state: CognitivePipelineState, result: dict) -> DomainEvent | None:
        execution: PipelineExecution | None = state.get("execution")
        if not execution:
            return None
        return PipelineCompleted(data=execution.model_dump(mode="json"))

    return _make_timed_node("store", store, event_store, _pipeline_event_factory)


def _learning_event_factory(state: CognitivePipelineState, result: dict) -> DomainEvent | None:
    learning = result.get("learning")
    if not learning:
        return None
    return StrategyEvaluated(data=learning)


def create_learn_node(engine, event_store: EventStore | None = None):
    async def learn(state: CognitivePipelineState) -> dict:
        return await engine.process(state)
    # No event_factory: LearningEngine.process buffers its own (richer) event.
    return _make_timed_node("learn", learn, event_store)
