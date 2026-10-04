"""BriefExtractor: turns an LLM JSON blob into validated config payloads,
dropping anything the engine wouldn't recognize (unknown strategy_type, unknown
intent trigger, tactics without an instruction)."""

import pytest

from prosales.services.brief_extractor import BriefExtractor


class FakeLLM:
    def __init__(self, payload):
        self._payload = payload
        self.seen = None

    async def complete_json(self, messages, model=None, temperature=0.3):
        self.seen = messages
        return self._payload


@pytest.mark.asyncio
async def test_extract_happy_path():
    llm = FakeLLM(
        {
            "identity": {"name": "Audi Sales", "description": "Premium car sales"},
            "personality": {"brand_tone": "Warm but professional"},
            "rules": [{"rule_id": "greet", "intent": "greeting", "action_type": "greet", "priority": 10}],
            "strategies": [
                {
                    "strategy_type": "consultive",
                    "name": "Consultive Selling",
                    "description": "Understand needs first",
                    "triggers": [{"intent": "inquiry"}],
                    "tactics": [{"name": "discover", "prompt_instruction": "Ask open questions."}],
                }
            ],
        }
    )
    result = await BriefExtractor(llm).extract("We sell premium Audis in Miami.")

    assert result.identity.name == "Audi Sales"
    assert result.personality.brand_tone == "Warm but professional"
    assert len(result.rules) == 1 and result.rules[0].intent == "greeting"
    assert len(result.strategies) == 1
    assert result.strategies[0].strategy_type == "consultive"
    assert result.strategies[0].tactics[0].position == 0


@pytest.mark.asyncio
async def test_extract_drops_unknown_strategy_type():
    llm = FakeLLM(
        {
            "identity": {"name": "X"},
            "personality": {},
            "rules": [],
            "strategies": [
                {"strategy_type": "make_it_up", "name": "Bogus", "tactics": []},
                {
                    "strategy_type": "price_defense",
                    "name": "Price Defense",
                    "tactics": [{"name": "reframe", "prompt_instruction": "Reframe to value."}],
                },
            ],
        }
    )
    result = await BriefExtractor(llm).extract("brief")

    types = [s.strategy_type for s in result.strategies]
    assert types == ["price_defense"]  # bogus one dropped


@pytest.mark.asyncio
async def test_extract_drops_unknown_intent_trigger_and_empty_tactics():
    llm = FakeLLM(
        {
            "identity": {"name": "X"},
            "personality": {},
            "rules": [{"rule_id": "r1", "intent": "not_a_real_intent", "action_type": "inform"}],
            "strategies": [
                {
                    "strategy_type": "rapport_building",
                    "name": "Rapport",
                    "triggers": [{"intent": "greeting"}, {"intent": "bogus"}],
                    "tactics": [
                        {"name": "warm", "prompt_instruction": "Greet warmly."},
                        {"name": "empty", "prompt_instruction": ""},
                    ],
                }
            ],
        }
    )
    result = await BriefExtractor(llm).extract("brief")

    # Rule kept, but the unknown intent filter is nulled (not dropped entirely).
    assert result.rules[0].intent is None
    strat = result.strategies[0]
    assert [t["intent"] for t in strat.triggers] == ["greeting"]  # bogus trigger dropped
    assert len(strat.tactics) == 1  # empty-instruction tactic dropped


@pytest.mark.asyncio
async def test_extract_tolerates_missing_sections():
    result = await BriefExtractor(FakeLLM({})).extract("brief")
    assert result.identity.name  # falls back to a default name
    assert result.rules == []
    assert result.strategies == []
