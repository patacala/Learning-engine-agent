"""Organization domain models."""

from uuid import UUID

from pydantic import BaseModel, Field


class OrganizationConfig(BaseModel):
    """Lightweight tenant config. Business details live in the CRM."""

    organization_id: UUID
    name: str
    capabilities: list[str] = Field(default_factory=list)

    def has_capability(self, cap: str) -> bool:
        return cap in self.capabilities
