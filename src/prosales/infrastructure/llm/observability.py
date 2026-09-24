"""Ground-truth HTTP-level tracking for LLM calls — built 2026-09-24 because
every latency finding so far was one-off (curl by hand, ad-hoc scripts). This
hooks the ACTUAL httpx transport under OpenAI/Anthropic's shared clients so
every real pipeline run answers, for free, the two questions that matter:

1. Is a slow node slow because of ONE slow HTTP round-trip (model/API-side),
   or because the SDK silently retried (network/5xx/timeout) and the retries
   summed up? These look identical from the outside (both just "this node
   took 2.6s") but need completely different fixes.
2. Does it correlate with anything (node, time of day, which provider)?

Zero behavior change: pure observation via httpx's event_hooks, wired once in
infrastructure/llm/clients.py. Nothing here can affect what gets sent/streamed.
"""

import time
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass, field

import httpx


@dataclass
class HttpAttempt:
    started_at: float
    elapsed_ms: float | None = None
    status_code: int | None = None
    method: str = ""
    path: str = ""  # just the path, not the full URL (no query/host noise)


@dataclass
class LLMCallTracker:
    """Context manager: every real HTTP request/response the OpenAI/Anthropic
    SDK's shared client makes while this block is active — across ANY number
    of concurrent coroutines spawned inside it (asyncio.gather included;
    contextvars propagate to child tasks by default) — gets recorded here.

    Used as ``with LLMCallTracker(node_id) as t: ...`` around each pipeline
    node in pipeline/nodes.py's _make_timed_node, so `t.http_attempts` /
    `t.http_retry_count` ride the existing NodeTrace → pipeline.completed
    event, no new persistence layer needed.
    """

    node: str
    attempts: list[HttpAttempt] = field(default_factory=list)
    _token: object = None

    def __enter__(self) -> "LLMCallTracker":
        self._token = _current_tracker.set(self)
        return self

    def __exit__(self, *exc) -> None:
        _current_tracker.reset(self._token)

    @property
    def http_attempts(self) -> int:
        return len(self.attempts)

    @property
    def http_retry_count(self) -> int:
        return max(0, len(self.attempts) - 1)

    @property
    def http_max_elapsed_ms(self) -> float | None:
        """The single slowest HTTP round-trip — distinguishes '1 attempt that
        was just slow' from 'N attempts that individually look fine but
        summed up' (the latter means retries, not raw model latency)."""
        durations = [a.elapsed_ms for a in self.attempts if a.elapsed_ms is not None]
        return max(durations) if durations else None


_current_tracker: ContextVar[LLMCallTracker | None] = ContextVar("llm_call_tracker", default=None)


async def _on_request(request: httpx.Request) -> None:
    tracker = _current_tracker.get()
    if tracker is None:
        return
    attempt = HttpAttempt(started_at=time.monotonic(), method=request.method, path=request.url.path)
    tracker.attempts.append(attempt)
    request.extensions["_llm_attempt"] = attempt


async def _on_response(response: httpx.Response) -> None:
    # Deliberately does NOT read the response body — a streaming response
    # (see OpenAIProvider.stream/AnthropicProvider.stream) must stay
    # untouched here, the caller reads it incrementally afterward.
    attempt = response.request.extensions.get("_llm_attempt")
    if attempt is None:
        return
    attempt.elapsed_ms = round((time.monotonic() - attempt.started_at) * 1000, 1)
    attempt.status_code = response.status_code


EVENT_HOOKS: dict[str, list[Callable]] = {"request": [_on_request], "response": [_on_response]}
