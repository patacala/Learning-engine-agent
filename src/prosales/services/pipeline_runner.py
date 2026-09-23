"""Shared pipeline execution — used by REST API and Voice channels."""

import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from prosales.config import settings
from prosales.core.models.agent import AgentContext
from prosales.core.models.execution import PipelineExecution, Versions
from prosales.di.container import create_analyzer_llm, create_llm_provider
from prosales.engines.learning.event_store import EventStore
from prosales.infrastructure.cache.redis import RedisCache
from prosales.infrastructure.database.repositories.event import SQLEventRepository
from prosales.infrastructure.agent.providers import (
    AgentIdentityProvider,
    AgentPersonalityProvider,
    AgentPromptProvider,
    AgentRuleProvider,
    AgentStrategyProvider,
    AgentVoiceProvider,
)
from prosales.pipeline.graph import build_cognitive_graph

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of a pipeline execution."""

    response: str
    voice_text: str
    voice_ssml: str | None = None
    analysis_summary: dict = field(default_factory=dict)
    route: str = ""
    outcome: str = "open"
    # Additive — populated for observability/eval tooling (scripts/eval_conversation.py);
    # existing callers (REST, voice) ignore these and are unaffected.
    strategy_summary: dict = field(default_factory=dict)
    learning_summary: dict = field(default_factory=dict)
    # What the agent actually had as retrieved context (RAG) for this turn —
    # the only thing an eval judge can honestly check "no_fabrication" against;
    # without it, "did it invent a price/discount/warranty" is pure guesswork.
    knowledge_summary: dict = field(default_factory=dict)
    qualification_terminal: bool = False
    contact_qualification: dict = field(default_factory=dict)


class PipelineRunner:
    """Single point of pipeline execution for REST and Voice channels.

    Holds NO live DB session: it receives a ``session_factory`` and every
    DB-touching component (memory, knowledge, providers, store, event flush)
    opens its own SHORT session, so no connection is held across the LLM nodes.
    """

    def __init__(self, session_factory, cache: RedisCache | None = None):
        self._sf = session_factory
        self.cache = cache

    async def run(
        self,
        message: str,
        client_id: UUID,
        conversation_id: UUID,
        agent_context: AgentContext | None = None,
        store_user_message: bool = True,
    ) -> PipelineResult:
        """Run the cognitive pipeline and return a structured result."""
        primary_llm = create_llm_provider()
        analyzer_llm = create_analyzer_llm()

        # Build agent providers (all session_factory-backed; DB touched only on
        # a Redis cache miss, in a short session).
        from prosales.engines.knowledge.pattern_retriever import PatternRetriever
        from prosales.infrastructure.agent.providers import AgentStyleProvider

        pattern_retriever = PatternRetriever(self._sf)

        if agent_context and self.cache:
            personality_provider = AgentPersonalityProvider(self._sf, self.cache)
            rule_provider = AgentRuleProvider(self._sf, self.cache)
            strategy_provider = AgentStrategyProvider(self._sf, self.cache)
            prompt_provider = AgentPromptProvider(self._sf, self.cache)
            voice_provider = AgentVoiceProvider(self._sf, self.cache)
            identity_provider = AgentIdentityProvider(self._sf, self.cache)
            style_provider = AgentStyleProvider(self._sf, self.cache)
        else:
            personality_provider = None
            rule_provider = None
            strategy_provider = None
            prompt_provider = None
            voice_provider = None
            identity_provider = None
            style_provider = None

        # Build and run pipeline
        graph = build_cognitive_graph(
            primary_llm=primary_llm,
            analyzer_llm=analyzer_llm,
            session_factory=self._sf,
            analyzer_model=settings.analyzer_llm_model,
            event_store=None,  # events are buffered on execution, flushed below
            personality_provider=personality_provider,
            rule_provider=rule_provider,
            strategy_provider=strategy_provider,
            prompt_provider=prompt_provider,
            voice_provider=voice_provider,
            identity_provider=identity_provider,
            style_provider=style_provider,
            pattern_retriever=pattern_retriever,
            use_episodic=True,
        )

        compiled = graph.compile()

        execution = PipelineExecution(
            conversation_id=conversation_id,
            client_id=client_id,
            started_at=datetime.now(timezone.utc),
            versions=Versions(
                pipeline=settings.pipeline_version,
                prompt=settings.prompt_version,
            ),
        )

        initial_state = {
            "conversation_id": conversation_id,
            "client_id": client_id,
            "current_message": message,
            "execution": execution,
            "agent_context": agent_context,
            "store_user_message": store_user_message,
        }

        result = await compiled.ainvoke(initial_state)

        # Flush all buffered domain events once, in a short transaction (telemetry;
        # separate from the store node's critical write so it can't roll it back).
        exec_obj = result.get("execution")
        if exec_obj and getattr(exec_obj, "pending_events", None):
            try:
                async with self._sf() as s:
                    async with s.begin():
                        store = EventStore(SQLEventRepository(s))
                        for ev in exec_obj.pending_events:
                            await store.store(ev)
            except Exception as e:
                logger.warning("Failed to flush pipeline events: %s", e)

        # Extract result
        analysis = result.get("analysis")
        analysis_dict = {}
        if analysis and hasattr(analysis, "intent"):
            analysis_dict = {
                "intent": str(analysis.intent.intent),
                "sentiment": str(analysis.sentiment.sentiment),
                "language": str(analysis.language.language),
                "stage": str(analysis.stage.stage) if getattr(analysis, "stage", None) else "",
                "urgency": str(analysis.urgency.level) if getattr(analysis, "urgency", None) else "",
            }

        voice_output = result.get("voice_output")
        route = result.get("route")
        route_str = str(route.path) if route and hasattr(route, "path") else ""

        strategy = result.get("strategy")
        strategy_dict = {}
        if strategy is not None and getattr(strategy, "strategy_type", None):
            stype = strategy.strategy_type
            strategy_dict = {
                "strategy_type": stype.value if hasattr(stype, "value") else str(stype),
                "tactic_instruction": getattr(strategy, "tactic_instruction", ""),
                "reasoning": getattr(strategy, "reasoning", ""),
            }

        knowledge = result.get("knowledge")
        knowledge_dict = {}
        if knowledge is not None and getattr(knowledge, "documents", None):
            knowledge_dict = {
                "query_used": knowledge.query_used,
                "documents": [
                    {"title": d.get("title", ""), "content": d.get("content", "")}
                    for d in knowledge.documents
                ],
            }

        learning_ctx = result.get("learning_context")
        learning_dict = {}
        if learning_ctx is not None:
            learning_dict = {
                "would_inject": not learning_ctx.is_empty(),
                "proven_plays": learning_ctx.proven_plays,
                "winning_expressions": learning_ctx.winning_expressions,
                "anti_expressions": learning_ctx.anti_expressions,
                "behavior_rules": learning_ctx.behavior_rules,
            }

        return PipelineResult(
            response=result.get("response", ""),
            voice_text=voice_output.text if voice_output else result.get("response", ""),
            voice_ssml=voice_output.ssml if voice_output else None,
            analysis_summary=analysis_dict,
            route=route_str,
            outcome=result.get("outcome", "open"),
            strategy_summary=strategy_dict,
            learning_summary=learning_dict,
            knowledge_summary=knowledge_dict,
            qualification_terminal=bool(result.get("qualification_terminal", False)),
            contact_qualification=result.get("contact_qualification", {}) or {},
        )
