"""Shared SSE helper for endpoints that stream progress stages."""

import json


def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"
