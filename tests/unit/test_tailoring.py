"""Tailoring selects and rewords approved content, and never adds to it."""

from __future__ import annotations

import asyncio
from datetime import date

import pytest
from jobapply_ai.models import TokenUsage
from jobapply_ai.provider import BaseAIProvider
from jobapply_resume.models import ContactInfo, SourceRecord
from jobapply_resume.quality import score_resume
from jobapply_resume.tailoring import ResumeTailoringService, TailoringInputs

JOB = {
    "title": "Senior Data Engineer",
    "company_name": "Cobalt Software",
    "skills": ["python", "sql", "airflow", "dbt"],
    "requirements": ["5+ years building data pipelines", "Strong Python and SQL"],
    "preferred_qualifications": ["Snowflake"],
}


@pytest.fixture
def inputs() -> TailoringInputs:
    experience = {
        "id": "1",
        "company": "Northwind Analytics",
        "title": "Senior Data Engineer",
        "location": "San Francisco, CA",
        "start_date": date(2021, 3, 1),
        "end_date": None,
        "is_current": True,
        "accomplishments": [
            "Built automated data pipelines using Python and SQL that cut nightly batch time.",
            "Organised the team offsite.",
            "Migrated 40 legacy ETL jobs to Airflow, reducing on-call pages by 60%.",
            "Partnered with analysts to define a dbt semantic layer used by 12 dashboards.",
            "Wrote the on-call runbook.",
            "Reduced pipeline compute spend by 22% through partition tuning.",
        ],
        "technologies": ["Python", "SQL", "Airflow"],
        "skills": [],
    }
    sources = [
        SourceRecord(
            id="experience_1",
            kind="experience",
            text=" ".join(
                [
                    experience["title"],
                    experience["company"],
                    *experience["accomplishments"],
                    "Python SQL Airflow",
                ]
            ),
            entities=["Northwind Analytics", "Python", "SQL", "Airflow"],
        ),
        SourceRecord(id="skill_1", kind="skill", text="Python", numbers={"python": 5}),
        SourceRecord(id="profile", kind="profile", text="Jordan Rivera Senior Data Engineer"),
    ]
    return TailoringInputs(
        contact=ContactInfo(full_name="Jordan Rivera", email="jordan@example.com"),
        sources=sources,
        experiences=[experience],
        education=[{"id": "e1", "institution": "University of Texas", "degree": "B.S."}],
        skills=["Python", "SQL", "Airflow", "Excel"],
        certifications=["AWS Certified Solutions Architect"],
        summary="Data engineer focused on reliable pipelines.",
    )


def tailor(service, inputs, **kwargs):
    return asyncio.run(service.tailor(inputs, JOB, **kwargs))


def test_without_a_provider_the_users_own_bullets_are_used(inputs):
    outcome = tailor(ResumeTailoringService(), inputs)
    assert outcome.used_ai is False
    bullets = [bullet.text for bullet in outcome.document.experience[0].bullets]
    assert all(text in inputs.experiences[0]["accomplishments"] for text in bullets)
    assert all(bullet.source_ids for bullet in outcome.document.experience[0].bullets)


def test_relevant_bullets_are_prioritised(inputs):
    outcome = tailor(ResumeTailoringService(), inputs, max_pages=1)
    bullets = [bullet.text for bullet in outcome.document.experience[0].bullets]
    assert "Organised the team offsite." not in bullets[:2]


def test_page_budget_limits_the_number_of_bullets(inputs):
    one_page = tailor(ResumeTailoringService(), inputs, max_pages=1)
    three_page = tailor(ResumeTailoringService(), inputs, max_pages=3)
    assert len(one_page.document.experience[0].bullets) < len(
        three_page.document.experience[0].bullets
    )


def test_provenance_is_recorded_for_every_statement(inputs):
    outcome = tailor(ResumeTailoringService(), inputs)
    assert outcome.document.provenance
    for record in outcome.document.provenance:
        assert record.generated_text
        assert record.source_ids


class _FabricatingProvider(BaseAIProvider):
    """Proposes one grounded bullet and one invented one."""

    name = "fabricating"
    default_model = "test"

    async def _generate(self, *, system, user, max_output_tokens, temperature, model):
        return (
            """{
              "summary": "Data engineer focused on reliable pipelines.",
              "summary_source_ids": ["profile"],
              "skills": ["Python", "SQL", "Kubernetes"],
              "experience": [
                {"experience_id": "experience_1", "bullets": [
                  {"text": "Migrated 40 legacy ETL jobs to Airflow, reducing on-call pages by 60%.",
                   "source_ids": ["experience_1"], "confidence": 0.95},
                  {"text": "Led the company-wide Kubernetes migration.",
                   "source_ids": ["experience_1"], "confidence": 0.95}
                ]}
              ]
            }""",
            TokenUsage(),
        )


def test_an_invented_bullet_is_rejected_and_reported(inputs):
    outcome = tailor(ResumeTailoringService(_FabricatingProvider()), inputs)
    assert outcome.used_ai is True

    bullets = [bullet.text for bullet in outcome.document.experience[0].bullets]
    assert "Led the company-wide Kubernetes migration." not in bullets
    assert any("Kubernetes" in item["text"] for item in outcome.rejected)


def test_a_skill_the_user_never_listed_is_dropped(inputs):
    outcome = tailor(ResumeTailoringService(_FabricatingProvider()), inputs)
    assert "Kubernetes" not in outcome.document.skills
    assert any(item["text"] == "Kubernetes" for item in outcome.rejected)


def test_a_provider_failure_falls_back_to_the_users_own_content(inputs):
    class BrokenProvider(BaseAIProvider):
        name = "broken"
        default_model = "test"

        async def _generate(self, **kwargs):
            raise RuntimeError("provider unavailable")

    outcome = tailor(ResumeTailoringService(BrokenProvider()), inputs)
    assert outcome.used_ai is False
    assert outcome.document.experience[0].bullets, "the resume still has content"


def test_quality_scoring_rewards_a_relevant_resume(inputs):
    outcome = tailor(ResumeTailoringService(), inputs)
    score = score_resume(outcome.document, JOB)
    assert 0 <= score.overall <= 100
    assert score.ats_readability >= 80
    assert score.keyword_coverage >= 50


def test_quality_scoring_flags_a_missing_contact_email(inputs):
    outcome = tailor(ResumeTailoringService(), inputs)
    outcome.document.contact.email = None
    score = score_resume(outcome.document, JOB)
    assert score.ats_readability < 100
    assert any("e-mail" in note for note in score.notes)


def test_factual_consistency_drops_when_the_truth_layer_rejected_something(inputs):
    from jobapply_resume.models import TruthReport

    outcome = tailor(ResumeTailoringService(), inputs)
    clean = score_resume(outcome.document, JOB, TruthReport(allowed=True))
    dirty = score_resume(
        outcome.document,
        JOB,
        TruthReport(allowed=False, rejected_statements=["Led the Kubernetes migration"]),
    )
    assert dirty.factual_consistency < clean.factual_consistency
    assert dirty.overall < clean.overall
