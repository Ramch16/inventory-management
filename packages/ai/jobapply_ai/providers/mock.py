"""Deterministic provider for local development and tests.

It never reaches the network and needs no API key. Responses are schema-shaped and
derived from the input, so tests exercise the real validation and truth-checking paths
rather than a stub that always returns success.
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


def _source_ids(user: str, limit: int = 3) -> list[str]:
    found = list(dict.fromkeys(_SOURCE_ID_RE.findall(user)))
    return found[:limit] or ["profile"]


def _first_sentence(text: str, fallback: str) -> str:
    for line in text.splitlines():
        cleaned = line.strip(" -•\t")
        if len(cleaned) > 30:
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
        if prompt_id in self.responses:
            payload = self.responses[prompt_id]
        else:
            payload = self._synthesize(prompt_id, user)
        raw = json.dumps(payload)
        return raw, TokenUsage(input_tokens=len(user) // 4, output_tokens=len(raw) // 4)

    @staticmethod
    def _infer_prompt_id(system: str, user: str) -> str:
        haystack = f"{system}\n{user}".lower()
        if (
            "converts a job posting" in haystack
            or "job posting:" in haystack
            and "structured" in haystack
        ):
            return "JOB_EXTRACTION"
        if "deterministic scores" in haystack:
            return "JOB_MATCHING"
        if "tailored resume" in haystack or "target length" in haystack:
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
                "explanation": "Deterministic scores drive this recommendation; "
                "the mock provider adds no narrative.",
            }
        if prompt_id == "RESUME_TAILORING":
            experience_ids = [
                sid for sid in _SOURCE_ID_RE.findall(user) if sid.startswith("experience_")
            ]
            return {
                "summary": _first_sentence(user, "Experienced professional."),
                "summary_source_ids": sources,
                "skills": [],
                "experience": [
                    {
                        "experience_id": experience_id,
                        "bullets": [
                            {
                                "text": _first_sentence(user, "Delivered project work."),
                                "source_ids": [experience_id],
                                "confidence": 0.9,
                            }
                        ],
                    }
                    for experience_id in list(dict.fromkeys(experience_ids))[:4]
                ],
                "projects": [],
            }
        if prompt_id == "COVER_LETTER":
            return {
                "paragraphs": [
                    "I am writing to apply for this role.",
                    _first_sentence(user, "My background matches the requirements."),
                ],
                "source_ids": sources,
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
                        "rationale": "mock provider does not guess mappings",
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
