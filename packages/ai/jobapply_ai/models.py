"""Provider-agnostic AI request/response contracts."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TokenUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


class JSONCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_id: str
    system: str
    user: str
    json_schema: dict[str, Any]
    max_output_tokens: int = 2048
    temperature: float = 0.2
    model: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class JSONCompletionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Already validated against ``json_schema``.
    data: dict[str, Any]
    raw: str
    model: str
    provider: str
    usage: TokenUsage = Field(default_factory=TokenUsage)
    latency_ms: int = 0
    repaired: bool = False


class TextCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_id: str
    system: str
    user: str
    max_output_tokens: int = 1024
    temperature: float = 0.3
    model: str | None = None


class TextCompletionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    model: str
    provider: str
    usage: TokenUsage = Field(default_factory=TokenUsage)
    latency_ms: int = 0


class ProviderHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    healthy: bool
    detail: str | None = None
    latency_ms: int | None = None
