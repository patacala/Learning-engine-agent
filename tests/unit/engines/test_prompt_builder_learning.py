"""PromptBuilder injects learned plays / behavior rules from the retriever."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from prosales.engines.knowledge.pattern_retriever import LearningContext
from prosales.engines.response.prompt_builder import PromptBuilder


@pytest.mark.asyncio
async def test_learning_context_from_state_is_injected():
    ctx = LearningContext(
        proven_plays=[{"move_kind": "closing", "success_rate": 0.9, "excerpt": "Book it"}],
        behavior_rules=["Validate before pricing"],
    )
    state = {"current_message": "Hola", "learning_context": ctx}
    result = await PromptBuilder().process(state)
    system = result["prompt_messages"][0].content
    assert "JUGADAS QUE FUNCIONAN" in system
    assert "REGLAS APRENDIDAS" in system


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
        "agent_context": SimpleNamespace(agent_version_id=avid),
        "strategy": SimpleNamespace(strategy_type="consultive", tactic_instruction=""),
    }
    result = await PromptBuilder(pattern_retriever=FakeRetriever()).process(state)
    system = result["prompt_messages"][0].content
    assert "FRASES GANADORAS" in system
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
        "agent_context": SimpleNamespace(agent_version_id=uuid4()),
    }
    # Should not raise; reply still built.
    result = await PromptBuilder(pattern_retriever=BoomRetriever()).process(state)
    assert result["prompt_messages"][-1].content == "Hola"
