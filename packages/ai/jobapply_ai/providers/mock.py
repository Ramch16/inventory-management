"""Deterministic provider for local development and tests.

It never reaches the network and needs no API key. Responses are schema-shaped and
derived from the input records, so tests exercise the real validation and
truth-checking paths rather than a stub that always returns success — and, crucially,
the mock's output *passes* verification, so local development does not look broken.
"""

from __future__ import annotations

import json
import re
from typing import Any

from jobapply_ai.models import TokenUsage
from jobapply_ai.provider import BaseAIProvider

_SOURCE_ID_RE = re.compile(
    r"\b((?:experience|skill|education|certification|project)_[\w-]+|profile)\b"
)
#: Source records reach a prompt as "<id>: <content>" lines.
_SOURCE_LINE_RE = re.compile(
    r"^((?:experience|skill|education|certification|project)_[\w-]+|profile):\s*(.+)$"
)


def _source_ids(user: str, limit: int = 3) -> list[str]:
    found = list(dict.fromkeys(_SOURCE_ID_RE.findall(user)))
    return found[:limit] or ["profile"]


def _source_lines(user: str) -> dict[str, str]:
    """Parse the "<id>: <content>" source block out of a rendered prompt."""
    found: dict[str, str] = {}
    for line in user.splitlines():
        match = _SOURCE_LINE_RE.match(line.strip())
        if match:
            found[match.group(1)] = match.group(2).strip()
    return found


def _first_sentence(text: str, fallback: str) -> str:
    """First real sentence of ``text``.

    The mock must never echo instruction text back: doing so produces output the truth
    layer rejects, which makes a working local setup look broken.
    """
    for candidate in re.split(r"(?<=[.!?])\s+", text or ""):
        cleaned = candidate.strip(" -•\t\n")
        if len(cleaned) > 25 and not cleaned.endswith(":"):
            return cleaned[:280]
    return fallback


class MockAIProvider(BaseAIProvider):
    name = "mock"
    default_model = "mock-1"

    def __init__(self, *, responses: dict[str, dict[str, Any]] | None = None) -> None:
        #: Optional canned responses keyed by prompt id, for targeted test cases.
        self.responses = responses or {}
        self.calls: list[dict[str, str]] = []

    async def _generate(
        self, *, system: str, user: str, max_output_tokens: int, temperature: float, model: str
    ) -> tuple[str, TokenUsage]:
        self.calls.append({"system": system, "user": user, "model": model})
        prompt_id = self._infer_prompt_id(system, user)
        payload = self.responses.get(prompt_id) or self._synthesize(prompt_id, user)
        raw = json.dumps(payload)
        return raw, TokenUsage(input_tokens=len(user) // 4, output_tokens=len(raw) // 4)

    @staticmethod
    def _infer_prompt_id(system: str, user: str) -> str:
        haystack = f"{system}\n{user}".lower()
        if "converts a job posting" in haystack:
            return "JOB_EXTRACTION"
        if "deterministic scores" in haystack:
            return "JOB_MATCHING"
        if "target length" in haystack or "tailored resume" in haystack:
            return "RESUME_TAILORING"
        if "cover letter" in haystack:
            return "COVER_LETTER"
        if "allowed mapping targets" in haystack:
            return "FIELD_MAPPING"
        if "draft answer" in haystack:
            return "CONFIDENCE_EVALUATION"
        if "question:" in haystack:
            return "APPLICATION_QUESTION"
        return "UNKNOWN"

    def _synthesize(self, prompt_id: str, user: str) -> dict[str, Any]:
        sources = _source_ids(user)
        records = _source_lines(user)

        if prompt_id == "JOB_EXTRACTION":
            title = re.search(r"(?im)^title:\s*(.+)$", user)
            company = re.search(r"(?im)^company:\s*(.+)$", user)
            return {
                "title": title.group(1).strip() if title else None,
                "company": company.group(1).strip() if company else None,
                "location": None,
                "remote_type": "unknown",
                "employment_type": "unknown",
                "salary_min": None,
                "salary_max": None,
                "salary_currency": None,
                "requirements": [],
                "preferred_qualifications": [],
                "skills": [],
                "education": None,
                "experience_required_years": None,
                "seniority": None,
                "sponsorship_information": None,
            }

        if prompt_id == "JOB_MATCHING":
            return {
                "matched_skills": [],
                "missing_skills": [],
                "risks": [],
                "explanation": (
                    "Deterministic scores drive this recommendation; the mock provider "
                    "adds no narrative."
                ),
            }

        if prompt_id == "RESUME_TAILORING":
            # Each bullet is a sentence taken verbatim from the record it cites, so the
            # mock exercises the real verification path and passes it.
            experience_ids = [key for key in records if key.startswith("experience_")]
            profile_text = records.get("profile", "")
            return {
                "summary": _first_sentence(profile_text, "Experienced professional."),
                "summary_source_ids": ["profile"] if profile_text else sources,
                "skills": [],
                "experience": [
                    {
                        "experience_id": experience_id,
                        "bullets": [
                            {
                                "text": _first_sentence(
                                    records[experience_id], "Delivered project work."
                                ),
                                "source_ids": [experience_id],
                                "confidence": 0.9,
                            }
                        ],
                    }
                    for experience_id in experience_ids[:4]
                ],
                "projects": [],
            }

        if prompt_id == "COVER_LETTER":
            first_id = next(iter(records), None)
            return {
                "paragraphs": [
                    "I am writing to apply for this role.",
                    _first_sentence(
                        records.get(first_id or "", ""),
                        "My background matches the requirements.",
                    ),
                ],
                "source_ids": [first_id] if first_id else sources,
                "confidence": 0.8,
            }

        if prompt_id == "FIELD_MAPPING":
            field_ids = re.findall(r'"field_id"\s*:\s*"([^"]+)"', user)
            return {
                "mappings": [
                    {
                        "field_id": field_id,
                        "target": "unknown",
                        "confidence": 0.0,
                        "rationale": "the mock provider does not guess mappings",
                    }
                    for field_id in field_ids
                ]
            }

        if prompt_id == "CONFIDENCE_EVALUATION":
            return {"confidence": 0.5, "issues": [], "requires_review": True}

        if prompt_id == "APPLICATION_QUESTION":
            return {
                "answer": None,
                "confidence": 0.0,
                "source": "default",
                "source_ids": [],
                "requires_review": True,
                "reasoning": "The mock provider does not compose answers.",
            }

        return {}
