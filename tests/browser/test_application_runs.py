"""End-to-end automation against the local mock ATS sites.

Every stop condition the platform promises is exercised here with a real browser:
CAPTCHA, OTP, a sign-in wall, an unmappable field, and a submission that produces no
confirmation.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from jobapply_browser.engine import ApplicationRunner
from jobapply_browser.models import RunContext, SignInCredential
from jobapply_browser.questions import AnswerContext, ApplicationQuestionService
from jobapply_shared.enums import (
    ApplicationStatus,
    AtsKind,
    AutomationRunState,
    InterventionType,
)

pytestmark = pytest.mark.browser

RESUME = Path(__file__).parent.parent / "fixtures" / "resumes" / "sample_resume.txt"


def answer_context() -> AnswerContext:
    return AnswerContext(
        profile={
            "first_name": "Jordan",
            "last_name": "Rivera",
            "email": "jordan.rivera@example.com",
            "phone": "+14155550142",
            "city": "San Francisco",
            "state": "CA",
            "country": "United States",
            "linkedin_url": "https://linkedin.com/in/jordanrivera",
            "current_title": "Senior Data Engineer",
            "years_experience": 6,
            "requires_sponsorship_now": False,
            "requires_sponsorship_future": False,
        },
        skill_years={"python": 5},
        experiences=[
            {"company": "Northwind Analytics", "title": "Senior Data Engineer", "is_current": True}
        ],
        job={"title": "Senior Data Engineer", "company_name": "Northwind Analytics"},
        saved_answers={"why are you interested in this role?": "The data platform work."},
    )


def context_for(
    url: str,
    *,
    ats: AtsKind,
    auto_submit: bool = True,
    credential: SignInCredential | None = None,
    **metadata,
) -> RunContext:
    return RunContext(
        application_id="app-1",
        user_id="user-1",
        job_id="job-1",
        apply_url=url,
        ats=ats,
        auto_submit=auto_submit,
        resume_path=str(RESUME),
        credential=credential,
        metadata={"company": "Northwind Analytics", "title": "Senior Data Engineer", **metadata},
    )


async def _run(manager, url, ats, *, auto_submit=True, credential=None, **metadata):
    runner = ApplicationRunner(question_service=ApplicationQuestionService())
    async with manager.session() as page:
        return await runner.run(
            page,
            context_for(url, ats=ats, auto_submit=auto_submit, credential=credential, **metadata),
            answer_context(),
        )
    # the context is always closed by the session manager


def test_greenhouse_application_is_filled_and_submitted(browser_manager, mock_ats, run_async):
    report = run_async(_run(browser_manager, mock_ats.url("/greenhouse"), AtsKind.GREENHOUSE))

    assert report.detection is not None
    assert report.detection.ats == AtsKind.GREENHOUSE
    assert len(report.detection.signals) >= 2, "a platform needs two agreeing signals"

    assert report.form is not None
    field_ids = {field.field_id for field in report.form.fields}
    assert {"first_name", "last_name", "email", "work_auth", "sponsorship"} <= field_ids

    assert report.intervention is None, report.intervention
    assert report.status == ApplicationStatus.CONFIRMATION_CAPTURED
    assert report.state == AutomationRunState.COMPLETED
    assert report.confirmation is not None
    assert report.confirmation.confirmed
    assert report.confirmation.confirmation_id == "NW-48213-A"

    submission = mock_ats.submissions[-1]
    assert "job_application[first_name]" in submission.fields


def test_sensitive_answers_come_from_the_profile(browser_manager, mock_ats, run_async):
    report = run_async(_run(browser_manager, mock_ats.url("/greenhouse"), AtsKind.GREENHOUSE))
    answers = {answer.field_id: answer for answer in report.answers}

    assert answers["work_auth"].answer == "Yes"
    assert answers["work_auth"].source.value == "profile"
    assert answers["sponsorship"].answer == "No"
    assert answers["sponsorship"].is_sensitive is True


def test_the_resume_is_uploaded(browser_manager, mock_ats, run_async):
    report = run_async(_run(browser_manager, mock_ats.url("/greenhouse"), AtsKind.GREENHOUSE))
    uploads = [outcome for outcome in report.fills if outcome.field_id == "resume"]
    assert uploads and uploads[0].filled


def test_lever_application_runs_with_its_own_adapter(browser_manager, mock_ats, run_async):
    report = run_async(
        _run(
            browser_manager,
            mock_ats.url("/lever"),
            AtsKind.LEVER,
            company="Cobalt Software",
            title="Analytics Engineer",
        )
    )
    assert report.detection is not None and report.detection.ats == AtsKind.LEVER
    assert report.status in {
        ApplicationStatus.CONFIRMATION_CAPTURED,
        ApplicationStatus.SUBMISSION_UNCONFIRMED,
    }


def test_a_captcha_pauses_the_run_and_never_submits(browser_manager, mock_ats, run_async):
    before = len(mock_ats.submissions)
    report = run_async(_run(browser_manager, mock_ats.url("/captcha"), AtsKind.GREENHOUSE))

    assert report.state == AutomationRunState.CAPTCHA_REQUIRED
    assert report.status == ApplicationStatus.WAITING_FOR_VERIFICATION
    assert report.intervention is not None
    assert report.intervention.type == InterventionType.CAPTCHA
    assert "does not solve CAPTCHAs" in report.intervention.reason
    assert len(mock_ats.submissions) == before, "nothing may be submitted behind a CAPTCHA"


def test_an_otp_prompt_pauses_for_the_user(browser_manager, mock_ats, run_async):
    report = run_async(_run(browser_manager, mock_ats.url("/otp"), AtsKind.LEVER))
    assert report.state == AutomationRunState.OTP_REQUIRED
    assert report.intervention is not None
    assert report.intervention.type == InterventionType.OTP
    assert "never stored" in report.intervention.reason


def test_a_sign_in_wall_stops_rather_than_creating_an_account(browser_manager, mock_ats, run_async):
    report = run_async(_run(browser_manager, mock_ats.url("/workday"), AtsKind.WORKDAY))
    assert report.intervention is not None
    assert report.intervention.type == InterventionType.AUTHENTICATION_REQUIRED
    assert report.status == ApplicationStatus.WAITING_FOR_VERIFICATION


def test_the_generic_adapter_handles_a_plain_employer_form(browser_manager, mock_ats, run_async):
    report = run_async(
        _run(
            browser_manager,
            mock_ats.url("/generic"),
            AtsKind.GENERIC,
            company="Helios",
            title="Apply",
        )
    )
    assert report.detection is not None and report.detection.ats == AtsKind.GENERIC
    assert report.status in {
        ApplicationStatus.CONFIRMATION_CAPTURED,
        ApplicationStatus.SUBMISSION_UNCONFIRMED,
    }


def test_an_unmappable_field_on_an_unknown_site_pauses(browser_manager, mock_ats, run_async):
    before = len(mock_ats.submissions)
    report = run_async(
        _run(
            browser_manager,
            mock_ats.url("/generic-ambiguous"),
            AtsKind.GENERIC,
            company="Helios",
            title="Apply",
        )
    )
    assert report.intervention is not None
    assert report.status == ApplicationStatus.WAITING_FOR_VERIFICATION
    assert len(mock_ats.submissions) == before


def test_review_mode_stops_before_submitting(browser_manager, mock_ats, run_async):
    before = len(mock_ats.submissions)
    report = run_async(
        _run(browser_manager, mock_ats.url("/greenhouse"), AtsKind.GREENHOUSE, auto_submit=False)
    )
    assert report.status == ApplicationStatus.READY_TO_SUBMIT
    assert report.state == AutomationRunState.WAITING_FOR_USER
    assert len(mock_ats.submissions) == before


def test_a_submission_with_no_confirmation_is_never_reported_as_applied(
    browser_manager, mock_ats, run_async
):
    mock_ats.suppress_confirmation = True
    try:
        report = run_async(_run(browser_manager, mock_ats.url("/greenhouse"), AtsKind.GREENHOUSE))
    finally:
        mock_ats.suppress_confirmation = False

    assert report.status == ApplicationStatus.SUBMISSION_UNCONFIRMED
    assert report.confirmation is not None and report.confirmation.confirmed is False


def test_a_wrong_adapter_is_corrected_by_page_evidence(browser_manager, mock_ats, run_async):
    """The URL said Ashby; the page proves Greenhouse."""
    report = run_async(_run(browser_manager, mock_ats.url("/greenhouse"), AtsKind.ASHBY))
    assert report.detection is not None
    assert report.detection.ats == AtsKind.GREENHOUSE


def test_every_run_records_a_step_timeline(browser_manager, mock_ats, run_async):
    report = run_async(_run(browser_manager, mock_ats.url("/greenhouse"), AtsKind.GREENHOUSE))
    names = [step.name for step in report.steps]
    assert names[:4] == ["navigate", "detect", "inspect_form", "map_fields"]
    assert "submit" in names


CREDENTIAL = SignInCredential(
    credential_id="cred-1", username="candidate@example.com", secret="mock-password"
)


def test_a_stored_credential_signs_in_and_the_run_continues(browser_manager, mock_ats, run_async):
    """Signing in to the user's own account is not a bypass — it is the user acting."""
    report = run_async(
        _run(
            browser_manager,
            mock_ats.url("/login"),
            AtsKind.GENERIC,
            credential=CREDENTIAL,
            company="Helios",
            title="Apply",
        )
    )

    assert mock_ats.sign_in_attempts == ["candidate@example.com"]
    steps = {step.name: step.status for step in report.steps}
    assert steps.get("sign_in") == "ok"
    assert report.intervention is None
    assert report.form is not None and report.form.fields, "the form behind the wall was reached"


def test_a_wrong_credential_pauses_instead_of_trying_again(browser_manager, mock_ats, run_async):
    """One attempt only: repeated guesses would lock the user out of their own account."""
    wrong = SignInCredential(
        credential_id="cred-1", username="candidate@example.com", secret="not-the-password"
    )
    report = run_async(
        _run(browser_manager, mock_ats.url("/login"), AtsKind.GENERIC, credential=wrong)
    )

    assert mock_ats.sign_in_attempts == ["candidate@example.com"], "exactly one attempt"
    assert report.intervention is not None
    assert report.intervention.type == InterventionType.AUTHENTICATION_REQUIRED
    assert report.status == ApplicationStatus.WAITING_FOR_VERIFICATION


def test_a_captcha_after_sign_in_still_stops_the_run(browser_manager, mock_ats, run_async):
    """A correct password never becomes a way past a challenge."""
    report = run_async(
        _run(
            browser_manager,
            mock_ats.url("/login-captcha"),
            AtsKind.GENERIC,
            credential=CREDENTIAL,
        )
    )

    assert report.intervention is not None
    assert report.intervention.type == InterventionType.CAPTCHA
    assert report.status == ApplicationStatus.WAITING_FOR_VERIFICATION


def test_a_sign_in_wall_without_a_stored_credential_still_pauses(
    browser_manager, mock_ats, run_async
):
    report = run_async(_run(browser_manager, mock_ats.url("/login"), AtsKind.GENERIC))

    assert mock_ats.sign_in_attempts == [], "nothing was typed into the sign-in form"
    assert report.intervention is not None
    assert report.intervention.type == InterventionType.AUTHENTICATION_REQUIRED
