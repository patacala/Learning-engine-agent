from learning_engine.config import settings
from learning_engine.core.enums import LLMProvider as LLMProviderEnum
from learning_engine.infrastructure.cache.redis import RedisCache
from learning_engine.infrastructure.events.bus import InMemoryEventBus
from learning_engine.infrastructure.llm.anthropic import AnthropicProvider
from learning_engine.infrastructure.llm.openai import OpenAIProvider
from learning_engine.infrastructure.llm.provider import LLMProvider


def create_llm_provider(provider: str | None = None) -> LLMProvider:
    provider = provider or settings.primary_llm_provider
    if provider == LLMProviderEnum.OPENAI:
        return OpenAIProvider(service_tier=settings.primary_llm_service_tier)
    elif provider == LLMProviderEnum.ANTHROPIC:
        return AnthropicProvider()
    raise ValueError(f"Unknown LLM provider: {provider}")


def create_analyzer_llm() -> LLMProvider:
    """LLM provider for analyzers (cheaper model)."""
    return OpenAIProvider(service_tier=settings.analyzer_llm_service_tier)


def create_cache() -> RedisCache:
    return RedisCache()


def create_event_bus() -> InMemoryEventBus:
    return InMemoryEventBus()
