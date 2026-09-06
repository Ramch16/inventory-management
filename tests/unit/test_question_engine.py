"""The question engine: explicit data first, a model last, and never for the
questions that carry legal weight."""

from __future__ import annotations

import asyncio

import pytest
from jobapply_browser.mapping import map_field
from jobapply_browser.models import FieldOption, NormalizedField
from jobapply_browser.questions import AnswerContext, ApplicationQuestionService
from jobapply_shared.enums import AnswerSource, FieldType


@pytest.fixture
def context() -> AnswerContext:
    return AnswerContext(
        profile={
            "first_name": "Jordan",
            "last_name": "Rivera",
            "email": "jordan@example.com",
            "phone": "+1 415 555 0142",
            "city": "San Francisco",
            "state": "CA",
            "country": "United States",
            "linkedin_url": "https://linkedin.com/in/jordanrivera",
            "current_title": "Senior Data Engineer",
            "years_experience": 6,
            "salary_min": 160000,
            "requires_sponsorship_now": False,
            "requires_sponsorship_future": False,
        },
        skill_years={"python": 5, "airflow": 3},
        education=[{"institution": "University of Texas at Austin", "degree": "B.S."}],
        experiences=[
            {"company": "Northwind Analytics", "title": "Senior Data Engineer", "is_current": True}
        ],
        job={"title": "Data Engineer", "company_name": "Cobalt Software"},
    )


@pytest.fixture
def service() -> ApplicationQuestionService:
    # No provider: this is the deterministic layer under test.
    return ApplicationQuestionService()


def resolve(service, field, context):
    return asyncio.run(service.answer(field, map_field(field), context))


def make(label: str, **kwargs) -> NormalizedField:
    kwargs.setdefault("field_id", "f1")
    return NormalizedField(label=label, **kwargs)


def test_profile_fields_are_filled_without_review(service, context):
    for label, expected in [
        ("First Name", "Jordan"),
        ("Last Name", "Rivera"),
        ("Email Address", "jordan@example.com"),
        ("Phone Number", "+1 415 555 0142"),
        ("City", "San Francisco"),
        ("Current Job Title", "Senior Data Engineer"),
    ]:
        answer = resolve(service, make(label), context)
        assert answer.answer == expected
        assert answer.source == AnswerSource.PROFILE
        assert answer.requires_review is False
        assert answer.can_autofill


def test_a_missing_profile_field_pauses_rather_than_guessing(service, context):
    context.profile["phone"] = None
    answer = resolve(service, make("Phone Number"), context)
    assert answer.answer is None
    assert answer.requires_review is True


def test_work_authorization_comes_from_the_declared_profile_field(service, context):
    field = make(
        "Are you legally authorized to work in the United States?",
        type=FieldType.SELECT,
        options=[FieldOption(label="Yes", value="Yes"), FieldOption(label="No", value="No")],
    )
    answer = resolve(service, field, context)
    assert answer.answer == "Yes"
    assert answer.source == AnswerSource.PROFILE
    assert answer.is_sensitive is True
    assert answer.requires_review is False


def test_work_authorization_pauses_when_it_was_never_declared(service, context):
    context.profile["requires_sponsorship_now"] = None
    field = make("Are you legally authorized to work in the United States?")
    answer = resolve(service, field, context)
    assert answer.answer is None
    assert answer.requires_review is True
    assert "work authorization" in (answer.reason or "").lower()


def test_sponsorship_now_and_future_are_answered_separately(service, context):
    context.profile["requires_sponsorship_now"] = False
    context.profile["requires_sponsorship_future"] = True

    now = resolve(service, make("Do you require sponsorship now?"), context)
    future = resolve(service, make("Will you require sponsorship in the future?"), context)
    assert now.answer == "Yes", "either now or in the future counts as requiring sponsorship"
    assert future.answer == "Yes"

    context.profile["requires_sponsorship_future"] = False
    assert resolve(service, make("Do you require sponsorship now?"), context).answer == "No"


@pytest.mark.parametrize(
    "label",
    [
        "Do you have a disability?",
        "Are you a protected veteran?",
        "Race / Ethnicity",
        "Have you ever been convicted of a felony?",
    ],
)
def test_protected_characteristics_always_require_the_user(service, context, label):
    answer = resolve(service, make(label), context)
    assert answer.requires_review is True
    assert answer.is_sensitive is True
    assert answer.source != AnswerSource.AI_GENERATED


def test_a_decline_option_is_offered_but_not_submitted_unreviewed(service, context):
    field = make(
        "Are you a protected veteran?",
        type=FieldType.SELECT,
        options=[
            FieldOption(label="Yes", value="1"),
            FieldOption(label="No", value="2"),
            FieldOption(label="I prefer not to answer", value="3"),
        ],
    )
    answer = resolve(service, field, context)
    assert answer.answer == "3"
    assert answer.requires_review is True


def test_legal_attestations_are_never_auto_answered(service, context):
    answer = resolve(
        service, make("I certify that the information provided is true and complete"), context
    )
    assert answer.answer is None
    assert answer.requires_review is True
    assert "yourself" in (answer.reason or "")


def test_salary_expectation_uses_the_profile_minimum(service, context):
    answer = resolve(service, make("Desired salary"), context)
    assert answer.answer == "160000"
    assert answer.is_sensitive is True
    assert answer.requires_review is True, "compensation is reviewed before it is sent"


def test_salary_pauses_when_the_profile_has_no_minimum(service, context):
    context.profile["salary_min"] = None
    answer = resolve(service, make("Desired salary"), context)
    assert answer.answer is None


def test_years_of_a_specific_skill_come_from_the_profile(service, context):
    answer = resolve(service, make("How many years of Python experience do you have?"), context)
    assert answer.answer == "5"
    assert answer.source == AnswerSource.PROFILE
    assert answer.requires_review is False


def test_an_unrecorded_skill_pauses_rather_than_inventing_a_number(service, context):
    answer = resolve(service, make("How many years of Kubernetes experience do you have?"), context)
    assert answer.answer is None
    assert answer.requires_review is True
    assert "Kubernetes" in (answer.reason or "")


def test_total_experience_comes_from_the_profile(service, context):
    assert resolve(service, make("Years of total experience"), context).answer == "6"


def test_select_options_are_matched_not_typed(service, context):
    field = make(
        "State",
        type=FieldType.SELECT,
        options=[
            FieldOption(label="California", value="CA"),
            FieldOption(label="Texas", value="TX"),
        ],
    )
    context.profile["state"] = "California"
    answer = resolve(service, field, context)
    assert answer.answer == "CA"


def test_a_value_with_no_matching_option_pauses(service, context):
    field = make(
        "Country",
        type=FieldType.SELECT,
        options=[FieldOption(label="Canada", value="CA"), FieldOption(label="Mexico", value="MX")],
    )
    answer = resolve(service, field, context)
    assert answer.answer is None
    assert answer.requires_review is True


def test_a_previously_approved_answer_is_reused(service, context):
    context.saved_answers["why are you interested in this position?"] = (
        "Because of the data platform work."
    )
    answer = resolve(service, make("Why are you interested in this position?"), context)
    assert answer.answer == "Because of the data platform work."
    assert answer.source == AnswerSource.USER_PROVIDED
    assert answer.requires_review is False


def test_without_a_provider_an_open_question_pauses(service, context):
    answer = resolve(service, make("Why are you interested in this position?"), context)
    assert answer.answer is None
    assert answer.requires_review is True


def test_a_model_never_answers_a_sensitive_question():
    from jobapply_ai.providers.mock import MockAIProvider

    service = ApplicationQuestionService(provider=MockAIProvider())
    field = make("Are you a protected veteran?")
    answer = asyncio.run(service.resolve_with_ai(field, map_field(field), AnswerContext()))
    assert answer.answer is None
    assert "never answered by a model" in (answer.reason or "")


def test_a_generated_answer_never_reaches_the_autofill_band():
    """Even a confident generation is reviewed: only explicit data auto-fills."""
    from jobapply_ai.models import TokenUsage
    from jobapply_ai.provider import BaseAIProvider

    class ConfidentProvider(BaseAIProvider):
        name = "confident"
        default_model = "test"

        async def _generate(self, *, system, user, max_output_tokens, temperature, model):
            return (
                '{"answer": "I admire the data platform work.", "confidence": 1.0, '
                '"source": "ai_generated", "source_ids": ["profile"], "requires_review": false}',
                TokenUsage(),
            )

    service = ApplicationQuestionService(provider=ConfidentProvider())
    field = make("Why are you interested in this position?")
    answer = asyncio.run(service.answer(field, map_field(field), AnswerContext()))
    assert answer.answer == "I admire the data platform work."
    assert answer.confidence <= 0.94
    assert answer.requires_review is False or answer.confidence < 0.95


def test_a_generated_answer_that_fails_the_truth_layer_is_dropped():
    from jobapply_ai.models import TokenUsage
    from jobapply_ai.provider import BaseAIProvider
    from jobapply_resume.models import SourceRecord
    from jobapply_resume.truth import ResumeTruthLayer, build_source_index

    class InflatingProvider(BaseAIProvider):
        name = "inflating"
        default_model = "test"

        async def _generate(self, *, system, user, max_output_tokens, temperature, model):
            return (
                '{"answer": "I have 9 years of Python experience.", "confidence": 0.99, '
                '"source": "ai_generated", "source_ids": ["skill_1"], "requires_review": false}',
                TokenUsage(),
            )

    layer = ResumeTruthLayer(
        build_source_index(
            [SourceRecord(id="skill_1", kind="skill", text="Python", numbers={"python": 5})]
        )
    )
    service = ApplicationQuestionService(provider=InflatingProvider(), truth_layer=layer)
    field = make("Tell us about your Python background")
    answer = asyncio.run(service.answer(field, map_field(field), AnswerContext()))
    assert answer.answer is None
    assert "could not be traced" in (answer.reason or "")


def test_answer_all_returns_one_result_per_field(service, context):
    fields = [
        make("First Name", field_id="a"),
        NormalizedField(field_id="b", label="Last Name"),
        NormalizedField(field_id="c", label="Favourite colour"),
    ]
    mappings = [map_field(field) for field in fields]
    answers = asyncio.run(service.answer_all(fields, mappings, context))
    assert [answer.field_id for answer in answers] == ["a", "b", "c"]
    assert answers[2].requires_review is True
