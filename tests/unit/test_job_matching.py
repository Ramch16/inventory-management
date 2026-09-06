"""Match scoring is deterministic, weighted and refuses to recommend a hard fail."""

from __future__ import annotations

import pytest
from jobapply_jobs.matching import JobMatchingService
from jobapply_jobs.models import MatchProfile, MatchWeights, RawJob
from jobapply_jobs.normalize import JobNormalizer
from jobapply_shared.enums import MatchRecommendation, RemoteType

normalizer = JobNormalizer()


def job(**overrides):
    base = {
        "source_slug": "sample",
        "source_job_id": "1",
        "company": "Northwind Analytics",
        "title": "Senior Data Engineer",
        "location": "San Francisco, CA",
        "description": (
            "Requirements\n- 5+ years of experience building pipelines\n"
            "- Strong Python and SQL\n- Airflow and dbt\n- Bachelor's degree\n"
        ),
    }
    base.update(overrides)
    return normalizer.normalize(RawJob(**base))


def profile(**overrides) -> MatchProfile:
    base = {
        "titles": ["Data Engineer"],
        "current_title": "Senior Data Engineer",
        "years_experience": 6.0,
        "skills": ["Python", "SQL", "Airflow", "dbt"],
        "education_level": "B.S. Computer Science",
        "locations": ["San Francisco, CA"],
        "requires_sponsorship_now": False,
        "requires_sponsorship_future": False,
    }
    base.update(overrides)
    return MatchProfile(**base)


@pytest.fixture
def service() -> JobMatchingService:
    return JobMatchingService()


def test_a_strong_fit_is_recommended(service):
    result = service.score(profile(), job())
    assert result.score >= 85
    assert result.recommendation == MatchRecommendation.APPLY
    assert set(result.matched_skills) >= {"python", "sql", "airflow", "dbt"}
    assert result.missing_skills == []


def test_missing_skills_lower_the_score(service):
    weak = service.score(profile(skills=["Python"]), job())
    strong = service.score(profile(), job())
    assert weak.score < strong.score
    assert "sql" in weak.missing_skills


def test_experience_shortfall_lowers_the_score(service):
    junior = service.score(profile(years_experience=1.0), job())
    senior = service.score(profile(years_experience=6.0), job())
    assert junior.score < senior.score
    assert junior.experience_score < 50


def test_an_undeclared_authorization_is_neutral_not_assumed(service):
    result = service.score(
        profile(requires_sponsorship_now=None, requires_sponsorship_future=None), job()
    )
    assert result.authorization_score == 50
    assert any("not declared" in risk.lower() for risk in result.risks)


def test_a_stated_no_sponsorship_posting_is_a_hard_fail_for_a_candidate_who_needs_it(service):
    posting = job(
        description="Requirements\n- Python\n\nWe are unable to sponsor work visas for this role."
    )
    assert posting.sponsorship_offered is False

    result = service.score(
        profile(requires_sponsorship_now=True, requires_sponsorship_future=True), posting
    )
    assert result.hard_requirement_failed is True
    assert result.recommendation == MatchRecommendation.SKIP


def test_silence_about_sponsorship_is_a_risk_not_a_hard_fail(service):
    result = service.score(
        profile(requires_sponsorship_now=True, requires_sponsorship_future=True), job()
    )
    assert result.hard_requirement_failed is False
    assert any("does not mention sponsorship" in risk for risk in result.risks)


def test_excluded_company_and_title_are_hard_fails(service):
    excluded_company = service.score(
        profile(excluded_companies=["Northwind Analytics, Inc."]), job()
    )
    assert excluded_company.hard_requirement_failed
    assert excluded_company.recommendation == MatchRecommendation.SKIP

    excluded_title = service.score(
        profile(excluded_titles=["senior director"]), job(title="Senior Director of Engineering")
    )
    assert excluded_title.hard_requirement_failed


def test_excluded_keyword_is_a_hard_fail(service):
    result = service.score(
        profile(excluded_keywords=["commission-only"]),
        job(description="Requirements\n- Sales\n\nThis role is commission-only."),
    )
    assert result.hard_requirement_failed


def test_salary_below_the_users_minimum_is_a_hard_fail(service):
    posting = job(description="Requirements\n- Python\n\nCompensation: $80,000 - $95,000 per year")
    result = service.score(profile(salary_min=150_000), posting)
    assert result.hard_requirement_failed
    assert any("below your minimum" in risk for risk in result.risks)


def test_remote_preference_penalises_an_onsite_role(service):
    onsite = job(description="Requirements\n- Python\n\nThis role is on-site five days a week.")
    result = service.score(profile(remote_preference=RemoteType.REMOTE, locations=[]), onsite)
    assert result.location_score <= 30


def test_weights_are_configurable_and_change_the_outcome(service):
    posting = job()
    weak_skills = profile(skills=["Python"])

    skill_heavy = service.score(
        weak_skills,
        posting,
        MatchWeights(
            skills=0.9,
            experience=0.02,
            title=0.02,
            education=0.02,
            location=0.02,
            authorization=0.02,
        ),
    )
    skill_light = service.score(
        weak_skills,
        posting,
        MatchWeights(
            skills=0.02, experience=0.3, title=0.3, education=0.14, location=0.14, authorization=0.1
        ),
    )
    assert skill_heavy.score < skill_light.score


def test_weights_are_normalised_so_a_partial_override_keeps_the_scale():
    weights = MatchWeights(
        skills=1.0, experience=1.0, title=1.0, education=1.0, location=1.0, authorization=1.0
    ).normalized()
    assert sum(weights.values()) == pytest.approx(1.0)
    assert all(value == pytest.approx(1 / 6) for value in weights.values())


def test_zero_weights_are_rejected():
    with pytest.raises(ValueError, match="positive"):
        MatchWeights(
            skills=0, experience=0, title=0, education=0, location=0, authorization=0
        ).normalized()


def test_seniority_mismatch_pulls_the_score_down(service):
    director = job(title="Senior Director of Engineering")
    result = service.score(profile(), director)
    aligned = service.score(profile(), job())
    assert result.seniority_score < aligned.seniority_score
    assert result.score < aligned.score


def test_explanation_reports_the_score_and_the_decision(service):
    result = service.score(profile(), job())
    assert str(result.score) in result.explanation
    assert result.weights
