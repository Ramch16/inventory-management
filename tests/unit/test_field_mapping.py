"""Deterministic field mapping, and the guardrails on the AI fallback."""

from __future__ import annotations

import pytest
from jobapply_browser.mapping import TARGETS, accept_ai_mapping, map_field, map_fields, unmapped
from jobapply_browser.models import FieldOption, NormalizedField
from jobapply_shared.enums import FieldType, QuestionCategory


def make(label: str, **overrides) -> NormalizedField:
    return NormalizedField(field_id=overrides.pop("field_id", "f1"), label=label, **overrides)


@pytest.mark.parametrize(
    ("label", "target"),
    [
        ("First Name", "profile.first_name"),
        ("Last name", "profile.last_name"),
        ("Full Name", "profile.full_name"),
        ("Email Address", "profile.email"),
        ("Phone Number", "profile.phone"),
        ("LinkedIn Profile", "profile.linkedin_url"),
        ("GitHub", "profile.github_url"),
        ("Personal website", "profile.portfolio_url"),
        ("City", "profile.city"),
        ("State/Province", "profile.state"),
        ("Zip / Postal Code", "profile.postal_code"),
        ("Current Job Title", "profile.current_title"),
        ("Resume/CV", "generated_resume"),
        ("Cover Letter", "generated_cover_letter"),
        ("When can you start?", "answer.start_date"),
        ("Why are you interested in this position?", "answer.why_interested"),
    ],
)
def test_ordinary_fields_map_deterministically(label, target):
    mapping = map_field(make(label))
    assert mapping.target == target
    assert mapping.strategy == "deterministic"
    assert mapping.confidence >= 0.85
    assert mapping.is_sensitive is False


@pytest.mark.parametrize(
    ("label", "target", "category"),
    [
        (
            "Are you legally authorized to work in the United States?",
            "profile.work_authorized",
            QuestionCategory.WORK_AUTHORIZATION,
        ),
        (
            "Will you now or in the future require visa sponsorship?",
            "profile.requires_sponsorship",
            QuestionCategory.SPONSORSHIP,
        ),
        ("Desired salary", "profile.salary_expectation", QuestionCategory.COMPENSATION),
        ("Do you have a disability?", "sensitive.disability", QuestionCategory.DISABILITY),
        ("Are you a protected veteran?", "sensitive.veteran", QuestionCategory.VETERAN),
        ("Race / Ethnicity", "sensitive.demographic", QuestionCategory.DEMOGRAPHIC),
        (
            "Have you ever been convicted of a felony?",
            "sensitive.criminal_history",
            QuestionCategory.CRIMINAL_HISTORY,
        ),
        (
            "I certify that the information provided is true and complete",
            "sensitive.legal_attestation",
            QuestionCategory.LEGAL_ATTESTATION,
        ),
    ],
)
def test_sensitive_fields_are_flagged(label, target, category):
    mapping = map_field(make(label))
    assert mapping.target == target
    assert mapping.category == category
    assert mapping.is_sensitive is True


@pytest.mark.parametrize(
    ("label", "target"),
    [
        ("How many years of Python experience do you have?", "answer.skill_years"),
        ("Years of experience with dbt", "answer.skill_years"),
        ("Years of total experience", "profile.years_experience"),
        ("Years of professional experience", "profile.years_experience"),
    ],
)
def test_career_total_and_per_skill_experience_are_distinguished(label, target):
    assert map_field(make(label)).target == target


def test_excludes_prevent_a_generic_rule_from_stealing_a_field():
    assert map_field(make("Reference first name")).target != "profile.first_name"
    assert map_field(make("Company name")).target != "profile.full_name"


def test_an_unrecognised_field_is_left_unmapped_rather_than_guessed():
    mapping = map_field(make("What is your favourite colour?"))
    assert mapping.target is None
    assert mapping.strategy == "unmapped"
    assert mapping.confidence == 0.0


def test_mapping_reads_every_available_signal():
    field = NormalizedField(
        field_id="f9",
        label=None,
        name="job_application[answers_attributes][0][text_value]",
        context_text="Are you authorized to work in the United States?",
    )
    assert map_field(field).target == "profile.work_authorized"


def test_unmapped_helper_selects_the_leftovers():
    fields = [make("First Name", field_id="a"), make("Favourite colour", field_id="b")]
    mappings = map_fields(fields)
    assert [mapping.field_id for mapping in unmapped(mappings)] == ["b"]


def test_ai_mapping_is_capped_below_deterministic_confidence():
    field = make("Tell us about a project you are proud of")
    mapping = accept_ai_mapping(field, "answer.why_interested", 0.99)
    assert mapping.strategy == "ai"
    assert mapping.confidence <= 0.90


def test_ai_cannot_invent_a_mapping_target():
    mapping = accept_ai_mapping(make("Anything"), "profile.social_security_number", 0.99)
    assert mapping.target is None
    assert mapping.strategy == "ai_rejected"


def test_ai_cannot_declare_an_unclear_field_sensitive():
    """A model must not decide that a vague question is really about sponsorship."""
    mapping = accept_ai_mapping(
        make("Anything else we should know?"), "profile.requires_sponsorship", 0.99
    )
    assert mapping.target is None
    assert mapping.strategy == "ai_rejected"


def test_ai_may_confirm_a_sensitive_mapping_a_rule_already_found():
    field = make("Will you require sponsorship?")
    mapping = accept_ai_mapping(field, "profile.requires_sponsorship", 0.99)
    assert mapping.target == "profile.requires_sponsorship"


def test_every_sensitive_target_is_declared_sensitive():
    for key, target in TARGETS.items():
        if key.startswith("sensitive.") or key in {
            "profile.work_authorized",
            "profile.requires_sponsorship",
            "profile.salary_expectation",
        }:
            assert target.sensitive, f"{key} must be marked sensitive"


def test_select_options_are_carried_through():
    field = NormalizedField(
        field_id="f1",
        label="Are you authorized to work in the United States?",
        type=FieldType.SELECT,
        options=[FieldOption(label="Yes", value="1"), FieldOption(label="No", value="0")],
    )
    assert map_field(field).target == "profile.work_authorized"
    assert len(field.options) == 2
