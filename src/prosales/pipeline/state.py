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
