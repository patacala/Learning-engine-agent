import pytest

from prosales.core.enums import Sentiment
from prosales.core.models.analysis import AnalysisResult, SentimentResult
from prosales.engines.personality.engine import PersonalityEngine


@pytest.fixture
def engine():
    return PersonalityEngine()


@pytest.mark.asyncio
async def test_empathic_on_negative(engine):
    state = {
        "analysis": AnalysisResult(
            sentiment=SentimentResult(sentiment=Sentiment.NEGATIVE)
        )
    }
    result = await engine.process(state)
    profile = result["personality"]
    assert "empático" in profile.emotion.traits


@pytest.mark.asyncio
async def test_enthusiastic_on_positive(engine):
    state = {
        "analysis": AnalysisResult(
            sentiment=SentimentResult(sentiment=Sentiment.VERY_POSITIVE)
        )
    }
    result = await engine.process(state)
    profile = result["personality"]
    assert "entusiasta" in profile.emotion.traits


@pytest.mark.asyncio
async def test_compiles_instructions(engine):
    state = {"analysis": AnalysisResult()}
    result = await engine.process(state)
    instructions = result["personality"].compile_instructions()
    assert len(instructions) > 0
