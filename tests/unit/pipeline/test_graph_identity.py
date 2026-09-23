"""Tests for identity node in the pipeline graph."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from prosales.pipeline.graph import build_cognitive_graph


@pytest.fixture
def graph():
    """Build graph with mocked dependencies."""
    primary_llm = MagicMock()
    analyzer_llm = MagicMock()

    g = build_cognitive_graph(
        primary_llm=primary_llm,
        analyzer_llm=analyzer_llm,
        session_factory=MagicMock(),
    )
    return g


class TestGraphIdentityWiring:
    def test_identify_node_exists(self, graph):
        assert "identify" in graph.nodes

    def test_route_connects_to_identify(self, graph):
        # route should have an edge to identify
        edges = graph.edges
        # Check that route -> identify edge exists
        route_targets = [e[1] for e in edges if e[0] == "route"]
        assert "identify" in route_targets
