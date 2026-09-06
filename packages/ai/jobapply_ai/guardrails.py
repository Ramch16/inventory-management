"""Validation applied to every model response before it reaches business logic.

The pipeline is: parse JSON → validate against the prompt's schema → (one repair
attempt) → hand a plain dict to the caller. Free-form model text never escapes this
module, and it never reaches the browser automation directly.
"""

from __future__ import annotations

import json
import re
from typing import Any

from jobapply_shared.errors import ProviderError
from jsonschema import Draft202012Validator

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


class AIResponseError(ProviderError):
    code = "ai_response_invalid"


def extract_json(raw: str) -> Any:
    """Pull a JSON document out of a model response.

    Handles the two common wrappers — a fenced code block, or prose surrounding the
    object — without ever ``eval``-ing anything.
    """
    text = raw.strip()
    fenced = _FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = min((idx for idx in (text.find("{"), text.find("[")) if idx != -1), default=-1)
    if start == -1:
        raise AIResponseError("Model response contained no JSON document")
    end = max(text.rfind("}"), text.rfind("]"))
    if end <= start:
        raise AIResponseError("Model response contained an unterminated JSON document")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise AIResponseError(f"Model response was not valid JSON: {exc.msg}") from exc


def validate_against_schema(data: Any, schema: dict[str, Any]) -> dict[str, Any]:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda err: list(err.path))
    if errors:
        details = "; ".join(
            f"{'/'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
            for error in errors[:5]
        )
        raise AIResponseError(f"Model response failed schema validation: {details}")
    if not isinstance(data, dict):
        raise AIResponseError("Model response must be a JSON object")
    return data


def schema_violations(data: Any, schema: dict[str, Any]) -> list[str]:
    validator = Draft202012Validator(schema)
    return [
        f"{'/'.join(str(part) for part in error.path) or '<root>'}: {error.message}"
        for error in validator.iter_errors(data)
    ]


def repair_instruction(raw: str, violations: list[str]) -> str:
    """The single follow-up message sent when a response fails validation."""
    joined = "\n".join(f"- {violation}" for violation in violations[:8])
    return (
        "Your previous response did not satisfy the required JSON schema.\n"
        f"Problems:\n{joined}\n\n"
        "Return ONLY the corrected JSON document. Do not add commentary, and do not "
        "invent any information that was not in the input.\n\n"
        f"Previous response:\n{raw[:4000]}"
    )


def try_schema(data: Any, schema: dict[str, Any]) -> tuple[bool, list[str]]:
    violations = schema_violations(data, schema)
    return (not violations, violations)


def ensure_no_extra_entities(data: dict[str, Any], allowed: set[str], fields: list[str]) -> None:
    """Business rule helper: reject a response naming an entity we never supplied."""
    for field in fields:
        value = data.get(field)
        candidates = value if isinstance(value, list) else [value]
        for candidate in candidates:
            if candidate and str(candidate).strip().lower() not in allowed:
                raise AIResponseError(
                    f"Model introduced an unapproved value for '{field}': {candidate!r}"
                )
