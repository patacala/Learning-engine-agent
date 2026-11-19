"""DTOs for the Expressions layer."""

from uuid import UUID

from pydantic import BaseModel, Field


def normalize_phrase(phrase: str) -> str:
    """Lowercased, whitespace-collapsed key used to dedup expressions."""
    return " ".join(phrase.lower().split())[:500]


class ExpressionCandidate(BaseModel):
    """What the LLM returns: an anchor to an agent turn + classification."""

    turn_index: int
    polarity: str = "winning"  # winning | anti
    goal: str = ""
    stage: str = ""
    quote: str = ""  # LLM's quote; validated as a substring of the real turn


class Expression(BaseModel):
    """A materialized exact phrase (verbatim) ready to persist/aggregate."""

    id: UUID | None = None
    agent_version_id: UUID | None = None
    organization_id: UUID | None = None
    exact_phrase: str
    polarity: str = "winning"
    goal: str = ""
    stage: str = ""
    score: float = 0.0
    contexts: list = Field(default_factory=list)
    conversation_ids: list = Field(default_factory=list)
    agent_ids: list = Field(default_factory=list)
    times_used: int = 1
    success_rate: float = 0.0
    avg_score: float = 0.0
