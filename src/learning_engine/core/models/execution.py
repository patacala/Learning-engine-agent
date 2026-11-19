"""Pipeline execution tracing models for observability."""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class NodeTrace(BaseModel):
    """Trace for a single pipeline node execution."""

    node_id: str
    started_at: datetime
    finished_at: datetime
    duration_ms: float
    status: str  # "success" | "error" | "skipped"
    error: str | None = None
    # Real HTTP-level ground truth for any LLM/embedding calls made during
    # this node (infrastructure/llm/observability.py) — lets latency analysis
    # tell "one slow API round-trip" apart from "the SDK silently retried and
    # the retries summed up", which look identical from duration_ms alone.
    http_attempts: int = 0
    http_retry_count: int = 0
    http_max_elapsed_ms: float | None = None


class LLMCall(BaseModel):
    """Trace for a single LLM API call."""

    provider: str  # "openai", "anthropic"
    model: str  # "gpt-4o", "gpt-4o-mini"
    temperature: float
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    duration_ms: float = 0


class Versions(BaseModel):
    """Version tracking for pipeline, prompt, and model."""

    pipeline: str = "1.0.0"
    prompt: str = "response_v1"
    model: str = ""  # filled with the model used


class RuleEvaluation(BaseModel):
    """Result of evaluating a single business rule."""

    rule: str  # "intent_objection_v1", "negative_sentiment"
    matched: bool
    confidence: float = 1.0
    reason: str = ""  # "Client mentioned price is too high"


class DecisionTrace(BaseModel):
    """Trace of the decision engine's rule evaluation."""

    actions: list[str] = Field(default_factory=list)
    evaluations: list[RuleEvaluation] = Field(default_factory=list)
    total_rules_evaluated: int = 0


class StrategyTrace(BaseModel):
    """Trace of strategy selection with scoring."""

    selected: str = ""  # "price_defense"
    candidates: list[str] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
    reason: str = ""  # "Intent=objection, mapped to price_defense"
    switched: bool = False  # True if strategy was switched


class PipelineExecution(BaseModel):
    """Complete pipeline execution trace — travels in state, persisted in events."""

    # IDs
    trace_id: UUID = Field(default_factory=uuid4)
    request_id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID | None = None
    client_id: UUID | None = None

    # Timing
    started_at: datetime | None = None
    finished_at: datetime | None = None
    total_ms: float = 0

    # Traces per node
    nodes: list[NodeTrace] = Field(default_factory=list)

    # Decision & Strategy
    decision: DecisionTrace | None = None
    strategy: StrategyTrace | None = None

    # LLM calls
    llm_calls: list[LLMCall] = Field(default_factory=list)

    # Versions
    versions: Versions = Field(default_factory=Versions)

    # Events emitted during this pipeline
    events_emitted: list[str] = Field(default_factory=list)

    # Buffered domain events, flushed to DB once at the end (excluded from dumps).
    pending_events: list = Field(default_factory=list, exclude=True)
