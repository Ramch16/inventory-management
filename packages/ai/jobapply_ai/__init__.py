"""Provider-agnostic AI layer with schema validation and guardrails."""

from jobapply_ai.factory import build_ai_provider, get_ai_provider
from jobapply_ai.models import JSONCompletionRequest, JSONCompletionResult
from jobapply_ai.prompts import REGISTRY, Prompt, get_prompt
from jobapply_ai.provider import AIProvider, BaseAIProvider

__all__ = [
    "REGISTRY",
    "AIProvider",
    "BaseAIProvider",
    "JSONCompletionRequest",
    "JSONCompletionResult",
    "Prompt",
    "build_ai_provider",
    "get_ai_provider",
    "get_prompt",
]
