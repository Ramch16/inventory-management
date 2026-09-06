"""The Resume Truth Layer is the platform's hallucination guard."""

from __future__ import annotations

import pytest
from jobapply_resume.models import (
    ContactInfo,
    SourceRecord,
    TailoredBullet,
    TailoredExperience,
    TailoredResume,
)
from jobapply_resume.sources import build_source_records
from jobapply_resume.truth import ResumeTruthLayer, build_source_index


@pytest.fixture
def layer() -> ResumeTruthLayer:
    records = [
        SourceRecord(
            id="experience_123",
            kind="experience",
            text=(
                "Senior Data Engineer at Northwind Analytics. Built automated data "
                "pipelines using Python and SQL that cut nightly batch time from six "
                "hours to ninety minutes."
            ),
            entities=["Northwind Analytics", "Senior Data Engineer", "Python", "SQL"],
        ),
        SourceRecord(id="skill_55", kind="skill", text="Python", numbers={"python": 5}),
        SourceRecord(id="skill_56", kind="skill", text="AWS", numbers={"aws": 3}),
        SourceRecord(
            id="education_9", kind="education", text="B.S. Computer Science, University of Texas"
        ),
    ]
    return ResumeTruthLayer(build_source_index(records))


def test_a_grounded_rewrite_is_allowed(layer):
    verdict = layer.verify_statement(
        "Built automated data pipelines using Python and SQL", ["experience_123", "skill_55"]
    )
    assert verdict.allowed
    assert verdict.confidence > 0.8
    assert verdict.matched_source_ids == ["experience_123", "skill_55"]


def test_an_unlisted_technology_is_rejected(layer):
    verdict = layer.verify_statement(
        "Built automated data pipelines using Kubernetes and Kafka", ["experience_123"]
    )
    assert not verdict.allowed
    assert any("kubernetes" in reason for reason in verdict.reasons)


def test_an_inflated_number_is_rejected(layer):
    """The spec's example: the model says eight years, the profile says three."""
    verdict = layer.verify_answer("I have 8 years of AWS experience", ["skill_56"])
    assert not verdict.allowed
    assert any("but the profile records 3" in reason for reason in verdict.reasons)


def test_an_accurate_number_is_allowed(layer):
    assert layer.verify_answer("I have 3 years of AWS experience", ["skill_56"]).allowed


def test_an_unrecorded_number_is_rejected(layer):
    verdict = layer.verify_answer("I have 7 years of experience", ["skill_55"])
    assert not verdict.allowed
    assert any("not recorded" in reason for reason in verdict.reasons)


def test_a_nonexistent_source_is_rejected(layer):
    verdict = layer.verify_statement("Built pipelines using Python", ["experience_999"])
    assert not verdict.allowed
    assert any("do not exist" in reason for reason in verdict.reasons)


def test_an_uncited_statement_is_rejected(layer):
    assert not layer.verify_statement("Built pipelines using Python", []).allowed


@pytest.mark.parametrize(
    "text",
    [
        "Held an active Top Secret clearance",
        "Authorized to work in the United States without sponsorship",
        "US citizen with a valid H-1B transfer",
    ],
)
def test_legally_significant_claims_are_never_generated(layer, text):
    verdict = layer.verify_statement(text, ["experience_123"])
    assert not verdict.allowed


def test_ungrounded_prose_is_rejected_even_with_a_real_source(layer):
    verdict = layer.verify_statement(
        "Recognised across the industry as a visionary leader", ["experience_123"]
    )
    assert not verdict.allowed
    assert any("traceable" in reason for reason in verdict.reasons)


def test_document_verification_reports_every_problem(layer):
    document = TailoredResume(
        contact=ContactInfo(full_name="Jordan Rivera"),
        summary="Built automated data pipelines using Python and SQL",
        summary_source_ids=["experience_123"],
        skills=["Python", "Kubernetes"],
        experience=[
            TailoredExperience(
                experience_id="experience_123",
                company="Northwind Analytics",
                title="Senior Data Engineer",
                bullets=[
                    TailoredBullet(
                        text="Built automated data pipelines using Python and SQL",
                        source_ids=["experience_123"],
                        confidence=0.9,
                    ),
                    TailoredBullet(
                        text="Led the migration to Kubernetes",
                        source_ids=["experience_123"],
                        confidence=0.9,
                    ),
                ],
            )
        ],
        certifications=["Certified Kubernetes Administrator"],
    )
    report = layer.verify_document(document)
    assert not report.allowed
    assert "Kubernetes" in report.rejected_statements
    assert "Certified Kubernetes Administrator" in report.rejected_statements
    assert any("Led the migration" in statement for statement in report.rejected_statements)


def test_a_fully_grounded_document_passes(layer):
    document = TailoredResume(
        contact=ContactInfo(full_name="Jordan Rivera"),
        summary="Built automated data pipelines using Python and SQL",
        summary_source_ids=["experience_123"],
        skills=["Python", "SQL"],
        experience=[
            TailoredExperience(
                experience_id="experience_123",
                company="Northwind Analytics",
                title="Senior Data Engineer",
                bullets=[
                    TailoredBullet(
                        text="Built automated data pipelines using Python and SQL",
                        source_ids=["experience_123"],
                        confidence=0.9,
                    )
                ],
            )
        ],
    )
    assert layer.verify_document(document).allowed


def test_source_records_are_built_from_profile_data():
    from datetime import date

    records = build_source_records(
        profile={"first_name": "Jordan", "current_title": "Data Engineer", "years_experience": 6},
        experiences=[
            {
                "id": "abc",
                "company": "Northwind Analytics",
                "title": "Senior Data Engineer",
                "start_date": date(2021, 3, 1),
                "end_date": None,
                "accomplishments": ["Built pipelines with Python"],
                "technologies": ["Python"],
                "skills": [],
            }
        ],
        skills=[{"id": "s1", "name": "Python", "years_experience": 5}],
    )
    index = build_source_index(records)
    assert "experience_abc" in index.records
    assert index.numbers["python"] >= 3
    assert index.years_for(None) == 6.0
