"""Test that PromptBuilder injects the learned style block."""

import pytest

from learning_engine.engines.identity_learning.models import AgentStyleProfile
from learning_engine.engines.response.prompt_builder import PromptBuilder


@pytest.mark.asyncio
async def test_style_profile_appended_to_system_message():
    profile = AgentStyleProfile(
        question_ratio=0.8,
        empathy_level=0.7,
        microexpressions=[{"phrase": "Excelente", "frequency": 0.5}],
    )
    state = {"current_message": "Hola", "style_profile": profile}

    result = await PromptBuilder().process(state)
    system = result["prompt_messages"][0].content
    assert "ESTILO APRENDIDO" in system
    assert "Excelente" in system


@pytest.mark.asyncio
async def test_no_style_profile_leaves_prompt_unchanged():
    state = {"current_message": "Hola"}
    result = await PromptBuilder().process(state)
    system = result["prompt_messages"][0].content
    assert "ESTILO APRENDIDO" not in system
