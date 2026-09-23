"""Tests for PipelineRunner — shared pipeline execution."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from prosales.services.pipeline_runner import PipelineRunner, PipelineResult


@pytest.mark.asyncio
async def test_runner_produces_correct_result():
    """PipelineRunner.run should return a PipelineResult with all fields."""
    runner = PipelineRunner(AsyncMock(), cache=None)

    client_id = uuid4()
    conversation_id = uuid4()

    # Mock the voice output
    mock_voice = MagicMock()
    mock_voice.text = "Hola, ¿en qué puedo ayudarte?"
    mock_voice.ssml = "<speak>Hola</speak>"

    # Mock analysis
    mock_analysis = MagicMock()
    mock_analysis.intent.intent = "greeting"
    mock_analysis.sentiment.sentiment = "positive"
    mock_analysis.language.language = "es"

    # Mock route
    mock_route = MagicMock()
    mock_route.path = "fast_path"

    pipeline_result_state = {
        "response": "Hola, ¿en qué puedo ayudarte?",
        "voice_output": mock_voice,
        "analysis": mock_analysis,
        "route": mock_route,
    }

    with patch("prosales.services.pipeline_runner.SQLEventRepository"), \
         patch("prosales.services.pipeline_runner.EventStore"), \
         patch("prosales.services.pipeline_runner.create_llm_provider"), \
         patch("prosales.services.pipeline_runner.create_analyzer_llm"), \
         patch("prosales.services.pipeline_runner.build_cognitive_graph") as mock_graph:

        mock_compiled = AsyncMock()
        mock_compiled.ainvoke.return_value = pipeline_result_state
        mock_graph.return_value.compile.return_value = mock_compiled

        result = await runner.run(
            message="Hola",
            client_id=client_id,
            conversation_id=conversation_id,
            store_user_message=False,
        )

    assert isinstance(result, PipelineResult)
    assert result.response == "Hola, ¿en qué puedo ayudarte?"
    assert result.voice_text == "Hola, ¿en qué puedo ayudarte?"
    assert result.voice_ssml == "<speak>Hola</speak>"
    assert result.analysis_summary["intent"] == "greeting"
    assert result.route == "fast_path"


@pytest.mark.asyncio
async def test_runner_without_agent_context():
    """PipelineRunner should work without agent context (no providers)."""
    runner = PipelineRunner(AsyncMock(), cache=None)

    pipeline_result_state = {
        "response": "Default response",
    }

    with patch("prosales.services.pipeline_runner.SQLEventRepository"), \
         patch("prosales.services.pipeline_runner.EventStore"), \
         patch("prosales.services.pipeline_runner.create_llm_provider"), \
         patch("prosales.services.pipeline_runner.create_analyzer_llm"), \
         patch("prosales.services.pipeline_runner.build_cognitive_graph") as mock_graph:

        mock_compiled = AsyncMock()
        mock_compiled.ainvoke.return_value = pipeline_result_state
        mock_graph.return_value.compile.return_value = mock_compiled

        result = await runner.run(
            message="Hola",
            client_id=uuid4(),
            conversation_id=uuid4(),
            agent_context=None,
            store_user_message=False,
        )

    assert result.response == "Default response"
    assert result.voice_text == "Default response"
    assert result.voice_ssml is None
    assert result.analysis_summary == {}
