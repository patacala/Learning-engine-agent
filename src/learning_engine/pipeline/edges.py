"""Conditional edges for the cognitive pipeline."""

from learning_engine.core.enums import ConversationPath
from learning_engine.pipeline.state import CognitivePipelineState


def route_by_path(state: CognitivePipelineState) -> str:
    """Route based on ConversationManager decision."""
    route = state.get("route")
    if route and route.path == ConversationPath.FAST_PATH:
        return "fast_path"
    return "full_path"
