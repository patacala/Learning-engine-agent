"""DTO for per-contact qualification (universal, funnel-agnostic)."""

from uuid import UUID

from pydantic import BaseModel, Field


class ContactQualification(BaseModel):
    id: UUID | None = None
    client_id: UUID | None = None
    organization_id: UUID | None = None

    temperature: str = "cold"  # cold | warm | hot
    status: str = "unqualified"  # unqualified | qualifying | qualified
    readiness: float = 0.0
    bant: dict = Field(default_factory=dict)  # {need, budget, authority, timeline: bool}
    signals: dict = Field(default_factory=dict)  # {signal: count} accumulated
    facts: dict = Field(default_factory=dict)  # {product_interest, budget, timeline, ...}
    suggested_transition: str = "hold"  # advance | hold | disqualify | lost
    last_conversation_id: UUID | None = None

    def to_public(self) -> dict:
        """Shape emitted to the CRM (signals as a list of names)."""
        return {
            "temperature": self.temperature,
            "status": self.status,
            "readiness": self.readiness,
            "bant": self.bant,
            "signals": sorted(self.signals.keys()),
            "facts": self.facts,
            "suggested_transition": self.suggested_transition,
        }
