"""Direct regression guard for the bug found empirically 2026-09-24: two turns
of the same agent, differing only in the client's detected sentiment, used to
produce a system_msg that diverged at character 148 — killing any chance of
OpenAI's automatic prompt caching (needs an exact-matching prefix) ever
kicking in, no matter how many static tokens followed. system_msg must now be
byte-identical regardless of emotion; only context_msg may vary with it."""

import pytest

from prosales.core.enums import Sentiment
from prosales.core.models.analysis import AnalysisResult, SentimentResult
from prosales.core.models.personality import PersonalityLayer, PersonalityProfile
from prosales.engines.response.prompt_builder import PromptBuilder


def _profile_for(sentiment: Sentiment) -> PersonalityProfile:
    from prosales.engines.personality.layers import get_emotion_layer

    return PersonalityProfile(
        brand=PersonalityLayer(tone="Cálido", instructions=["Sé cálido y cercano"]),
        conversation=PersonalityLayer(tone="Consultivo", instructions=["Escucha primero"]),
        voice=PersonalityLayer(tone="Natural", instructions=[]),
        emotion=get_emotion_layer(sentiment),
        identity=PersonalityLayer(),
    )


@pytest.mark.asyncio
async def test_system_msg_is_identical_across_different_sentiments():
    state_negative = {
        "current_message": "me parece carísimo",
        "personality": _profile_for(Sentiment.NEGATIVE),
        "analysis": AnalysisResult(sentiment=SentimentResult(sentiment=Sentiment.NEGATIVE)),
    }
    state_positive = {
        "current_message": "me encanta, quiero verlo",
        "personality": _profile_for(Sentiment.VERY_POSITIVE),
        "analysis": AnalysisResult(sentiment=SentimentResult(sentiment=Sentiment.VERY_POSITIVE)),
    }

    builder = PromptBuilder()
    result_negative = await builder.process(state_negative)
    result_positive = await builder.process(state_positive)

    system_negative = result_negative["prompt_messages"][0].content
    system_positive = result_positive["prompt_messages"][0].content

    assert system_negative == system_positive, (
        "system_msg must stay byte-identical across turns regardless of client "
        "sentiment — this is what lets OpenAI's prompt caching match its prefix. "
        "If this fails, an emotion-dependent (or otherwise per-turn) value leaked "
        "back into _build_system_message()/DEFAULT_SYSTEM_TEMPLATE."
    )


@pytest.mark.asyncio
async def test_context_msg_carries_the_mood_that_moved_out_of_system_msg():
    state = {
        "current_message": "me parece carísimo",
        "personality": _profile_for(Sentiment.NEGATIVE),
        "analysis": AnalysisResult(sentiment=SentimentResult(sentiment=Sentiment.NEGATIVE)),
    }
    result = await PromptBuilder().process(state)
    context_msg = result["prompt_messages"][1].content
    assert "CURRENT MOOD" in context_msg
    assert "Empático" in context_msg


@pytest.mark.asyncio
async def test_strategy_and_plan_live_in_context_msg_not_system_msg():
    from types import SimpleNamespace

    state = {
        "current_message": "hola",
        "strategy": SimpleNamespace(strategy_type="consultive", tactic_instruction="Preguntá sobre su necesidad"),
        "plan": SimpleNamespace(goal="Calificar", next_action=SimpleNamespace(prompt_instruction="Pedí el presupuesto")),
    }
    result = await PromptBuilder().process(state)
    system_msg = result["prompt_messages"][0].content
    context_msg = result["prompt_messages"][1].content

    assert "Preguntá sobre su necesidad" not in system_msg
    assert "Pedí el presupuesto" not in system_msg
    assert "Preguntá sobre su necesidad" in context_msg
    assert "Pedí el presupuesto" in context_msg
