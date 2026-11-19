"""DTOs for the Insights layer."""

from uuid import UUID

from pydantic import BaseModel, Field


class Insight(BaseModel):
    id: UUID | None = None
    agent_version_id: UUID | None = None
    organization_id: UUID | None = None
    insight_text: str
    behavior_rule: str = ""
    supporting_cluster_ids: list = Field(default_factory=list)
    pattern_kinds: list = Field(default_factory=list)
    confidence: float = 0.0
    sample_size: int = 0
    status: str = "draft"
