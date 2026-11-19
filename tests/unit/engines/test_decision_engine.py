import pytest

from learning_engine.core.enums import Intent, Sentiment
from learning_engine.core.models.analysis import AnalysisResult, IntentResult, SentimentResult
from learning_engine.engines.decision.engine import DecisionEngine


@pytest.fixture
def engine():
    return DecisionEngine()


@pytest.mark.asyncio
async def test_empathize_on_negative_sentiment(engine):
    state = {
        "analysis": AnalysisResult(
            intent=IntentResult(intent=Intent.OBJECTION),
            sentiment=SentimentResult(sentiment=Sentiment.NEGATIVE, score=-0.5),
        )
    }
    result = await engine.process(state)
    actions = result["decision"].actions
    action_types = [a.type for a in actions]
    assert "empathize" in action_types
    # empathize should be highest priority
    assert actions[0].type == "empathize"


@pytest.mark.asyncio
async def test_greeting_action(engine):
    state = {
        "analysis": AnalysisResult(
            intent=IntentResult(intent=Intent.GREETING),
        )
    }
    result = await engine.process(state)
    action_types = [a.type for a in result["decision"].actions]
    assert "greet" in action_types
