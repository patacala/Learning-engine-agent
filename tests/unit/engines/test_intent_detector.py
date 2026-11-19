"""IntentDetector is the most-consumed analyzer signal in the pipeline (Strategy
scoring, Decision rules, FAST/FULL_PATH routing, planner, voice, contact
qualification all read it) — yet it had zero test coverage verifying it produces
different outputs for different inputs, since it's the only LLM-backed detector
without a fixture-based test (unlike sentiment/urgency/risk).
"""

from typing import Any

import pytest

from learning_engine.core.enums import Intent
from learning_engine.engines.analyzers.intent import IntentDetector


class FakeLLM:
    """Returns whatever intent/confidence the test wired up — no network call."""

    def __init__(self, response: dict[str, Any] | None = None, raise_error: bool = False):
        self._response = response or {"intent": "unknown", "confidence": 0.5}
        self._raise = raise_error

    async def complete_json(self, messages, **kwargs) -> dict:
        if self._raise:
            raise RuntimeError("simulated LLM failure")
        return self._response


@pytest.mark.parametrize(
    "raw_intent,confidence,expected",
    [
        ("greeting", 0.95, Intent.GREETING),
        ("objection", 0.8, Intent.OBJECTION),
        ("scheduling", 0.7, Intent.SCHEDULING),
        ("farewell", 0.6, Intent.FAREWELL),
    ],
)
async def test_detect_maps_different_llm_outputs_to_different_intents(
    raw_intent, confidence, expected
):
    detector = IntentDetector(llm=FakeLLM({"intent": raw_intent, "confidence": confidence}))
    result = await detector.detect(text="doesn't matter, LLM output is faked")
    assert result.intent == expected
    assert result.confidence == confidence


async def test_detect_passes_through_sub_intent():
    detector = IntentDetector(
        llm=FakeLLM({"intent": "objection", "confidence": 0.9, "sub_intent": "price"})
    )
    result = await detector.detect(text="it's too expensive")
    assert result.sub_intent == "price"


async def test_detect_falls_back_to_unknown_on_llm_failure():
    """A crashed/unavailable LLM must not crash the pipeline — it degrades to
    IntentResult() defaults (UNKNOWN, confidence=0.0), never raises."""
    detector = IntentDetector(llm=FakeLLM(raise_error=True))
    result = await detector.detect(text="anything")
    assert result.intent == Intent.UNKNOWN
    assert result.confidence == 0.0


async def test_detect_defaults_confidence_when_missing_from_llm_response():
    detector = IntentDetector(llm=FakeLLM({"intent": "inquiry"}))  # no confidence key
    result = await detector.detect(text="what colors do you have?")
    assert result.intent == Intent.INQUIRY
    assert result.confidence == 0.5  # IntentDetector's own documented default
