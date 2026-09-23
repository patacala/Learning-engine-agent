from pydantic import BaseModel, Field

from prosales.core.models.conversation import Message


class RelevantContext(BaseModel):
    """Filtered, token-optimized context for current message."""

    recent_messages: list[Message] = Field(default_factory=list)
    critical_facts: list[dict] = Field(default_factory=list)
    relevant_documents: list[dict] = Field(default_factory=list)
    active_strategy: str = ""
    applicable_rules: list[str] = Field(default_factory=list)
    conversation_summary: str = ""
