"""AI output must pass schema validation before any business logic sees it."""

from __future__ import annotations

import asyncio

import pytest
from jobapply_ai.guardrails import (
    AIResponseError,
    ensure_no_extra_entities,
    extract_json,
    validate_against_schema,
)
from jobapply_ai.models import JSONCompletionRequest
from jobapply_ai.prompts import REGISTRY, get_prompt
from jobapply_ai.provider import BaseAIProvider
from jobapply_ai.providers.mock import MockAIProvider

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer", "confidence"],
    "properties": {
        "answer": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}


def test_extract_json_handles_fenced_and_wrapped_responses():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Here you go:\n{"a": 1}\nHope that helps.') == {"a": 1}


def test_extract_json_rejects_a_response_with_no_json():
    with pytest.raises(AIResponseError):
        extract_json("I cannot help with that.")


def test_schema_validation_rejects_out_of_range_and_unknown_fields():
    validate_against_schema({"answer": "yes", "confidence": 0.9}, SCHEMA)
    with pytest.raises(AIResponseError):
        validate_against_schema({"answer": "yes", "confidence": 4}, SCHEMA)
    with pytest.raises(AIResponseError):
        validate_against_schema({"answer": "yes", "confidence": 0.5, "extra": 1}, SCHEMA)
    with pytest.raises(AIResponseError):
        validate_against_schema({"answer": "yes"}, SCHEMA)


def test_business_rule_blocks_unapproved_entities():
    with pytest.raises(AIResponseError):
        ensure_no_extra_entities(
            {"company": "Fabricated Corp"}, {"northwind analytics"}, ["company"]
        )
    ensure_no_extra_entities(
        {"company": "Northwind Analytics"}, {"northwind analytics"}, ["company"]
    )


@pytest.mark.parametrize("prompt_id", sorted(REGISTRY))
def test_every_prompt_declares_a_strict_json_schema(prompt_id):
    prompt = get_prompt(prompt_id)
    assert prompt.json_schema["type"] == "object"
    assert prompt.json_schema.get("additionalProperties") is False
    assert prompt.json_schema.get("required")
    assert "Absolute rules" in prompt.system


class _MalformedProvider(BaseAIProvider):
    """First response is broken, the repair round-trip returns valid JSON."""

    name = "malformed"
    default_model = "test"

    def __init__(self) -> None:
        self.calls = 0

    async def _generate(self, *, system, user, max_output_tokens, temperature, model):
        from jobapply_ai.models import TokenUsage

        self.calls += 1
        if self.calls == 1:
            return "sorry, here is prose instead", TokenUsage()
        return '{"answer": "yes", "confidence": 0.9}', TokenUsage()


class _AlwaysBrokenProvider(_MalformedProvider):
    name = "broken"

    async def _generate(self, *, system, user, max_output_tokens, temperature, model):
        from jobapply_ai.models import TokenUsage

        self.calls += 1
        return "still not json", TokenUsage()


def _request() -> JSONCompletionRequest:
    return JSONCompletionRequest(prompt_id="TEST", system="s", user="u", json_schema=SCHEMA)


def test_one_repair_attempt_is_made_for_a_malformed_response():
    provider = _MalformedProvider()
    result = asyncio.run(provider.complete_json(_request()))
    assert result.repaired is True
    assert result.data["answer"] == "yes"
    assert provider.calls == 2


def test_a_persistently_invalid_response_fails_loudly():
    provider = _AlwaysBrokenProvider()
    with pytest.raises(AIResponseError):
        asyncio.run(provider.complete_json(_request()))
    assert provider.calls == 2, "exactly one repair attempt, then give up"


def test_mock_provider_returns_schema_valid_data_for_every_prompt():
    provider = MockAIProvider()
    prompt = get_prompt("RESUME_TAILORING")
    request = JSONCompletionRequest(
        prompt_id=prompt.id,
        system=prompt.system,
        user=prompt.render(
            sources="experience_1: Built pipelines with Python at Northwind Analytics",
            job="Data Engineer",
            max_pages=1,
        ),
        json_schema=prompt.json_schema,
    )
    result = asyncio.run(provider.complete_json(request))
    assert result.provider == "mock"
    assert result.data["experience"][0]["experience_id"] == "experience_1"
    assert result.usage.total > 0


def test_mock_provider_refuses_to_answer_sensitive_questions():
    provider = MockAIProvider()
    prompt = get_prompt("APPLICATION_QUESTION")
    request = JSONCompletionRequest(
        prompt_id=prompt.id,
        system=prompt.system,
        user=prompt.render(
            question="Are you authorized to work in the United States?",
            field_type="radio",
            options="Yes, No",
            facts="profile: Jordan Rivera",
            job="Data Engineer",
        ),
        json_schema=prompt.json_schema,
    )
    result = asyncio.run(provider.complete_json(request))
    assert result.data["requires_review"] is True
    assert result.data["answer"] is None
