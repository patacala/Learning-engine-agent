from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from typing_extensions import TypedDict

from prosales.core.models.agent import AgentContext
from prosales.core.models.analysis import AnalysisResult
from prosales.core.models.identity import AgentIdentity
from prosales.core.models.decision import Decision
from prosales.core.models.execution import PipelineExecution
from prosales.core.models.personality import PersonalityProfile
from prosales.core.models.plan import SalesPlan
from prosales.engines.context_builder.models import RelevantContext
from prosales.engines.conversation_manager.models import RouteDecision
from prosales.engines.knowledge.models import KnowledgeResult
from prosales.engines.knowledge.pattern_retriever import LearningContext
from prosales.engines.memory.models import FullMemory
from prosales.engines.response.models import GeneratedResponse, ResponsePlan
from prosales.engines.strategy.models import StrategySelection
from prosales.engines.voice.models import VoiceOutput
from prosales.infrastructure.llm.provider import LLMMessage


class CognitivePipelineState(TypedDict, total=False):
    # Input
    conversation_id: UUID
    client_id: UUID
    current_message: str

    # Agent context
    agent_context: AgentContext | None

    # External context supplied by the caller (e.g. the CRM's /crm/inbound
    # payload: contact profile, upcoming_appointments, payment_services,
    # timezone). Read-only reference data the pipeline injects into the prompt
    # and the tool loop uses — never re-queried by an engine. Absent for the
    # plain /conversation/message path.
    extra_context: dict | None

    # Identity
    identity: AgentIdentity | None

    # Memory
    memory: FullMemory

    # Context (filtered)
    context: RelevantContext

    # Analysis
    analysis: AnalysisResult

    # Routing
    route: RouteDecision

    # Knowledge (RAG)
    knowledge: KnowledgeResult
    # Embedding of `current_message`, computed once by whichever node needs it
    # first (KnowledgeEngine on full_path, or PatternRetriever via build_prompt
    # on fast_path where `retrieve` is skipped) and reused by the other — avoids
    # 2 separate OpenAI embedding round-trips for the same text in one turn
    # (measured ~200ms-2s each, same latency variance as any other OpenAI call).
    message_embedding: list[float] | None

    # Decision
    decision: Decision

    # Strategy
    strategy: StrategySelection
    current_strategy: str | None
    strategy_attempts: int
    tactic_position: int

    # Plan
    plan: SalesPlan

    # Personality
    personality: PersonalityProfile

    # Response pipeline
    response_plan: ResponsePlan
    prompt_messages: list[LLMMessage]
    llm_response: str
    response: str
    # Set only by callers that want token-level streaming (see
    # PipelineRunner.run(on_token=...) / POST /conversation/message/stream).
    # When present, the llm_call node streams and calls this per chunk instead
    # of a single blocking complete() — everything downstream (post_process,
    # store, learn) is unaffected either way, it only ever sees the final text.
    stream_callback: Callable[[str], Awaitable[None]] | None
    # In-turn Action Layer: a CRMToolExecutor the caller (crm_inbound) sets when
    # the org has CRM connectivity + the capability. When present, llm_call runs
    # a tool-use loop (LLM ⇄ CRM /ai/tools/execute) instead of a single
    # completion. Absent → plain text-only completion, as before.
    tool_executor: Any
    # Cognitive Learning Engine: what PromptBuilder retrieved/injected this
    # turn. Was previously computed and discarded — undeclared TypedDict keys
    # are silently dropped by LangGraph's state merging, so this MUST be
    # declared here for callers (PipelineRunner, Test Playground) to see it.
    learning_context: LearningContext | None

    # Voice
    voice_output: VoiceOutput

    # Learning
    initial_sentiment: str
    learning: dict

    # Qualification (Cognition-inferred outcome)
    outcome: str
    qualification_terminal: bool
    contact_qualification: dict

    # Observability
    execution: PipelineExecution
