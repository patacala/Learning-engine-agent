"""Tests for AgentIdentity DTO."""

from prosales.core.models.identity import AgentIdentity


class TestAgentIdentityDefaults:
    def test_defaults(self):
        identity = AgentIdentity()
        assert identity.name == ""
        assert identity.communication_style == "consultive"
        assert identity.principles == []
        assert identity.values == []
        assert identity.words_never_use == []

    def test_prompt_context_empty_when_no_data(self):
        identity = AgentIdentity()
        assert identity.prompt_context == ""

    def test_prompt_context_with_principles_values_beliefs(self):
        identity = AgentIdentity(
            principles=["Never lie"],
            values=["Honesty > sale"],
            beliefs=["Silence is powerful"],
            compliance_notes="GDPR required",
        )
        ctx = identity.prompt_context
        assert "PRINCIPLES:" in ctx
        assert "- Never lie" in ctx
        assert "VALUES:" in ctx
        assert "- Honesty > sale" in ctx
        assert "BELIEFS:" in ctx
        assert "- Silence is powerful" in ctx
        assert "COMPLIANCE:" in ctx
        assert "GDPR required" in ctx

    def test_language_context_empty_when_no_data(self):
        identity = AgentIdentity()
        assert identity.language_context == ""

    def test_language_context_with_words(self):
        identity = AgentIdentity(
            words_never_use=["cheap", "discount"],
            words_prefer=["investment", "value"],
        )
        ctx = identity.language_context
        assert "NEVER use these words: cheap, discount" in ctx
        assert "PREFER these words: investment, value" in ctx
