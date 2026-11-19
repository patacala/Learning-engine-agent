"""Tests for engines with AgentContext integration."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from learning_engine.core.models.agent import AgentContext
from learning_engine.engines.strategy.models import StrategySelection


def _make_agent_context(
    org_capabilities=None,
    agent_capabilities=None,
    agent_type="sales",
):
    return AgentContext(
        organization_id=uuid.uuid4(),
        organization_name="Test Org",
        org_capabilities=org_capabilities or ["knowledge"],
        agent_id=uuid.uuid4(),
        agent_version_id=uuid.uuid4(),
        agent_name="Test Agent",
        agent_type=agent_type,
        agent_capabilities=agent_capabilities or ["voice", "negotiation"],
    )


def _make_analysis():
    analysis = MagicMock()
    analysis.intent.intent = MagicMock(value="inquiry")
    analysis.sentiment.sentiment = MagicMock(value="neutral")
    analysis.language.language = "es"
    return analysis


class TestStrategyEngineCapabilityGating:
    @pytest.mark.asyncio
    async def test_skip_when_no_negotiation_capability(self):
        from learning_engine.engines.strategy.engine import StrategyEngine

        ctx = _make_agent_context(agent_capabilities=["voice"])  # No negotiation

        engine = StrategyEngine(strategy_provider=None)
        result = await engine.process({
            "analysis": _make_analysis(),
            "agent_context": ctx,
        })

        assert result["strategy"].reasoning == "negotiation capability disabled"

    @pytest.mark.asyncio
    async def test_passes_when_has_negotiation(self):
        from learning_engine.engines.strategy.engine import StrategyEngine

        ctx = _make_agent_context(agent_capabilities=["voice", "negotiation"])

        engine = StrategyEngine(strategy_provider=None)
        result = await engine.process({
            "analysis": _make_analysis(),
            "agent_context": ctx,
        })

        # Should proceed to hardcoded catalog (no provider)
        assert result["strategy"].reasoning != "negotiation capability disabled"


class TestVoiceEngineCapabilityGating:
    @pytest.mark.asyncio
    async def test_passthrough_when_no_voice_capability(self):
        from learning_engine.engines.voice.engine import VoiceLayerEngine

        ctx = _make_agent_context(agent_capabilities=["negotiation"])  # No voice

        engine = VoiceLayerEngine(voice_provider=None)
        result = await engine.process({
            "response": "Hello there",
            "analysis": _make_analysis(),
            "agent_context": ctx,
        })

        assert result["voice_output"].text == "Hello there"
        assert result["response"] == "Hello there"


class TestKnowledgeEngineCapabilityGating:
    @pytest.mark.asyncio
    async def test_skip_when_no_knowledge_capability(self):
        from learning_engine.engines.knowledge.engine import KnowledgeEngine

        ctx = _make_agent_context(org_capabilities=[])  # No knowledge in org

        mock_store = MagicMock()
        engine = KnowledgeEngine(mock_store)
        result = await engine.process({
            "current_message": "What cars do you have?",
            "agent_context": ctx,
        })

        assert result["knowledge"].documents == []
        assert result["knowledge"].query_used == "What cars do you have?"


class TestPersonalityEngineWithAgentContext:
    @pytest.mark.asyncio
    async def test_loads_personality_from_agent_version(self):
        from learning_engine.engines.personality.engine import PersonalityEngine
        from learning_engine.core.models.agent import AgentPersonalityConfig

        ctx = _make_agent_context()
        mock_provider = AsyncMock()
        mock_provider.get = AsyncMock(return_value=AgentPersonalityConfig(
            brand_traits=["premium"],
            brand_tone="Luxury",
            brand_instructions=["Be premium"],
            voice_traits=["calm"],
            voice_tone="Calm",
            voice_instructions=["Be calm"],
        ))

        engine = PersonalityEngine(personality_provider=mock_provider)
        result = await engine.process({
            "analysis": _make_analysis(),
            "agent_context": ctx,
        })

        assert result["personality"].brand.tone == "Luxury"
        mock_provider.get.assert_called_once_with(ctx.agent_version_id)


class TestDecisionEngineWithAgentContext:
    @pytest.mark.asyncio
    async def test_loads_rules_from_agent_version(self):
        from learning_engine.engines.decision.engine import DecisionEngine
        from learning_engine.core.models.agent import AgentRule

        ctx = _make_agent_context()
        mock_provider = AsyncMock()
        mock_provider.get = AsyncMock(return_value=[
            AgentRule(rule_id="r1", intent="inquiry", action_type="inform", priority=8),
        ])

        engine = DecisionEngine(rule_provider=mock_provider)
        result = await engine.process({
            "analysis": _make_analysis(),
            "agent_context": ctx,
        })

        assert result["decision"] is not None
        mock_provider.get.assert_called_once_with(ctx.agent_version_id)


class TestPromptBuilderWithAgentContext:
    @pytest.mark.asyncio
    async def test_uses_agent_version_id_for_lookup(self):
        from learning_engine.engines.response.prompt_builder import PromptBuilder

        ctx = _make_agent_context()
        mock_prompt_provider = AsyncMock()
        mock_prompt_provider.get = AsyncMock(return_value={})

        engine = PromptBuilder(
            prompt_provider=mock_prompt_provider,
        )

        result = await engine.process({
            "analysis": _make_analysis(),
            "agent_context": ctx,
            "current_message": "Hola",
            "personality": None,
            "context": None,
            "response_plan": None,
            "strategy": None,
            "plan": None,
            "identity": None,
        })

        assert "prompt_messages" in result
        mock_prompt_provider.get.assert_called_once_with(ctx.agent_version_id)
