import pytest

from prosales.engines.response.post_processor import PostProcessor


@pytest.fixture
def processor():
    return PostProcessor()


@pytest.mark.asyncio
async def test_removes_ai_references(processor):
    state = {"llm_response": "Como modelo de lenguaje, te puedo ayudar con eso."}
    result = await processor.process(state)
    assert "modelo de lenguaje" not in result["response"]


@pytest.mark.asyncio
async def test_removes_markdown(processor):
    state = {"llm_response": "El **Toyota Corolla** tiene *excelente* rendimiento."}
    result = await processor.process(state)
    assert "**" not in result["response"]
    assert "*" not in result["response"]


@pytest.mark.asyncio
async def test_cleans_whitespace(processor):
    state = {"llm_response": "Hola   ,  bienvenido   al concesionario."}
    result = await processor.process(state)
    assert "   " not in result["response"]
