"""Resume tailoring.

The flow is deliberately narrow:

    approved records + job posting
        -> AI proposes a selection and rewording (JSON, schema-validated)
        -> ResumeTruthLayer verifies every statement against the records
        -> anything unverifiable is dropped, and the user's own wording is used
        -> a TailoredResume with per-statement provenance

The model never introduces a fact. Its job is selection, ordering and phrasing.
If the provider is unavailable or its output cannot be verified, tailoring still
succeeds — it simply falls back to the user's own bullets, prioritised
deterministically against the posting.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from jobapply_ai.models import JSONCompletionRequest
from jobapply_ai.prompts import get_prompt
from jobapply_ai.provider import AIProvider
from jobapply_shared.errors import ProviderError
from jobapply_shared.logging import get_logger
from jobapply_shared.text import normalize_text

from jobapply_resume.models import (
    ContactInfo,
    ProvenanceRecord,
    SourceRecord,
    TailoredBullet,
    TailoredEducation,
    TailoredExperience,
    TailoredProject,
    TailoredResume,
)
from jobapply_resume.truth import ResumeTruthLayer, build_source_index

logger = get_logger(__name__)

#: How many bullets a tailored role keeps, by resume length.
BULLETS_PER_ROLE = {1: 3, 2: 4, 3: 5}


@dataclass
class TailoringInputs:
    """Everything tailoring is allowed to draw on."""

    contact: ContactInfo
    sources: list[SourceRecord]
    experiences: list[dict[str, Any]] = field(default_factory=list)
    education: list[dict[str, Any]] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    projects: list[dict[str, Any]] = field(default_factory=list)
    summary: str | None = None


@dataclass
class TailoringOutcome:
    document: TailoredResume
    #: Statements the truth layer rejected, with reasons, for the audit trail.
    rejected: list[dict[str, Any]] = field(default_factory=list)
    used_ai: bool = False
    ai_model: str | None = None
    ai_provider: str | None = None


def _relevance(text: str, job_terms: set[str]) -> int:
    """How many of the posting's terms a bullet actually mentions."""
    words = set(normalize_text(text).split())
    return len(words & job_terms)


def _job_terms(job: dict[str, Any]) -> set[str]:
    parts = [
        job.get("title") or "",
        " ".join(job.get("skills") or []),
        " ".join(job.get("requirements") or []),
        " ".join(job.get("preferred_qualifications") or []),
    ]
    return {word for word in normalize_text(" ".join(parts)).split() if len(word) > 2}


class ResumeTailoringService:
    def __init__(self, provider: AIProvider | None = None) -> None:
        self.provider = provider

    # ------------------------------------------------------------------ fallback
    def _deterministic(
        self, inputs: TailoringInputs, job: dict[str, Any], max_pages: int
    ) -> TailoredResume:
        """Select and order the user's own content against the posting.

        No rewriting happens here: every bullet is exactly what the user wrote, so
        there is nothing to verify.
        """
        terms = _job_terms(job)
        keep = BULLETS_PER_ROLE.get(max_pages, 4)

        experiences: list[TailoredExperience] = []
        for record in inputs.experiences:
            bullets = list(record.get("accomplishments") or [])
            ranked = sorted(bullets, key=lambda text: _relevance(text, terms), reverse=True)
            source_id = f"experience_{record['id']}"
            experiences.append(
                TailoredExperience(
                    experience_id=source_id,
                    company=record["company"],
                    title=record["title"],
                    location=record.get("location"),
                    start_date=record.get("start_date"),
                    end_date=record.get("end_date"),
                    is_current=bool(record.get("is_current")),
                    bullets=[
                        TailoredBullet(text=text, source_ids=[source_id], confidence=1.0)
                        for text in ranked[:keep]
                    ],
                )
            )

        skills = sorted(
            inputs.skills,
            key=lambda skill: (normalize_text(skill) in terms, skill.lower()),
            reverse=True,
        )

        return TailoredResume(
            contact=inputs.contact,
            summary=inputs.summary,
            summary_source_ids=["profile"] if inputs.summary else [],
            skills=skills,
            experience=experiences,
            education=[
                TailoredEducation(
                    education_id=f"education_{record['id']}",
                    institution=record["institution"],
                    degree=record.get("degree"),
                    field_of_study=record.get("field_of_study"),
                    end_date=record.get("end_date"),
                    gpa=record.get("gpa"),
                )
                for record in inputs.education
            ],
            certifications=list(inputs.certifications),
            projects=[
                TailoredProject(
                    project_id=f"project_{record['id']}",
                    name=record["name"],
                    highlights=[
                        TailoredBullet(
                            text=text,
                            source_ids=[f"project_{record['id']}"],
                            confidence=1.0,
                        )
                        for text in (record.get("highlights") or [])[:3]
                    ],
                    technologies=list(record.get("technologies") or []),
                )
                for record in inputs.projects
            ],
            max_pages=max_pages,
        )

    # ----------------------------------------------------------------------- main
    async def tailor(
        self,
        inputs: TailoringInputs,
        job: dict[str, Any],
        *,
        max_pages: int = 2,
        template: str = "ats_classic",
    ) -> TailoringOutcome:
        base = self._deterministic(inputs, job, max_pages)
        base.template = template
        layer = ResumeTruthLayer(build_source_index(inputs.sources))

        if self.provider is None:
            base.provenance = _provenance_from(base)
            return TailoringOutcome(document=base)

        try:
            proposal, model, provider_name = await self._ask_provider(inputs, job, max_pages)
        except (ProviderError, Exception) as exc:  # noqa: BLE001 - fallback is the point
            logger.warning(
                "resume.tailoring_provider_failed",
                extra={
                    "context": {
                        "event": "resume.tailoring_provider_failed",
                        "detail": str(exc)[:200],
                    }
                },
            )
            base.provenance = _provenance_from(base)
            return TailoringOutcome(document=base)

        document, rejected = self._merge_verified(base, proposal, layer)
        document.provenance = _provenance_from(document)
        return TailoringOutcome(
            document=document,
            rejected=rejected,
            used_ai=True,
            ai_model=model,
            ai_provider=provider_name,
        )

    async def _ask_provider(
        self, inputs: TailoringInputs, job: dict[str, Any], max_pages: int
    ) -> tuple[dict[str, Any], str, str]:
        prompt = get_prompt("RESUME_TAILORING")
        sources_text = "\n".join(
            f"{record.id}: {record.text}" for record in inputs.sources if record.text
        )
        job_text = json.dumps(
            {
                "title": job.get("title"),
                "company": job.get("company_name"),
                "skills": job.get("skills"),
                "requirements": job.get("requirements"),
                "preferred_qualifications": job.get("preferred_qualifications"),
            },
            default=str,
        )
        request = JSONCompletionRequest(
            prompt_id=prompt.id,
            system=prompt.system,
            user=prompt.render(sources=sources_text, job=job_text, max_pages=max_pages),
            json_schema=prompt.json_schema,
            max_output_tokens=prompt.max_output_tokens,
            temperature=prompt.temperature,
        )
        result = await self.provider.complete_json(request)  # type: ignore[union-attr]
        return result.data, result.model, result.provider

    def _merge_verified(
        self, base: TailoredResume, proposal: dict[str, Any], layer: ResumeTruthLayer
    ) -> tuple[TailoredResume, list[dict[str, Any]]]:
        """Accept only the parts of the proposal the truth layer allows.

        A rejected bullet is replaced by the user's own wording rather than dropped,
        so the resume never gets thinner because a model misbehaved.
        """
        rejected: list[dict[str, Any]] = []
        document = base.model_copy(deep=True)

        summary = proposal.get("summary")
        summary_sources = proposal.get("summary_source_ids") or []
        if summary:
            verdict = layer.verify_statement(summary, summary_sources)
            if verdict.allowed:
                document.summary = summary
                document.summary_source_ids = verdict.matched_source_ids
            else:
                rejected.append({"section": "summary", "text": summary, "reasons": verdict.reasons})

        proposed_skills = proposal.get("skills") or []
        if proposed_skills:
            known = {normalize_text(skill) for skill in base.skills}
            kept = [skill for skill in proposed_skills if normalize_text(skill) in known]
            dropped = [skill for skill in proposed_skills if normalize_text(skill) not in known]
            for skill in dropped:
                rejected.append(
                    {
                        "section": "skills",
                        "text": skill,
                        "reasons": ["skill is not in the profile"],
                    }
                )
            if kept:
                # Keep the model's ordering for the skills it kept, then append the
                # rest of the user's skills so nothing is silently lost.
                remaining = [
                    skill
                    for skill in base.skills
                    if normalize_text(skill) not in {normalize_text(item) for item in kept}
                ]
                document.skills = kept + remaining

        proposed_experience = {
            item.get("experience_id"): item for item in proposal.get("experience") or []
        }
        for experience in document.experience:
            proposed = proposed_experience.get(experience.experience_id)
            if not proposed:
                continue
            verified: list[TailoredBullet] = []
            for bullet in proposed.get("bullets") or []:
                text = bullet.get("text", "")
                sources = bullet.get("source_ids") or []
                verdict = layer.verify_statement(text, sources)
                if verdict.allowed:
                    verified.append(
                        TailoredBullet(
                            text=text,
                            source_ids=verdict.matched_source_ids,
                            confidence=verdict.confidence,
                        )
                    )
                else:
                    rejected.append(
                        {
                            "section": f"experience:{experience.experience_id}",
                            "text": text,
                            "reasons": verdict.reasons,
                        }
                    )
            if verified:
                experience.bullets = verified

        return document, rejected


def _provenance_from(document: TailoredResume) -> list[ProvenanceRecord]:
    records: list[ProvenanceRecord] = []
    if document.summary:
        records.append(
            ProvenanceRecord(
                generated_text=document.summary,
                source_ids=document.summary_source_ids,
                confidence=1.0 if not document.summary_source_ids else 0.95,
                section="summary",
            )
        )
    for experience in document.experience:
        for bullet in experience.bullets:
            records.append(
                ProvenanceRecord(
                    generated_text=bullet.text,
                    source_ids=bullet.source_ids,
                    confidence=bullet.confidence,
                    section=f"experience:{experience.experience_id}",
                )
            )
    for project in document.projects:
        for highlight in project.highlights:
            records.append(
                ProvenanceRecord(
                    generated_text=highlight.text,
                    source_ids=highlight.source_ids,
                    confidence=highlight.confidence,
                    section=f"project:{project.project_id}",
                )
            )
    return records
