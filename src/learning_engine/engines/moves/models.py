"""DTOs for Conversation Moves."""

from uuid import UUID

from pydantic import BaseModel, Field


class MoveAnchor(BaseModel):
    """What the LLM returns per move: indices + classification, NO verbatim text.

    The verbatim excerpt is filled in by code from the evidence turns, so the
    memory never depends on the LLM not paraphrasing.
    """

    start_turn_index: int
    end_turn_index: int
    move_kind: str
    goal: str = ""
    client_state_before: str = ""
    client_state_after: str = ""
    polarity: str = "positive"  # positive | negative
    outcome_label: str = ""
    confidence: float = 0.8
    conditions: dict = Field(default_factory=dict)


class ConversationMove(BaseModel):
    """A fully-anchored move ready to persist (transcript_excerpt is verbatim)."""

    id: UUID | None = None
    evidence_source_id: UUID | None = None
    agent_version_id: UUID | None = None
    organization_id: UUID | None = None

    start_turn_index: int = 0
    end_turn_index: int = 0
    move_kind: str = ""
    goal: str = ""
    client_state_before: str = ""
    client_state_after: str = ""
    transcript_excerpt: str = ""
    polarity: str = "positive"
    outcome_label: str = ""
    score: float = 0.0
    confidence: float = 0.8
    human_rating: float | None = None
    conditions: dict = Field(default_factory=dict)
    cluster_id: UUID | None = None
    status: str = "pending"
