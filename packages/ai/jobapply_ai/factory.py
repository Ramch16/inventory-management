"""Provider selection.

``AI_PROVIDER`` chooses the implementation; nothing else in the platform names a
vendor.
"""

from __future__ import annotations

from functools import lru_cache

from jobapply_shared.settings import Settings, get_settings

from jobapply_ai.provider import AIProvider
from jobapply_ai.providers.mock import MockAIProvider


def build_ai_provider(settings: Settings | None = None) -> AIProvider:
    config = settings or get_settings()
    if config.ai_provider == "openai":
        from jobapply_ai.providers.openai import OpenAIProvider

        return OpenAIProvider(
            config.openai_api_key or "",
            model=config.openai_model,
            timeout=config.ai_timeout_seconds,
        )
    if config.ai_provider == "anthropic":
        from jobapply_ai.providers.anthropic import AnthropicProvider

        return AnthropicProvider(
            config.anthropic_api_key or "",
            model=config.anthropic_model,
            timeout=config.ai_timeout_seconds,
        )
    return MockAIProvider()


@lru_cache
def get_ai_provider() -> AIProvider:
    return build_ai_provider()
