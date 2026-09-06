"""OpenAI provider.

The SDK is an optional dependency: install with ``pip install -e ".[ai]"``. The rest
of the platform works with ``AI_PROVIDER=mock``.
"""

from __future__ import annotations

from jobapply_shared.errors import ProviderError, TransientError

from jobapply_ai.models import TokenUsage
from jobapply_ai.provider import BaseAIProvider


class OpenAIProvider(BaseAIProvider):
    name = "openai"

    def __init__(self, api_key: str, *, model: str = "gpt-4.1", timeout: int = 60) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for the OpenAI provider")
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ProviderError(
                "The openai package is not installed. Install the 'ai' extra.",
                code="provider_unavailable",
            ) from exc
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout)
        self.default_model = model

    async def _generate(
        self, *, system: str, user: str, max_output_tokens: int, temperature: float, model: str
    ) -> tuple[str, TokenUsage]:
        try:
            response = await self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=max_output_tokens,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
        except Exception as exc:  # pragma: no cover - network dependent
            raise TransientError(f"OpenAI request failed: {exc}") from exc
        content = response.choices[0].message.content or ""
        usage = TokenUsage(
            input_tokens=getattr(response.usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(response.usage, "completion_tokens", 0) or 0,
        )
        return content, usage
