"""ApplicationQuestionService.

The resolution order is fixed and non-negotiable:

1. explicit, user-provided profile data;
2. data derived from the user's own resume/experience records;
3. a model, and only to phrase an answer from facts already established.

A legally significant question — work authorization, sponsorship, demographics,
disability, veteran status, criminal history, compensation, any attestation — is
answered *only* from an explicit profile field. If that field is absent, the run
pauses and asks the user. A model is never allowed to supply one, and silence is
never read as an answer.

Every answer carries a confidence, a source and a ``requires_review`` flag. Below the
review threshold, or sensitive without explicit data, means a human sees it first.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from jobapply_ai.models import JSONCompletionRequest
from jobapply_ai.prompts import get_prompt
from jobapply_ai.provider import AIProvider
from jobapply_resume.truth import ResumeTruthLayer
from jobapply_shared.enums import AnswerSource
from jobapply_shared.logging import get_logger
from jobapply_shared.text import normalize_text, similarity

from jobapply_browser.models import FieldMapping, NormalizedField, ResolvedAnswer

logger = get_logger(__name__)

#: Answers at or above this are filled without asking.
AUTO_THRESHOLD = 0.95
#: Below this, a person reviews the answer.
REVIEW_THRESHOLD = 0.80

YES_TOKENS = ("yes", "y", "true", "i am", "i do", "authorized", "eligible")
NO_TOKENS = ("no", "n", "false", "i am not", "i do not", "not required")
DECLINE_TOKENS = (
    "decline",
    "prefer not",
    "do not wish",
    "don't wish",
    "not to answer",
    "choose not",
    "i do not wish to answer",
)


@dataclass
class AnswerContext:
    """The facts available to answer with, all of them user-supplied."""

    profile: dict[str, Any] = field(default_factory=dict)
    skill_years: dict[str, float] = field(default_factory=dict)
    education: list[dict[str, Any]] = field(default_factory=list)
    experiences: list[dict[str, Any]] = field(default_factory=list)
    job: dict[str, Any] = field(default_factory=dict)
    #: Answers the user has previously given and approved, keyed by question text.
    saved_answers: dict[str, str] = field(default_factory=dict)


def _first_matching_option(options: list, tokens: tuple[str, ...]) -> str | None:
    for option in options:
        label = normalize_text(option.label)
        if any(label == token or label.startswith(token) for token in tokens):
            return option.value
    for option in options:
        label = normalize_text(option.label)
        if any(token in label for token in tokens):
            return option.value
    return None


def _boolean_option(field_: NormalizedField, value: bool) -> str | None:
    """Pick the option that expresses ``value`` on a yes/no control."""
    if not field_.options:
        return "Yes" if value else "No"
    return _first_matching_option(field_.options, YES_TOKENS if value else NO_TOKENS)


def _decline_option(field_: NormalizedField) -> str | None:
    return _first_matching_option(field_.options, DECLINE_TOKENS) if field_.options else None


def _match_option(field_: NormalizedField, value: str) -> tuple[str | None, float]:
    """Map a free-text value onto one of the control's options."""
    if not field_.options:
        return value, 0.97
    target = normalize_text(value)
    for option in field_.options:
        if normalize_text(option.label) == target or option.value == value:
            return option.value, 0.97
    best, score = None, 0.0
    for option in field_.options:
        ratio = similarity(option.label, value)
        if ratio > score:
            best, score = option.value, ratio
    if score >= 0.9:
        return best, 0.9
    if score >= 0.75:
        return best, 0.78  # below the review threshold on purpose
    return None, 0.0


class ApplicationQuestionService:
    def __init__(
        self,
        *,
        provider: AIProvider | None = None,
        truth_layer: ResumeTruthLayer | None = None,
        auto_threshold: float = AUTO_THRESHOLD,
        review_threshold: float = REVIEW_THRESHOLD,
    ) -> None:
        self.provider = provider
        self.truth_layer = truth_layer
        self.auto_threshold = auto_threshold
        self.review_threshold = review_threshold

    # ------------------------------------------------------------------ helpers
    def _finalize(self, answer: ResolvedAnswer) -> ResolvedAnswer:
        """Apply the confidence bands. Sensitive answers never auto-fill on a model's
        say-so, and anything under the review threshold goes to a person."""
        if answer.answer is None:
            answer.requires_review = True
            return answer
        if answer.is_sensitive and answer.source not in (
            AnswerSource.PROFILE,
            AnswerSource.USER_PROVIDED,
        ):
            answer.requires_review = True
            answer.reason = answer.reason or (
                "Sensitive questions are answered only from an explicit profile field."
            )
            return answer
        if answer.confidence >= self.auto_threshold:
            # A direct restatement of a field the user entered and confirmed.
            answer.requires_review = False
        elif answer.confidence >= self.review_threshold and not answer.is_sensitive:
            # Confident enough to fill, but only because nothing sensitive rides on it.
            answer.requires_review = False
        else:
            answer.requires_review = True
        return answer

    @staticmethod
    def _blank(field_: NormalizedField, mapping: FieldMapping, reason: str) -> ResolvedAnswer:
        return ResolvedAnswer(
            field_id=field_.field_id,
            answer=None,
            confidence=0.0,
            source=AnswerSource.DEFAULT,
            requires_review=True,
            category=mapping.category,
            is_sensitive=mapping.is_sensitive,
            reason=reason,
        )

    # ------------------------------------------------------------- deterministic
    def resolve_deterministic(
        self, field_: NormalizedField, mapping: FieldMapping, context: AnswerContext
    ) -> ResolvedAnswer | None:
        """Answer from explicit user data. Returns ``None`` when this layer cannot."""
        profile = context.profile
        target = mapping.target

        if target is None:
            return None

        # --- previously approved answer for the same question -----------------
        question_key = normalize_text(field_.question or field_.label or "")
        if question_key and question_key in context.saved_answers:
            return ResolvedAnswer(
                field_id=field_.field_id,
                answer=context.saved_answers[question_key],
                confidence=0.99,
                source=AnswerSource.USER_PROVIDED,
                source_ids=["saved_answer"],
                category=mapping.category,
                is_sensitive=mapping.is_sensitive,
                reason="You answered this question before and approved the answer.",
            )

        # --- sensitive: explicit profile fields only --------------------------
        if target == "profile.work_authorized":
            if profile.get("requires_sponsorship_now") is None:
                return self._blank(
                    field_, mapping, "Declare your work authorization in your profile first."
                )
            authorized = not profile.get("requires_sponsorship_now")
            value = _boolean_option(field_, authorized)
            return ResolvedAnswer(
                field_id=field_.field_id,
                answer=value,
                confidence=0.99 if value else 0.0,
                source=AnswerSource.PROFILE,
                source_ids=["profile.authorization"],
                category=mapping.category,
                is_sensitive=True,
                reason="From the work authorization you declared.",
            )

        if target == "profile.requires_sponsorship":
            now = profile.get("requires_sponsorship_now")
            future = profile.get("requires_sponsorship_future")
            if now is None or future is None:
                return self._blank(
                    field_, mapping, "Declare your sponsorship answers in your profile first."
                )
            text = normalize_text(field_.question or field_.label or "")
            needs = bool(future) if "future" in text else bool(now or future)
            value = _boolean_option(field_, needs)
            return ResolvedAnswer(
                field_id=field_.field_id,
                answer=value,
                confidence=0.99 if value else 0.0,
                source=AnswerSource.PROFILE,
                source_ids=["profile.authorization"],
                category=mapping.category,
                is_sensitive=True,
                reason="From the sponsorship answers you declared.",
            )

        if target == "profile.salary_expectation":
            minimum = profile.get("salary_min")
            if not minimum:
                return self._blank(
                    field_, mapping, "Set your salary expectation in your profile first."
                )
            return ResolvedAnswer(
                field_id=field_.field_id,
                answer=str(minimum),
                # Deliberately below the auto band: a stated minimum is not the same
                # as the number the user wants to put on this application, so the
                # draft is shown to them before it is sent.
                confidence=0.90,
                source=AnswerSource.PROFILE,
                source_ids=["profile.salary_min"],
                category=mapping.category,
                is_sensitive=True,
                reason=(
                    "Drafted from the minimum salary in your profile — confirm the "
                    "figure before it is submitted."
                ),
            )

        if target in {
            "sensitive.disability",
            "sensitive.veteran",
            "sensitive.demographic",
            "sensitive.criminal_history",
        }:
            # These are the user's to answer. The platform will offer the form's own
            # "decline to answer" option as a draft, but never submits it unreviewed.
            decline = _decline_option(field_)
            return ResolvedAnswer(
                field_id=field_.field_id,
                answer=decline,
                confidence=0.0,
                source=AnswerSource.DEFAULT,
                category=mapping.category,
                is_sensitive=True,
                requires_review=True,
                reason=(
                    "This is a protected characteristic. Only you can answer it — "
                    "the form's decline option is offered as a starting point."
                ),
            )

        if target == "sensitive.legal_attestation":
            return self._blank(
                field_,
                mapping,
                "This is a legal attestation. You must read and accept it yourself.",
            )

        # --- ordinary profile fields ------------------------------------------
        simple: dict[str, Any] = {
            "profile.first_name": profile.get("first_name"),
            "profile.last_name": profile.get("last_name"),
            "profile.preferred_name": profile.get("preferred_name") or profile.get("first_name"),
            "profile.email": profile.get("email"),
            "profile.phone": profile.get("phone"),
            "profile.city": profile.get("city"),
            "profile.state": profile.get("state"),
            "profile.country": profile.get("country"),
            "profile.postal_code": profile.get("postal_code"),
            "profile.linkedin_url": profile.get("linkedin_url"),
            "profile.github_url": profile.get("github_url"),
            "profile.portfolio_url": profile.get("portfolio_url"),
            "profile.current_title": profile.get("current_title"),
        }
        if target == "profile.full_name":
            simple[target] = " ".join(
                part for part in (profile.get("first_name"), profile.get("last_name")) if part
            )
        if target == "profile.location":
            simple[target] = ", ".join(
                part
                for part in (profile.get("city"), profile.get("state"), profile.get("country"))
                if part
            )
        if target == "profile.current_company":
            current = next(
                (item for item in context.experiences if item.get("is_current")),
                context.experiences[0] if context.experiences else None,
            )
            simple[target] = current.get("company") if current else None
        if target == "profile.years_experience":
            years = profile.get("years_experience")
            simple[target] = str(int(years)) if years is not None else None
        if target in {"profile.education_school", "profile.education_degree"}:
            latest = context.education[0] if context.education else None
            simple[target] = (
                (latest or {}).get("institution")
                if target.endswith("school")
                else (latest or {}).get("degree")
            )

        if target in simple:
            value = simple[target]
            if not value:
                return self._blank(field_, mapping, "This is not filled in on your profile yet.")
            matched, confidence = _match_option(field_, str(value))
            if matched is None:
                return self._blank(
                    field_, mapping, "Your value does not match any of the form's options."
                )
            return ResolvedAnswer(
                field_id=field_.field_id,
                answer=matched,
                confidence=confidence,
                source=AnswerSource.PROFILE,
                source_ids=[target],
                category=mapping.category,
                is_sensitive=mapping.is_sensitive,
            )

        if target == "answer.skill_years":
            skill = self._extract_skill(field_)
            if not skill:
                return None
            years = context.skill_years.get(normalize_text(skill))
            if years is None:
                return self._blank(
                    field_,
                    mapping,
                    f"Your profile does not record how long you have used {skill}.",
                )
            return ResolvedAnswer(
                field_id=field_.field_id,
                answer=str(int(years)),
                confidence=0.97,
                source=AnswerSource.PROFILE,
                source_ids=[f"skill:{normalize_text(skill)}"],
                category=mapping.category,
                reason=f"From the {years:g} years recorded for {skill}.",
            )

        return None

    @staticmethod
    def _extract_skill(field_: NormalizedField) -> str | None:
        text = field_.question or field_.label or ""
        patterns = (
            r"(?i)years?\s+of\s+([A-Za-z0-9.+#/ -]{2,30}?)\s+experience",
            r"(?i)experience\s+(?:with|in|using)\s+([A-Za-z0-9.+#/ -]{2,30}?)\s*[?.,]?$",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return None

    # --------------------------------------------------------------------- ai
    async def resolve_with_ai(
        self, field_: NormalizedField, mapping: FieldMapping, context: AnswerContext
    ) -> ResolvedAnswer:
        """Phrase an answer from established facts. Never used for sensitive fields."""
        if mapping.is_sensitive:
            return self._blank(
                field_,
                mapping,
                "Sensitive questions are never answered by a model.",
            )
        if self.provider is None:
            return self._blank(field_, mapping, "No answer could be derived from your profile.")

        prompt = get_prompt("APPLICATION_QUESTION")
        facts = json.dumps(
            {
                "profile": {
                    key: value
                    for key, value in context.profile.items()
                    # Legally significant fields are not even shown to the model.
                    if key
                    not in {
                        "requires_sponsorship_now",
                        "requires_sponsorship_future",
                        "authorization_type",
                        "authorization_country",
                    }
                },
                "experience": context.experiences[:5],
                "skill_years": context.skill_years,
            },
            default=str,
        )
        request = JSONCompletionRequest(
            prompt_id=prompt.id,
            system=prompt.system,
            user=prompt.render(
                question=field_.question or field_.label or "",
                field_type=str(field_.type),
                options=", ".join(option.label for option in field_.options) or "free text",
                facts=facts,
                job=json.dumps(
                    {"title": context.job.get("title"), "company": context.job.get("company_name")}
                ),
            ),
            json_schema=prompt.json_schema,
            max_output_tokens=prompt.max_output_tokens,
            temperature=prompt.temperature,
        )

        try:
            result = await self.provider.complete_json(request)
        except Exception as exc:  # noqa: BLE001 - an unanswered field pauses the run
            logger.warning(
                "questions.provider_failed",
                extra={"context": {"event": "questions.provider_failed", "detail": str(exc)[:200]}},
            )
            return self._blank(field_, mapping, "The answer could not be generated.")

        text = result.data.get("answer")
        if not text:
            return self._blank(
                field_, mapping, result.data.get("reasoning") or "No answer was produced."
            )

        confidence = float(result.data.get("confidence") or 0.0)
        source_ids = list(result.data.get("source_ids") or [])

        if self.truth_layer is not None:
            verdict = self.truth_layer.verify_answer(text, source_ids or ["profile"])
            if not verdict.allowed:
                return self._blank(
                    field_,
                    mapping,
                    "The generated answer could not be traced to your records: "
                    + "; ".join(verdict.reasons[:2]),
                )
            confidence = min(confidence, verdict.confidence)

        return ResolvedAnswer(
            field_id=field_.field_id,
            answer=text,
            # A generated answer never reaches the auto-fill band on its own.
            confidence=min(confidence, 0.94),
            source=AnswerSource.AI_GENERATED,
            source_ids=source_ids,
            category=mapping.category,
            is_sensitive=mapping.is_sensitive,
            requires_review=bool(result.data.get("requires_review", True)),
        )

    # ------------------------------------------------------------------- entry
    async def answer(
        self, field_: NormalizedField, mapping: FieldMapping, context: AnswerContext
    ) -> ResolvedAnswer:
        deterministic = self.resolve_deterministic(field_, mapping, context)
        if deterministic is not None:
            return self._finalize(deterministic)
        generated = await self.resolve_with_ai(field_, mapping, context)
        return self._finalize(generated)

    async def answer_all(
        self,
        fields: list[NormalizedField],
        mappings: list[FieldMapping],
        context: AnswerContext,
    ) -> list[ResolvedAnswer]:
        by_id = {mapping.field_id: mapping for mapping in mappings}
        results: list[ResolvedAnswer] = []
        for field_ in fields:
            mapping = by_id.get(field_.field_id) or FieldMapping(field_id=field_.field_id)
            results.append(await self.answer(field_, mapping, context))
        return results
