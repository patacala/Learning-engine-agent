from pydantic import BaseModel, Field

from learning_engine.core.models.client import ClientMemory
from learning_engine.core.models.conversation import Message
from learning_engine.engines.episodic.models import EpisodeSummary


class WorkingMemory(BaseModel):
    """Short-term: current conversation messages."""

    messages: list[Message] = Field(default_factory=list)
    current_topic: str = ""


class EpisodicMemory(BaseModel):
    """Medium-term: past conversations summary."""

    past_conversations: list[dict] = Field(default_factory=list)
    total_interactions: int = 0
    last_interaction_summary: str = ""
    client_episodes: list[EpisodeSummary] = Field(default_factory=list)


class SemanticMemory(BaseModel):
    """Long-term: client facts and preferences."""

    facts: list[ClientMemory] = Field(default_factory=list)


class FullMemory(BaseModel):
    working: WorkingMemory = Field(default_factory=WorkingMemory)
    episodic: EpisodicMemory = Field(default_factory=EpisodicMemory)
    semantic: SemanticMemory = Field(default_factory=SemanticMemory)
