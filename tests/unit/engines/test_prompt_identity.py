"""Tests for PromptBuilder integration with Identity."""

import pytest

from prosales.core.models.identity import AgentIdentity
from prosales.engines.response.prompt_builder import PromptBuilder


@pytest.fixture
def builder():
    return PromptBuilder()


class TestPromptBuilderIdentity:
    @pytest.mark.asyncio
    async def test_injects_prompt_context(self, builder):
        identity = AgentIdentity(
            principles=["Never lie"],
            values=["Honesty > sale"],
        )
        state = {
            "current_message": "Hello",
            "identity": identity,
        }
        result = await builder.process(state)
        system_msg = result["prompt_messages"][0].content
        assert "IDENTITY:" in system_msg
        assert "PRINCIPLES:" in system_msg
        assert "Never lie" in system_msg

    @pytest.mark.asyncio
    async def test_injects_language_context(self, builder):
        identity = AgentIdentity(
            words_never_use=["cheap"],
            words_prefer=["investment"],
        )
        state = {
            "current_message": "Hello",
            "identity": identity,
        }
        result = await builder.process(state)
        system_msg = result["prompt_messages"][0].content
        assert "LANGUAGE CONSTRAINTS:" in system_msg
        assert "cheap" in system_msg
        assert "investment" in system_msg

    @pytest.mark.asyncio
    async def test_no_identity_blocks_when_empty(self, builder):
        state = {
            "current_message": "Hello",
            "identity": AgentIdentity(),
        }
        result = await builder.process(state)
        system_msg = result["prompt_messages"][0].content
        assert "IDENTITY:" not in system_msg
        assert "LANGUAGE CONSTRAINTS:" not in system_msg
