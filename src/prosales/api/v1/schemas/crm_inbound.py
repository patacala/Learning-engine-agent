"""Schema for the CRM's agent_trigger webhook payload (event_type=message.received).

Mirrors the `n8nPayload` shape built in the CRM's agent-trigger.processor.ts —
ProSales is just another possible target for that same webhook, selected as
the single active automation agent for this event (see CLAUDE.md context).
"""

from uuid import UUID

from pydantic import BaseModel, Field


class CRMInboundContact(BaseModel):
    id: str
    first_name: str = ""
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    lead_stage: str | None = None
    tags: list[str] = Field(default_factory=list)


class CRMInboundAppointment(BaseModel):
    id: str
    title: str | None = None
    starts_at: str | None = None
    ends_at: str | None = None
    status: str | None = None
    location: str | None = None
    meeting_url: str | None = None


class CRMInboundPaymentService(BaseModel):
    id: str
    name: str
    description: str | None = None
    amount: float | None = None
    currency: str | None = None


class CRMInboundPayload(BaseModel):
    message: str
    channel: str


class CRMInboundRequest(BaseModel):
    organization_id: str
    event_type: str
    conversation_id: UUID
    contact_id: str | None = None
    agent_id: str | None = None
    payload: CRMInboundPayload
    contact: CRMInboundContact | None = None
    upcoming_appointments: list[CRMInboundAppointment] = Field(default_factory=list)
    payment_services: list[CRMInboundPaymentService] = Field(default_factory=list)
    payment_currency: str = "usd"
