"""Anthropic provider.

The SDK is an optional dependency: install with ``pip install -e ".[ai]"``.
"""

from __future__ import annotations

from jobapply_shared.errors import ProviderError, TransientError

from jobapply_ai.models import TokenUsage
from jobapply_ai.provider import BaseAIProvider


class AnthropicProvider(BaseAIProvider):
    name = "anthropic"

    def __init__(self, api_key: str, *, model: str = "claude-sonnet-5", timeout: int = 60) -> None:
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for the Anthropic provider")
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ProviderError(
                "The anthropic package is not installed. Install the 'ai' extra.",
                code="provider_unavailable",
            ) from exc
        self._client = AsyncAnthropic(api_key=api_key, timeout=timeout)
        self.default_model = model

    async def _generate(
        self, *, system: str, user: str, max_output_tokens: int, temperature: float, model: str
    ) -> tuple[str, TokenUsage]:
        try:
            response = await self._client.messages.create(
                model=model,
                system=system,
                messages=[{"role": "user", "content": user}],
                max_tokens=max_output_tokens,
                temperature=temperature,
            )
        except Exception as exc:  # pragma: no cover - network dependent
            raise TransientError(f"Anthropic request failed: {exc}") from exc
        text = "".join(block.text for block in response.content if block.type == "text")
        usage = TokenUsage(
            input_tokens=getattr(response.usage, "input_tokens", 0) or 0,
            output_tokens=getattr(response.usage, "output_tokens", 0) or 0,
        )
        return text, usage
