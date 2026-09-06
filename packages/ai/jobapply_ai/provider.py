"""The ``AIProvider`` abstraction.

Nothing above this layer knows which vendor is in use. Adding a provider means adding
one class here; it does not mean touching a service.
"""

from __future__ import annotations

import time
from typing import Protocol, runtime_checkable

from jobapply_ai.guardrails import (
    AIResponseError,
    extract_json,
    repair_instruction,
    try_schema,
    validate_against_schema,
)
from jobapply_ai.models import (
    JSONCompletionRequest,
    JSONCompletionResult,
    ProviderHealth,
    TextCompletionRequest,
    TextCompletionResult,
    TokenUsage,
)


@runtime_checkable
class AIProvider(Protocol):
    name: str

    async def complete_json(self, request: JSONCompletionRequest) -> JSONCompletionResult: ...
    async def complete_text(self, request: TextCompletionRequest) -> TextCompletionResult: ...
    async def health(self) -> ProviderHealth: ...


class BaseAIProvider:
    """Shared JSON handling: one parse, one schema check, one repair attempt.

    Subclasses implement ``_generate`` only.
    """

    name = "base"
    default_model = ""

    async def _generate(
        self, *, system: str, user: str, max_output_tokens: int, temperature: float, model: str
    ) -> tuple[str, TokenUsage]:
        raise NotImplementedError

    async def complete_json(self, request: JSONCompletionRequest) -> JSONCompletionResult:
        model = request.model or self.default_model
        started = time.perf_counter()
        raw, usage = await self._generate(
            system=request.system,
            user=request.user,
            max_output_tokens=request.max_output_tokens,
            temperature=request.temperature,
            model=model,
        )
        repaired = False
        try:
            data = extract_json(raw)
        except AIResponseError:
            data = None

        ok, violations = (
            try_schema(data, request.json_schema)
            if data is not None
            else (False, ["response was not JSON"])
        )
        if not ok:
            repaired = True
            repair_raw, repair_usage = await self._generate(
                system=request.system,
                user=repair_instruction(raw, violations),
                max_output_tokens=request.max_output_tokens,
                temperature=0.0,
                model=model,
            )
            usage = TokenUsage(
                input_tokens=usage.input_tokens + repair_usage.input_tokens,
                output_tokens=usage.output_tokens + repair_usage.output_tokens,
            )
            raw = repair_raw
            data = extract_json(raw)

        validated = validate_against_schema(data, request.json_schema)
        return JSONCompletionResult(
            data=validated,
            raw=raw,
            model=model,
            provider=self.name,
            usage=usage,
            latency_ms=int((time.perf_counter() - started) * 1000),
            repaired=repaired,
        )

    async def complete_text(self, request: TextCompletionRequest) -> TextCompletionResult:
        model = request.model or self.default_model
        started = time.perf_counter()
        raw, usage = await self._generate(
            system=request.system,
            user=request.user,
            max_output_tokens=request.max_output_tokens,
            temperature=request.temperature,
            model=model,
        )
        return TextCompletionResult(
            text=raw,
            model=model,
            provider=self.name,
            usage=usage,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    async def health(self) -> ProviderHealth:
        return ProviderHealth(provider=self.name, healthy=True)
