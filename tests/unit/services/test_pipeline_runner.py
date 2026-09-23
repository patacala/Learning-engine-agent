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


class TestCompiledGraphCache:
    """Fase 4.1: the compiled graph is built once per process (per has_providers
    variant), not on every run() call — see PipelineRunner._get_compiled_graph."""

    def teardown_method(self):
        # Don't leak mocked/fake compiled graphs into other tests' cache lookups.
        PipelineRunner._graph_cache.clear()

    def test_same_session_factory_and_providers_flag_reuses_compiled_graph(self):
        sf = AsyncMock()
        runner = PipelineRunner(sf, cache=None)

        with patch("prosales.services.pipeline_runner.create_llm_provider"), \
             patch("prosales.services.pipeline_runner.create_analyzer_llm"), \
             patch("prosales.services.pipeline_runner.build_cognitive_graph") as mock_graph:
            mock_graph.return_value.compile.return_value = MagicMock(name="compiled")

            first = runner._get_compiled_graph(has_providers=False)
            second = runner._get_compiled_graph(has_providers=False)

        assert first is second
        mock_graph.assert_called_once()  # build_cognitive_graph only ran once

    def test_different_providers_flag_builds_a_different_graph(self):
        sf = AsyncMock()
        runner = PipelineRunner(sf, cache=MagicMock())

        with patch("prosales.services.pipeline_runner.create_llm_provider"), \
             patch("prosales.services.pipeline_runner.create_analyzer_llm"), \
             patch("prosales.services.pipeline_runner.build_cognitive_graph") as mock_graph:
            mock_graph.return_value.compile.side_effect = [
                MagicMock(name="no_providers"),
                MagicMock(name="with_providers"),
            ]

            without = runner._get_compiled_graph(has_providers=False)
            with_providers = runner._get_compiled_graph(has_providers=True)

        assert without is not with_providers
        assert mock_graph.call_count == 2
