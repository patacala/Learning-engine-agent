from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from prosales.core.types import JSON


class DomainEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    event_type: str
    conversation_id: UUID | None = None
    client_id: UUID | None = None
    data: JSON = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Existing event types
class MessageReceived(DomainEvent):
    event_type: str = "message.received"


class MessageSent(DomainEvent):
    event_type: str = "message.sent"


class ConversationStarted(DomainEvent):
    event_type: str = "conversation.started"


class ConversationClosed(DomainEvent):
    event_type: str = "conversation.closed"


class StrategyApplied(DomainEvent):
    event_type: str = "strategy.applied"


class StrategySwitch(DomainEvent):
    event_type: str = "strategy.switch"


# New observability event types
class AnalyzerCompleted(DomainEvent):
    event_type: str = "analyzer.completed"


class KnowledgeRetrieved(DomainEvent):
    event_type: str = "knowledge.retrieved"


class DecisionMade(DomainEvent):
    event_type: str = "decision.made"


class StrategySelected(DomainEvent):
    event_type: str = "strategy.selected"


class ResponseGenerated(DomainEvent):
    event_type: str = "response.generated"


class PipelineCompleted(DomainEvent):
    event_type: str = "pipeline.completed"


class EpisodeExtracted(DomainEvent):
    event_type: str = "episode.extracted"


class TrainingPatternExtracted(DomainEvent):
    event_type: str = "training.pattern_extracted"


class StrategyEvaluated(DomainEvent):
    event_type: str = "strategy.evaluated"
