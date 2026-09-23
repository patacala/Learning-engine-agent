"""DTOs for the Evidence layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EvidenceTurn(BaseModel):
    """One exact turn of a conversation. Immutable source of truth."""

    turn_index: int
    speaker: str  # "agent" | "client"
    text: str
    timestamp: datetime | None = None


class EvidenceSource(BaseModel):
    """A parsed conversation (expert transcript or live) with its turns."""

    id: UUID | None = None
    source_type: str = "expert_transcript"  # expert_transcript | live_conversation | playground
    agent_version_id: UUID | None = None
    organization_id: UUID | None = None
    conversation_id: UUID | None = None
    session_id: UUID | None = None
    outcome: str = "pending"
    outcome_score: float | None = None
    turns: list[EvidenceTurn] = Field(default_factory=list)

    def agent_turns(self) -> list[EvidenceTurn]:
        return [t for t in self.turns if t.speaker == "agent"]

    def turn_at(self, index: int) -> EvidenceTurn | None:
        for t in self.turns:
            if t.turn_index == index:
                return t
        return None

    def excerpt(self, start: int, end: int) -> str:
        """Verbatim multi-turn excerpt, speaker-labelled, from start..end inclusive."""
        label = {"agent": "Agente", "client": "Cliente"}
        parts = [
            f"{label.get(t.speaker, t.speaker.capitalize())}: {t.text}"
            for t in self.turns
            if start <= t.turn_index <= end
        ]
        return "\n".join(parts)
