import pytest

from learning_engine.core.enums import UrgencyLevel
from learning_engine.engines.analyzers.urgency import UrgencyDetector


@pytest.fixture
def detector():
    return UrgencyDetector()


@pytest.mark.asyncio
async def test_high_urgency(detector):
    result = await detector.detect("Necesito el carro urgente, hoy mismo")
    assert result.level == UrgencyLevel.HIGH
    assert len(result.signals) > 0


@pytest.mark.asyncio
async def test_medium_urgency(detector):
    result = await detector.detect("Me gustaría verlo pronto")
    assert result.level == UrgencyLevel.MEDIUM


@pytest.mark.asyncio
async def test_low_urgency(detector):
    result = await detector.detect("Estoy viendo opciones")
    assert result.level == UrgencyLevel.LOW
