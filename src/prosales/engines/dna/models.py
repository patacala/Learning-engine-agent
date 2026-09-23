"""DTO for Conversation DNA."""

from uuid import UUID

from pydantic import BaseModel

# Order of features packed into ConversationDNAModel.dna_vector (DNA_DIM = 12).
DNA_FEATURES = [
    "trust_score",
    "curiosity_score",
    "empathy_score",
    "urgency_score",
    "storytelling_score",
    "pressure_score",
    "talk_ratio",
    "conversational_balance",
    "question_density",
    "objection_density",
    "resolution_rate",
    "turn_length_norm",
]


class ConversationDNA(BaseModel):
    id: UUID | None = None
    evidence_source_id: UUID | None = None
    conversation_id: UUID | None = None
    agent_version_id: UUID | None = None
    organization_id: UUID | None = None

    trust_score: float = 0.0
    curiosity_score: float = 0.0
    empathy_score: float = 0.0
    urgency_score: float = 0.0
    storytelling_score: float = 0.0
    pressure_score: float = 0.0

    question_count: int = 0
    objection_count: int = 0
    objections_resolved: int = 0
    avg_turn_length: float = 0.0
    talk_ratio: float = 0.0
    conversational_balance: float = 0.0

    outcome: str = "pending"

    def to_vector(self) -> list[float]:
        """Pack into the 12-dim similarity vector (all features ~0-1)."""
        question_density = _soft(self.question_count, 10)
        objection_density = _soft(self.objection_count, 5)
        resolution_rate = (
            self.objections_resolved / self.objection_count if self.objection_count else 0.0
        )
        turn_length_norm = _soft(self.avg_turn_length, 40)
        return [
            self.trust_score,
            self.curiosity_score,
            self.empathy_score,
            self.urgency_score,
            self.storytelling_score,
            self.pressure_score,
            self.talk_ratio,
            self.conversational_balance,
            question_density,
            objection_density,
            min(1.0, resolution_rate),
            turn_length_norm,
        ]


def _soft(value: float, cap: float) -> float:
    """Soft-normalize a count/length to 0-1 (saturating at `cap`)."""
    if cap <= 0:
        return 0.0
    return min(1.0, value / cap)
