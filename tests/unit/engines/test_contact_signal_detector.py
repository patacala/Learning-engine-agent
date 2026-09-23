"""Tests for ContactSignalDetector (LLM mocked)."""

import pytest

from prosales.engines.analyzers.contact_signals import ContactSignalDetector


class _MockLLM:
    def __init__(self, payload):
        self.payload = payload

    async def complete(self, *a, **k): ...

    async def complete_json(self, messages, model=None, temperature=0.3):
        return self.payload


@pytest.mark.asyncio
async def test_valid_signals_and_facts():
    llm = _MockLLM({
        "signals": ["appointment_requested", "budget_confirmed"],
        "facts": {"product_interest": "Audi Q4", "budget": "50k"},
        "buying_intent": 0.8,
    })
    r = await ContactSignalDetector(llm).detect("agendemos, tengo 50k")
    assert set(r.signals) == {"appointment_requested", "budget_confirmed"}
    assert r.facts["product_interest"] == "Audi Q4"
    assert r.buying_intent == 0.8


@pytest.mark.asyncio
async def test_unknown_signals_filtered_out():
    llm = _MockLLM({"signals": ["appointment_requested", "made_up_signal"], "buying_intent": 0.5})
    r = await ContactSignalDetector(llm).detect("x")
    assert r.signals == ["appointment_requested"]


@pytest.mark.asyncio
async def test_buying_intent_clamped_and_bad_facts_ignored():
    llm = _MockLLM({"signals": [], "facts": "not-a-dict", "buying_intent": 5.0})
    r = await ContactSignalDetector(llm).detect("x")
    assert r.buying_intent == 1.0
    assert r.facts == {}


@pytest.mark.asyncio
async def test_llm_failure_returns_empty():
    class Boom:
        async def complete_json(self, *a, **k):
            raise RuntimeError("llm down")

    r = await ContactSignalDetector(Boom()).detect("x")
    assert r.signals == [] and r.buying_intent == 0.0
