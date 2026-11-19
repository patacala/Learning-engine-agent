"""PromptBuilder injects learned plays / behavior rules from the retriever."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from learning_engine.engines.knowledge.pattern_retriever import LearningContext
from learning_engine.engines.response.prompt_builder import PromptBuilder


@pytest.mark.asyncio
async def test_learning_context_from_state_is_injected():
    ctx = LearningContext(
        proven_plays=[{"move_kind": "closing", "success_rate": 0.9, "excerpt": "Book it"}],
        behavior_rules=["Validate before pricing"],
    )
    state = {"current_message": "Hola", "learning_context": ctx}
    result = await PromptBuilder().process(state)
    # Learning block lives in context_msg (per-turn dynamic), not system_msg
    # (static, kept stable for OpenAI prompt caching — see prompt_builder.py).
    context_msg = result["prompt_messages"][1].content
    assert "JUGADAS QUE FUNCIONAN" in context_msg
    assert "REGLAS APRENDIDAS" in context_msg


@pytest.mark.asyncio
async def test_retriever_called_with_agent_and_injected():
    calls = {}

    class FakeRetriever:
        async def retrieve(
            self,
            agent_version_id,
            move_kinds=None,
            stage=None,
            client_state=None,
            limit=3,
            message=None,
            message_embedding=None,
        ):
            calls["agent"] = agent_version_id
            calls["move_kinds"] = move_kinds
            calls["client_state"] = client_state
            calls["message"] = message
            calls["message_embedding"] = message_embedding
            return LearningContext(winning_expressions=["Muchos clientes empezaron así"])

    avid = uuid4()
    state = {
        "current_message": "Hola",
        "agent_context": SimpleNamespace(agent_version_id=avid, timezone="UTC"),
        "strategy": SimpleNamespace(strategy_type="consultive", tactic_instruction=""),
    }
    result = await PromptBuilder(pattern_retriever=FakeRetriever()).process(state)
    context_msg = result["prompt_messages"][1].content
    assert "FRASES GANADORAS" in context_msg
    assert calls["agent"] == avid
    # "consultive" strategy maps to discovery move kinds via the bridge.
    assert "discovery" in calls["move_kinds"]


@pytest.mark.asyncio
async def test_retriever_failure_is_non_fatal():
    class BoomRetriever:
        async def retrieve(self, *a, **k):
            raise RuntimeError("db down")

    state = {
        "current_message": "Hola",
        "agent_context": SimpleNamespace(agent_version_id=uuid4(), timezone="UTC"),
    }
    # Should not raise; reply still built.
    result = await PromptBuilder(pattern_retriever=BoomRetriever()).process(state)
    assert result["prompt_messages"][-1].content == "Hola"
