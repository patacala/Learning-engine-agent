import pytest

from prosales.core.enums import Language
from prosales.engines.analyzers.language import LanguageDetector


@pytest.fixture
def detector():
    return LanguageDetector()


@pytest.mark.asyncio
async def test_detects_spanish(detector):
    result = await detector.detect("Hola, busco un carro familiar")
    assert result.language == Language.ES


@pytest.mark.asyncio
async def test_detects_english(detector):
    result = await detector.detect("Hello, I'm looking for a car please")
    assert result.language == Language.EN


@pytest.mark.asyncio
async def test_detects_portuguese(detector):
    result = await detector.detect("Olá, procuro um carro")
    assert result.language == Language.PT


@pytest.mark.asyncio
async def test_defaults_to_spanish_on_unknown(detector):
    result = await detector.detect("xyz 123")
    assert result.language == Language.ES
