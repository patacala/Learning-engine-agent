import pytest

from prosales.core.enums import ConversationPath, Intent
from prosales.core.models.analysis import AnalysisResult, IntentResult
from prosales.engines.conversation_manager.engine import ConversationManager


@pytest.fixture
def manager():
    return ConversationManager()


@pytest.mark.asyncio
async def test_fast_path_for_greeting(manager):
    state = {
        "current_message": "Hola",
        "analysis": AnalysisResult(
            intent=IntentResult(intent=Intent.GREETING, confidence=0.9)
        ),
    }
    result = await manager.process(state)
    assert result["route"].path == ConversationPath.FAST_PATH


@pytest.mark.asyncio
async def test_full_path_for_comparison(manager):
    state = {
        "current_message": "Estoy comparando el Corolla con el Civic, ¿cuál me recomiendas?",
        "analysis": AnalysisResult(
            intent=IntentResult(intent=Intent.COMPARISON, confidence=0.9)
        ),
    }
    result = await manager.process(state)
    assert result["route"].path == ConversationPath.FULL_PATH
