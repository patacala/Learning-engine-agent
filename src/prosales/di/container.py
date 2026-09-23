from prosales.config import settings
from prosales.core.enums import LLMProvider as LLMProviderEnum
from prosales.infrastructure.cache.redis import RedisCache
from prosales.infrastructure.events.bus import InMemoryEventBus
from prosales.infrastructure.llm.anthropic import AnthropicProvider
from prosales.infrastructure.llm.openai import OpenAIProvider
from prosales.infrastructure.llm.provider import LLMProvider


def create_llm_provider(provider: str | None = None) -> LLMProvider:
    provider = provider or settings.primary_llm_provider
    if provider == LLMProviderEnum.OPENAI:
        return OpenAIProvider()
    elif provider == LLMProviderEnum.ANTHROPIC:
        return AnthropicProvider()
    raise ValueError(f"Unknown LLM provider: {provider}")


def create_analyzer_llm() -> LLMProvider:
    """LLM provider for analyzers (cheaper model)."""
    return OpenAIProvider()


def create_cache() -> RedisCache:
    return RedisCache()


def create_event_bus() -> InMemoryEventBus:
    return InMemoryEventBus()
