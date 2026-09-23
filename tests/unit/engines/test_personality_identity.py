"""Tests for PersonalityEngine integration with Identity."""

import pytest

from prosales.core.models.analysis import AnalysisResult
from prosales.core.models.identity import AgentIdentity
from prosales.engines.personality.engine import PersonalityEngine


@pytest.fixture
def engine():
    return PersonalityEngine()


class TestPersonalityIdentityIntegration:
    @pytest.mark.asyncio
    async def test_uses_communication_style_from_identity(self, engine):
        identity = AgentIdentity(communication_style="direct")
        state = {"analysis": AnalysisResult(), "identity": identity}
        result = await engine.process(state)
        profile = result["personality"]
        assert "directo" in profile.conversation.traits

    @pytest.mark.asyncio
    async def test_fallback_to_consultive_for_unknown_style(self, engine):
        identity = AgentIdentity(communication_style="unknown_style")
        state = {"analysis": AnalysisResult(), "identity": identity}
        result = await engine.process(state)
        profile = result["personality"]
        assert "consultivo" in profile.conversation.traits

    @pytest.mark.asyncio
    async def test_identity_layer_includes_principles_and_beliefs(self, engine):
        identity = AgentIdentity(
            principles=["Never lie about the product"],
            beliefs=["Silence is powerful"],
        )
        state = {"analysis": AnalysisResult(), "identity": identity}
        result = await engine.process(state)
        profile = result["personality"]
        instructions = profile.identity.instructions
        assert any("Never lie" in i for i in instructions)
        assert any("Silence" in i for i in instructions)
        # Verify they appear in compiled instructions too
        all_instructions = profile.compile_instructions()
        assert any("Never lie" in i for i in all_instructions)
