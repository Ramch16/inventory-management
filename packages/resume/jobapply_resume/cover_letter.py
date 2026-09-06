"""Cover letter generation.

A letter is written only when it is actually wanted, and only from approved records.
The same truth layer that guards resume bullets guards every paragraph here, so a
letter cannot claim an affinity, an achievement or a legal status the user never
recorded.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from jobapply_ai.models import JSONCompletionRequest
from jobapply_ai.prompts import get_prompt
from jobapply_ai.provider import AIProvider
from jobapply_shared.logging import get_logger

from jobapply_resume.models import SourceRecord
from jobapply_resume.truth import ResumeTruthLayer, build_source_index

logger = get_logger(__name__)


@dataclass
class CoverLetterDecision:
    should_generate: bool
    reason: str


@dataclass
class CoverLetter:
    text: str
    paragraphs: list[str] = field(default_factory=list)
    source_ids: list[str] = field(default_factory=list)
    confidence: float = 0.0
    model: str | None = None
    provider: str | None = None
    rejected: list[dict[str, Any]] = field(default_factory=list)


def should_generate_cover_letter(
    *, user_enabled: bool, employer_requires: bool | None, job: dict[str, Any]
) -> CoverLetterDecision:
    """Decide whether a letter is warranted.

    Order matters: an employer that requires one always gets one; otherwise the user's
    setting decides; otherwise a letter is offered only where it plausibly helps.
    """
    if employer_requires:
        return CoverLetterDecision(True, "The application form requires a cover letter.")
    if not user_enabled:
        return CoverLetterDecision(False, "Cover letters are switched off in your settings.")
    description = (job.get("description") or "").lower()
    if "cover letter" in description:
        return CoverLetterDecision(True, "The posting mentions a cover letter.")
    if job.get("seniority") and int(job.get("seniority") or 0) >= 4:
        return CoverLetterDecision(
            True, "Senior roles are usually read with a letter alongside the resume."
        )
    return CoverLetterDecision(True, "Cover letters are enabled for your applications.")


class CoverLetterService:
    def __init__(self, provider: AIProvider | None = None) -> None:
        self.provider = provider

    async def generate(
        self, *, sources: list[SourceRecord], job: dict[str, Any], applicant_name: str | None
    ) -> CoverLetter | None:
        """Return a verified letter, or ``None`` when one cannot be produced safely."""
        if self.provider is None:
            return None

        prompt = get_prompt("COVER_LETTER")
        sources_text = "\n".join(f"{record.id}: {record.text}" for record in sources if record.text)
        job_text = json.dumps(
            {
                "title": job.get("title"),
                "company": job.get("company_name"),
                "requirements": job.get("requirements"),
                "skills": job.get("skills"),
            },
            default=str,
        )
        request = JSONCompletionRequest(
            prompt_id=prompt.id,
            system=prompt.system,
            user=prompt.render(
                sources=sources_text, job=job_text, company=job.get("company_name") or ""
            ),
            json_schema=prompt.json_schema,
            max_output_tokens=prompt.max_output_tokens,
            temperature=prompt.temperature,
        )

        try:
            result = await self.provider.complete_json(request)
        except Exception as exc:  # noqa: BLE001 - a missing letter is recoverable
            logger.warning(
                "cover_letter.provider_failed",
                extra={
                    "context": {"event": "cover_letter.provider_failed", "detail": str(exc)[:200]}
                },
            )
            return None

        layer = ResumeTruthLayer(build_source_index(sources))
        claimed = result.data.get("source_ids") or []
        kept: list[str] = []
        rejected: list[dict[str, Any]] = []
        for paragraph in result.data.get("paragraphs") or []:
            verdict = layer.verify_answer(paragraph, claimed)
            if verdict.allowed:
                kept.append(paragraph)
            else:
                rejected.append({"text": paragraph, "reasons": verdict.reasons})

        if len(kept) < 2:
            # A letter that lost most of its content is worse than no letter; the
            # application proceeds with the resume alone.
            logger.info(
                "cover_letter.rejected",
                extra={
                    "context": {
                        "event": "cover_letter.rejected",
                        "kept": len(kept),
                        "rejected": len(rejected),
                    }
                },
            )
            return None

        greeting = (
            f"Dear {job.get('company_name')} hiring team," if job.get("company_name") else "Hello,"
        )
        closing = f"Sincerely,\n{applicant_name}" if applicant_name else "Sincerely,"
        text = "\n\n".join([greeting, *kept, closing])

        return CoverLetter(
            text=text,
            paragraphs=kept,
            source_ids=claimed,
            confidence=float(result.data.get("confidence") or 0.0),
            model=result.model,
            provider=result.provider,
            rejected=rejected,
        )
