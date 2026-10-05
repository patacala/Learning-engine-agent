"""Neutral fallback system prompt: when an agent has no stored templates, the
role must come from its identity — never the old hardcoded 'vehicle dealership'
sales role that flattened every agent into a car seller."""

from types import SimpleNamespace

import pytest

from prosales.engines.response.prompt_builder import PromptBuilder


def _identity(name, description):
    return SimpleNamespace(
        name=name, description=description, prompt_context="", language_context="",
    )


@pytest.mark.asyncio
async def test_fallback_uses_identity_role_not_dealership():
    state = {
        "current_message": "hola",
        "identity": _identity("Technical Support", "AI-powered technical service specialist"),
    }
    result = await PromptBuilder().process(state)  # no prompt_provider → fallback path
    system_msg = result["prompt_messages"][0].content.lower()

    assert "technical support" in system_msg
    assert "vehicle dealership" not in system_msg
    assert "sales assistant" not in system_msg


@pytest.mark.asyncio
async def test_fallback_without_identity_is_generic_not_sales():
    state = {"current_message": "hola"}
    result = await PromptBuilder().process(state)
    system_msg = result["prompt_messages"][0].content.lower()

    assert "a helpful conversational assistant" in system_msg
    assert "vehicle dealership" not in system_msg


def test_fallback_role_helper():
    b = PromptBuilder()
    assert b._fallback_role(_identity("Advisor", "AI advisor")) == "Advisor, AI advisor"
    assert b._fallback_role(_identity("Advisor", "")) == "Advisor"
    assert b._fallback_role(None) == "a helpful conversational assistant"
