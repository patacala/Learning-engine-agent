import pytest

from learning_engine.core.enums import RiskLevel
from learning_engine.engines.analyzers.risk import RiskDetector


@pytest.fixture
def detector():
    return RiskDetector()


@pytest.mark.asyncio
async def test_high_risk(detector):
    result = await detector.detect(
        "Es muy caro, la competencia tiene mejor oferta y no me convence"
    )
    assert result.level == RiskLevel.HIGH


@pytest.mark.asyncio
async def test_medium_risk(detector):
    result = await detector.detect("Es un poco caro, ¿no?")
    assert result.level == RiskLevel.MEDIUM


@pytest.mark.asyncio
async def test_low_risk(detector):
    result = await detector.detect("Me gusta mucho, cuéntame más")
    assert result.level == RiskLevel.LOW
