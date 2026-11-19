"""Pydantic schemas for the Test Playground module."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TemporaryDocument(BaseModel):
    """A single business-context document within a scenario."""

    id: str = ""
    title: str
    content: str
    category: str = "general"


class ScenarioCreate(BaseModel):
    name: str
    company_name: str = ""
    agent_version_id: UUID | None = None
    documents: list[TemporaryDocument] = Field(default_factory=list)
    quick_facts: dict[str, str] = Field(default_factory=dict)


class ScenarioResponse(BaseModel):
    id: UUID
    agent_version_id: UUID | None = None
    name: str
    company_name: str = ""
    documents: list[TemporaryDocument] = Field(default_factory=list)
    quick_facts: dict[str, str] = Field(default_factory=dict)
    created_at: datetime | None = None


class TestTurn(BaseModel):
    role: str = "user"
    content: str


class TestMessageRequest(BaseModel):
    """A single test turn with the active (possibly unsaved) scenario context."""

    message: str
    history: list[TestTurn] = Field(default_factory=list)
    company_name: str = ""
    documents: list[TemporaryDocument] = Field(default_factory=list)
    quick_facts: dict[str, str] = Field(default_factory=dict)


class RetrievedDocument(BaseModel):
    title: str = ""
    excerpt: str = ""
    category: str = ""
    source: str = "permanent"  # scenario | permanent
    distance: float | None = None


class TestDebugInfo(BaseModel):
    # Documents the RAG step retrieved (with provenance + relevance)
    knowledge_retrieved: list[RetrievedDocument] = Field(default_factory=list)
    # Points the response planner actually injected into the prompt
    knowledge_injected: list[str] = Field(default_factory=list)
    # Identity loaded into the prompt (not "used" — just loaded)
    identity_loaded: dict = Field(default_factory=dict)
    strategy: dict = Field(default_factory=dict)
    analysis: dict = Field(default_factory=dict)
    route: str = ""
    execution: dict = Field(default_factory=dict)
    # What the Cognitive Learning Engine surfaced for this turn (proven plays /
    # winning & anti expressions / behavior rules). This IS what got injected
    # into the actual prompt that produced `response` — the Test Playground
    # runs the same trained-agent pipeline as a real conversation, just
    # without persisting anything.
    learning_context: dict = Field(default_factory=dict)


class TestMessageResponse(BaseModel):
    response: str
    voice_ssml: str | None = None
    debug: TestDebugInfo


class HandoffRequest(BaseModel):
    """Turn a test conversation into an editable Training draft (unprocessed)."""

    agent_version_id: UUID
    source_label: str = ""
    transcript: str


class HandoffResponse(BaseModel):
    session_id: UUID
    status: str = "draft"
