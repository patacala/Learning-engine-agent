"""AgentIdentity DTO — defines who the agent is, never what to do."""

from pydantic import BaseModel, Field


class AgentIdentity(BaseModel):
    """Pure DTO. Defines who the agent is, never what to do."""

    name: str = ""
    description: str = ""
    communication_style: str = "consultive"
    compliance_notes: str = ""
    principles: list[str] = Field(default_factory=list)
    beliefs: list[str] = Field(default_factory=list)
    values: list[str] = Field(default_factory=list)
    words_never_use: list[str] = Field(default_factory=list)
    words_prefer: list[str] = Field(default_factory=list)

    @property
    def prompt_context(self) -> str:
        """Representation ready for PromptBuilder. No logic, just formatting."""
        parts = []
        if self.principles:
            parts.append("PRINCIPLES:\n" + "\n".join(f"- {p}" for p in self.principles))
        if self.values:
            parts.append("VALUES:\n" + "\n".join(f"- {v}" for v in self.values))
        if self.beliefs:
            parts.append("BELIEFS:\n" + "\n".join(f"- {b}" for b in self.beliefs))
        if self.compliance_notes:
            parts.append("COMPLIANCE:\n" + self.compliance_notes)
        return "\n\n".join(parts)

    @property
    def language_context(self) -> str:
        """Language constraints ready for prompt."""
        parts = []
        if self.words_never_use:
            parts.append(f"NEVER use these words: {', '.join(self.words_never_use)}")
        if self.words_prefer:
            parts.append(f"PREFER these words: {', '.join(self.words_prefer)}")
        return "\n".join(parts)
