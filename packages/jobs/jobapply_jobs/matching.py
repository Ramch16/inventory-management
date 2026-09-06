"""Deterministic job matching.

The score is computed in code, not by a model. A model may later be asked to *explain*
a score, but it never produces or adjusts one — that keeps matching reproducible and
auditable, and means a provider outage degrades explanations rather than the product.

The one rule that overrides everything: never recommend applying when the user
demonstrably fails a hard requirement the posting states.
"""

from __future__ import annotations

from jobapply_shared.enums import MatchRecommendation, RemoteType
from jobapply_shared.text import (
    normalize_company,
    normalize_location,
    normalize_text,
    normalize_title,
    seniority_level,
    title_similarity,
)

from jobapply_jobs.models import MatchProfile, MatchResult, MatchWeights, NormalizedJob

APPLY_THRESHOLD = 75
REVIEW_THRESHOLD = 55


def _pct(value: float) -> int:
    return int(round(max(0.0, min(1.0, value)) * 100))


class JobMatchingService:
    def __init__(self, weights: MatchWeights | None = None) -> None:
        self.weights = weights or MatchWeights()

    # ------------------------------------------------------------------ components
    def score_skills(
        self, profile: MatchProfile, job: NormalizedJob
    ) -> tuple[int, list[str], list[str]]:
        required = [skill for skill in job.skills if skill]
        if not required:
            # The posting lists no recognisable skills: this component cannot
            # discriminate, so it is neutral rather than a free 100.
            return 60, [], []
        owned = {normalize_text(skill) for skill in profile.skills}
        matched = [skill for skill in required if normalize_text(skill) in owned]
        missing = [skill for skill in required if normalize_text(skill) not in owned]
        return _pct(len(matched) / len(required)), matched, missing

    def score_experience(self, profile: MatchProfile, job: NormalizedJob) -> int:
        required = job.experience_required_years
        if required is None:
            return 70
        if profile.years_experience is None:
            return 50
        have = profile.years_experience
        if have >= required:
            # Being far over the requirement is not a better match for the role.
            excess = have - required
            return 100 if excess <= 5 else 88
        shortfall = required - have
        if shortfall <= 1:
            return 80
        if shortfall <= 2:
            return 60
        if shortfall <= 4:
            return 35
        return 10

    def score_title(self, profile: MatchProfile, job: NormalizedJob) -> int:
        candidates = [*profile.titles]
        if profile.current_title:
            candidates.append(profile.current_title)
        if not candidates:
            return 50
        return _pct(max(title_similarity(candidate, job.title) for candidate in candidates))

    def score_seniority(self, profile: MatchProfile, job: NormalizedJob) -> int:
        job_level = seniority_level(job.title)
        profile_levels = [
            level
            for level in (
                seniority_level(profile.current_title),
                *(seniority_level(title) for title in profile.titles),
            )
            if level is not None
        ]
        if job_level is None or not profile_levels:
            return 70
        distance = min(abs(job_level - level) for level in profile_levels)
        return {0: 100, 1: 80, 2: 50}.get(distance, 20)

    def score_education(self, profile: MatchProfile, job: NormalizedJob) -> int:
        if not job.education:
            return 80
        if not profile.education_level:
            return 50
        ranks = {
            "associate": 1,
            "bachelor": 2,
            "b.s": 2,
            "b.a": 2,
            "master": 3,
            "m.s": 3,
            "m.a": 3,
            "mba": 3,
            "phd": 4,
            "doctorate": 4,
        }

        def rank(value: str) -> int:
            lowered = normalize_text(value)
            return max((score for token, score in ranks.items() if token in lowered), default=0)

        required, have = rank(job.education), rank(profile.education_level)
        if required == 0:
            return 80
        if have >= required:
            return 100
        return 45 if required - have == 1 else 20

    def score_location(self, profile: MatchProfile, job: NormalizedJob) -> int:
        if job.remote_type == RemoteType.REMOTE:
            if profile.remote_preference in (None, RemoteType.REMOTE, RemoteType.HYBRID):
                return 100
            return 70
        if profile.remote_preference == RemoteType.REMOTE and job.remote_type in (
            RemoteType.ONSITE,
            RemoteType.HYBRID,
        ):
            return 25
        if not profile.locations or not job.normalized_location:
            return 60
        job_location = normalize_location(job.location)
        for wanted in profile.locations:
            candidate = normalize_location(wanted)
            if candidate and (candidate in job_location or job_location.startswith(candidate)):
                return 100
        return 70 if profile.open_to_relocation else 30

    def score_authorization(
        self, profile: MatchProfile, job: NormalizedJob
    ) -> tuple[int, list[str]]:
        """Scored only from what the user explicitly declared and what the posting
        explicitly says. Silence on either side is neutral, never an assumption."""
        risks: list[str] = []
        if profile.requires_sponsorship_now is None or profile.requires_sponsorship_future is None:
            return 50, ["Work authorization is not declared, so this cannot be assessed."]

        needs_sponsorship = bool(
            profile.requires_sponsorship_now or profile.requires_sponsorship_future
        )
        if not needs_sponsorship:
            return 100, risks

        if job.sponsorship_offered is True:
            return 100, risks
        if job.sponsorship_offered is False:
            return 0, ["The posting states it does not provide sponsorship, which you require."]
        if job.sponsorship_information:
            return 45, [
                "The posting mentions sponsorship without a clear answer — "
                "check it before applying."
            ]
        return 55, ["The posting does not mention sponsorship, which you require."]

    # ---------------------------------------------------------------------- overall
    def score(
        self, profile: MatchProfile, job: NormalizedJob, weights: MatchWeights | None = None
    ) -> MatchResult:
        active_weights = (weights or self.weights).normalized()

        skills_score, matched_skills, missing_skills = self.score_skills(profile, job)
        experience_score = self.score_experience(profile, job)
        title_score = self.score_title(profile, job)
        seniority_score = self.score_seniority(profile, job)
        education_score = self.score_education(profile, job)
        location_score = self.score_location(profile, job)
        authorization_score, risks = self.score_authorization(profile, job)

        overall = (
            skills_score * active_weights["skills"]
            + experience_score * active_weights["experience"]
            + title_score * active_weights["title"]
            + education_score * active_weights["education"]
            + location_score * active_weights["location"]
            + authorization_score * active_weights["authorization"]
        )
        # Seniority is a modifier rather than a weighted component: a wildly
        # mismatched level should pull the whole score down, not average out.
        overall *= 0.85 + 0.15 * (seniority_score / 100)
        score = int(round(overall))

        hard_failed = False

        if authorization_score == 0:
            hard_failed = True

        excluded_companies = {normalize_company(name) for name in profile.excluded_companies}
        if job.normalized_company in excluded_companies:
            hard_failed = True
            risks.append("This company is on your excluded list.")

        excluded_titles = [normalize_title(title) for title in profile.excluded_titles if title]
        job_title = job.normalized_title
        if any(excluded and excluded in job_title for excluded in excluded_titles):
            hard_failed = True
            risks.append("The title matches one of your excluded titles.")

        haystack = normalize_text(f"{job.title} {job.description or ''}")
        for keyword in profile.excluded_keywords:
            if keyword and normalize_text(keyword) in haystack:
                hard_failed = True
                risks.append(f"The posting contains your excluded keyword '{keyword}'.")
                break

        if (
            profile.salary_min
            and job.salary_max is not None
            and job.salary_max < profile.salary_min
        ):
            hard_failed = True
            risks.append(
                f"The stated maximum salary ({job.salary_max:,}) is below your minimum "
                f"({profile.salary_min:,})."
            )

        if (
            profile.employment_types
            and job.employment_type.value != "unknown"
            and job.employment_type not in profile.employment_types
        ):
            risks.append(f"Employment type is {job.employment_type.value.replace('_', ' ')}.")

        if missing_skills:
            risks.append(f"Missing {len(missing_skills)} of the listed skills.")

        if hard_failed:
            recommendation = MatchRecommendation.SKIP
        elif score >= APPLY_THRESHOLD:
            recommendation = MatchRecommendation.APPLY
        elif score >= REVIEW_THRESHOLD:
            recommendation = MatchRecommendation.REVIEW
        else:
            recommendation = MatchRecommendation.SKIP

        return MatchResult(
            score=score,
            skills_score=skills_score,
            experience_score=experience_score,
            education_score=education_score,
            location_score=location_score,
            authorization_score=authorization_score,
            title_score=title_score,
            seniority_score=seniority_score,
            recommendation=recommendation,
            matched_skills=matched_skills,
            missing_skills=missing_skills,
            risks=risks,
            hard_requirement_failed=hard_failed,
            explanation=self._explain(
                score, recommendation, matched_skills, missing_skills, risks, hard_failed
            ),
            weights=active_weights,
        )

    @staticmethod
    def _explain(
        score: int,
        recommendation: MatchRecommendation,
        matched: list[str],
        missing: list[str],
        risks: list[str],
        hard_failed: bool,
    ) -> str:
        """A deterministic summary. The AI explanation, when enabled, replaces this
        prose but never the numbers."""
        parts = [f"Overall fit {score}/100."]
        if matched:
            parts.append(f"Matches {len(matched)} listed skills ({', '.join(matched[:5])}).")
        if missing:
            parts.append(f"Missing {', '.join(missing[:5])}.")
        if hard_failed:
            parts.append(
                "A hard requirement or one of your exclusions fails, "
                "so applying is not recommended."
            )
        elif recommendation == MatchRecommendation.APPLY:
            parts.append("Strong enough to apply.")
        elif recommendation == MatchRecommendation.REVIEW:
            parts.append("Worth a look before applying.")
        else:
            parts.append("Below your bar for this profile.")
        if risks and not hard_failed:
            parts.append(risks[0])
        return " ".join(parts)
