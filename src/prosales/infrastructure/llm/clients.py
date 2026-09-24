"""Shared LLM/embedding HTTP clients (singletons with retry/backoff).

AsyncOpenAI/AsyncAnthropic are httpx-based with their own connection pool and are
safe to share across coroutines. Reusing one client (instead of creating ~3 per
turn) avoids connection churn and centralizes retry/timeout config.
"""

from functools import lru_cache

import httpx
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from prosales.config import settings
from prosales.infrastructure.llm.observability import EVENT_HOOKS


@lru_cache(maxsize=8)
def get_openai_client(api_key: str | None = None) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=api_key or settings.openai_api_key,
        max_retries=settings.llm_max_retries,  # SDK does exponential backoff (incl. 429)
        timeout=settings.llm_timeout_seconds,
        # Own httpx client (not the SDK's default) so every real HTTP attempt —
        # including SDK-level retries — is observable via LLMCallTracker.
        # Pure observation, doesn't touch requests/responses (see observability.py).
        http_client=httpx.AsyncClient(event_hooks=EVENT_HOOKS),
    )


@lru_cache(maxsize=8)
def get_anthropic_client(api_key: str | None = None) -> AsyncAnthropic:
    return AsyncAnthropic(
        api_key=api_key or settings.anthropic_api_key,
        max_retries=settings.llm_max_retries,
        timeout=settings.llm_timeout_seconds,
        http_client=httpx.AsyncClient(event_hooks=EVENT_HOOKS),
    )
