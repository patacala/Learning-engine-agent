"""UnifiedAnalyzer replaces 4 separate LLM calls (intent/sentiment/stage/
contact_signals) with 1 — same mapping/validation as each individual detector
(mirrors the fixtures in test_intent_detector.py / test_contact_signal_detector.py),
plus the failure-mode trade-off documented in unified.py: one call failing
takes all 4 sections down together (vs. only the one detector today)."""

from typing import Any

import pytest

from prosales.core.enums import ConversationStage, Intent, Sentiment
from prosales.engines.analyzers.unified import UnifiedAnalyzer


class FakeLLM:
    """Returns whatever combined JSON the test wired up — no network call."""

    def __init__(self, response: dict[str, Any] | None = None, raise_error: bool = False):
        self._response = response
        self._raise = raise_error

    async def complete_json(self, messages, **kwargs) -> dict:
        if self._raise:
            raise RuntimeError("simulated LLM failure")
        return self._response


def _full_response(**overrides) -> dict:
    base = {
        "intent": {"intent": "objection", "confidence": 0.8, "sub_intent": None},
        "sentiment": {"sentiment": "negative", "score": -0.4, "emotions": ["frustration"]},
        "stage": {"stage": "objection_handling", "confidence": 0.7},
        "contact_signals": {
            "signals": ["price_objection", "comparing_competitors"],
            "facts": {"product_interest": "sedan"},
            "buying_intent": 0.5,
        },
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_detect_maps_all_four_sections_in_one_call():
    llm = FakeLLM(_full_response())
    analyzer = UnifiedAnalyzer(llm)

    intent, sentiment, stage, contact_signals = await analyzer.detect("me parece caro comparado con otro lado")

    assert intent.intent == Intent.OBJECTION
    assert intent.confidence == 0.8
    assert sentiment.sentiment == Sentiment.NEGATIVE
    assert sentiment.emotions == ["frustration"]
    assert stage.stage == ConversationStage.OBJECTION_HANDLING
    assert contact_signals.signals == ["price_objection", "comparing_competitors"]
    assert contact_signals.facts == {"product_interest": "sedan"}
    assert contact_signals.buying_intent == 0.5


@pytest.mark.asyncio
async def test_invalid_signal_is_filtered_same_as_individual_detector():
    llm = FakeLLM(_full_response(contact_signals={
        "signals": ["price_objection", "made_up_signal"],
        "facts": {},
        "buying_intent": 0.2,
    }))
    analyzer = UnifiedAnalyzer(llm)

    _, _, _, contact_signals = await analyzer.detect("mensaje")

    assert contact_signals.signals == ["price_objection"]  # "made_up_signal" dropped


@pytest.mark.asyncio
async def test_malformed_single_section_falls_back_to_default_only_for_that_section():
    llm = FakeLLM(_full_response(stage={"stage": "not_a_real_stage", "confidence": 0.9}))
    analyzer = UnifiedAnalyzer(llm)

    intent, sentiment, stage, contact_signals = await analyzer.detect("mensaje")

    assert intent.intent == Intent.OBJECTION  # unaffected
    assert stage.stage == ConversationStage.OPENING  # default, section fell back
    assert stage.confidence == 0.0


@pytest.mark.asyncio
async def test_call_failure_falls_back_all_four_sections():
    """The documented trade-off vs. the 4-separate-calls path: one failure = all 4 default."""
    llm = FakeLLM(raise_error=True)
    analyzer = UnifiedAnalyzer(llm)

    intent, sentiment, stage, contact_signals = await analyzer.detect("mensaje")

    assert intent.intent == Intent.UNKNOWN
    assert sentiment.sentiment == Sentiment.NEUTRAL
    assert stage.stage == ConversationStage.OPENING
    assert contact_signals.signals == []
