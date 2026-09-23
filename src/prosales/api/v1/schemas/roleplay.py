"""Schemas for the roleplay training channel."""

from uuid import UUID

from pydantic import BaseModel, Field


class StartRoleplayRequest(BaseModel):
    scenario: str = Field(..., min_length=1, description="Trainer's scenario prompt")
    mode: str = Field(
        "client",
        description="Who Cognition plays: 'client' (persona) or 'agent' (seller demo)",
    )
    agent_version_id: UUID | None = Field(
        None,
        description=(
            "Optional published Cognition agent to play. Training agents are not "
            "tenant-owned; no organization API key is required. If omitted, the "
            "optional X-API-Key's primary agent is used."
        ),
    )


class StartRoleplayResponse(BaseModel):
    session_id: UUID
    mode: str
    scenario: str
    # The agent this session's learning will be attributed to (None if unresolved).
    agent_version_id: UUID | None


class RoleplayTurnRequest(BaseModel):
    text: str = Field(..., min_length=1, description="What the human just said (text)")


class RoleplayTurnResponse(BaseModel):
    session_id: UUID
    reply: str


class EndRoleplayRequest(BaseModel):
    outcome: str = Field(
        "scheduled",
        description=(
            "Outcome that drives learning. Must be one of the Outcome vocabulary: "
            "open, resolved, scheduled, abandoned, lost. Only terminal outcomes "
            "(scheduled/abandoned/lost) trigger learning; 'scheduled' (default) "
            "learns winning expressions, 'lost'/'abandoned' weight anti-patterns. "
            "Ignored when sub_outcome is given."
        ),
    )
    sub_outcome: str | None = Field(
        None,
        description=(
            "Optional scenario-flavored outcome the trainer picks instead of the "
            "coarse `outcome`: objection_handled, close_attempted, "
            "discovery_incomplete, client_disengaged, rapport_only. Overrides "
            "`outcome` via a fixed mapping to the Outcome vocabulary."
        ),
    )


class EndRoleplayResponse(BaseModel):
    session_id: UUID
    learning: bool


class RoleplayTurn(BaseModel):
    speaker: str  # "trainer" | "cognition"
    text: str


class LearnedMove(BaseModel):
    move_kind: str
    polarity: str | None
    transcript_excerpt: str
    score: float | None
    status: str


class LearnedExpression(BaseModel):
    exact_phrase: str
    polarity: str | None
    success_rate: float | None
    times_used: int


class RoleplayLearned(BaseModel):
    """What Cognition learned specifically from this roleplay session."""

    learned: bool
    learned_at: str | None
    moves_total: int
    moves_approved: int
    moves: list[LearnedMove]
    expressions: list[LearnedExpression]


class RoleplaySessionResponse(BaseModel):
    session_id: UUID
    mode: str | None
    scenario: str | None
    outcome: str
    sub_outcome: str | None
    is_active: bool
    learned: bool
    # The agent this session's learning is attributed to (None if unresolved).
    agent_version_id: UUID | None
    transcript: list[RoleplayTurn]
    learned_detail: RoleplayLearned
