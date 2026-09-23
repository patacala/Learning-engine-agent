"""Shared LLM/embedding HTTP clients (singletons with retry/backoff).

AsyncOpenAI/AsyncAnthropic are httpx-based with their own connection pool and are
safe to share across coroutines. Reusing one client (instead of creating ~3 per
turn) avoids connection churn and centralizes retry/timeout config.
"""

from functools import lru_cache

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from prosales.config import settings


@lru_cache(maxsize=8)
def get_openai_client(api_key: str | None = None) -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=api_key or settings.openai_api_key,
        max_retries=settings.llm_max_retries,  # SDK does exponential backoff (incl. 429)
        timeout=settings.llm_timeout_seconds,
    )


@lru_cache(maxsize=8)
def get_anthropic_client(api_key: str | None = None) -> AsyncAnthropic:
    return AsyncAnthropic(
        api_key=api_key or settings.anthropic_api_key,
        max_retries=settings.llm_max_retries,
        timeout=settings.llm_timeout_seconds,
    )
