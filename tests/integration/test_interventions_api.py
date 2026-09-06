"""The human-intervention lifecycle.

A run report produced by the automation is fed through the service exactly as the
worker would, so the pause → notify → answer → re-queue path is exercised without a
browser.
"""

from __future__ import annotations

import io
import uuid
from pathlib import Path

import pytest
from jobapply_browser.engine import InterventionRequest, RunReport
from jobapply_browser.models import (
    ConfirmationResult,
    FieldOption,
    FormSpec,
    NormalizedField,
    ResolvedAnswer,
)
from jobapply_db.models import (
    Application,
    ApplicationAnswer,
    ApplicationTask,
    Intervention,
    Notification,
    User,
)
from jobapply_shared.enums import (
    AnswerSource,
    ApplicationStatus,
    AutomationRunState,
    FieldType,
    InterventionType,
    QuestionCategory,
)
from sqlalchemy import select

FIXTURE = Path(__file__).parent.parent / "fixtures" / "resumes" / "sample_resume.txt"


@pytest.fixture
def application_row(api, registered, db_session):
    api.post(
        "/resumes/upload",
        files={"file": ("resume.txt", io.BytesIO(FIXTURE.read_bytes()), "text/plain")},
    )
    resume_id = api.get("/resumes").json()[0]["id"]
    api.post(f"/resumes/{resume_id}/import", json={})
    api.put(
        "/profile",
        json={
            "first_name": "Jordan",
            "last_name": "Rivera",
            "email": "jordan@example.com",
            "phone": "+1 415 555 0142",
            "city": "San Francisco",
            "country": "United States",
            "current_title": "Senior Data Engineer",
            "years_experience": 6,
        },
    )
    api.put(
        "/profile/work-authorization",
        json={
            "authorization_country": "United States",
            "authorization_type": "citizen",
            "requires_sponsorship_now": False,
            "requires_sponsorship_future": False,
            "confirmed": True,
        },
    )
    api.post("/jobs/search", json={})
    api.post("/jobs/rescore")

    from jobapply_shared.dates import utcnow

    user = db_session.execute(select(User)).scalar_one()
    user.onboarding_completed_at = utcnow()
    user.automation_paused = False
    db_session.commit()
    api.put("/automation-settings", json={"enabled": True, "min_match_score": 50})

    jobs = api.get("/jobs").json()["items"]
    top = max(jobs, key=lambda item: item["match"]["overall_score"])
    return api.post("/applications", json={"job_id": top["id"]}).json()


def captcha_report() -> RunReport:
    report = RunReport()
    report.state = AutomationRunState.CAPTCHA_REQUIRED
    report.status = ApplicationStatus.WAITING_FOR_VERIFICATION
    report.page_url = "https://boards.greenhouse.io/acme/jobs/1"
    report.page_title = "Apply"
    report.intervention = InterventionRequest(
        type=InterventionType.CAPTCHA,
        reason="This page uses a CAPTCHA. The platform does not solve CAPTCHAs.",
        current_step="navigate",
        payload={"evidence": ["reCAPTCHA widget"], "screenshot_key": "screenshots/x.png"},
    )
    report.step("navigate", "paused", "captcha")
    return report


def question_report() -> RunReport:
    form = FormSpec(
        url="https://boards.greenhouse.io/acme/jobs/1",
        fields=[
            NormalizedField(
                field_id="first_name", label="First Name", type=FieldType.TEXT, required=True
            ),
            NormalizedField(
                field_id="why",
                label="Why are you interested in this role?",
                type=FieldType.TEXTAREA,
                required=True,
            ),
            NormalizedField(
                field_id="veteran",
                label="Are you a protected veteran?",
                type=FieldType.SELECT,
                required=True,
                options=[
                    FieldOption(label="Yes", value="1"),
                    FieldOption(label="No", value="2"),
                    FieldOption(label="I prefer not to answer", value="3"),
                ],
            ),
        ],
    )
    report = RunReport()
    report.form = form
    report.state = AutomationRunState.LOW_CONFIDENCE
    report.status = ApplicationStatus.WAITING_FOR_VERIFICATION
    report.answers = [
        ResolvedAnswer(
            field_id="first_name",
            answer="Jordan",
            confidence=0.99,
            source=AnswerSource.PROFILE,
            requires_review=False,
        ),
        ResolvedAnswer(
            field_id="why",
            answer=None,
            confidence=0.0,
            requires_review=True,
            reason="No answer could be derived from your profile.",
        ),
        ResolvedAnswer(
            field_id="veteran",
            answer="3",
            confidence=0.0,
            requires_review=True,
            is_sensitive=True,
            category=QuestionCategory.VETERAN,
            reason="Only you can answer this.",
        ),
    ]
    report.intervention = InterventionRequest(
        type=InterventionType.MISSING_DATA,
        reason="Some questions need you.",
        current_step="answer_questions",
        payload={
            "questions": [
                {"field_id": "why", "question": "Why are you interested in this role?"},
                {"field_id": "veteran", "question": "Are you a protected veteran?"},
            ]
        },
    )
    return report


def _apply(db_session, application_id: str, report: RunReport):
    from jobapply_api.services.application_service import ApplicationService
    from jobapply_api.services.notification_service import NotificationService
    from jobapply_shared.email import ConsoleEmailSender

    application = db_session.get(Application, uuid.UUID(application_id))
    service = ApplicationService(db_session, NotificationService(db_session, ConsoleEmailSender()))
    service.apply_run_report(application, report)
    db_session.commit()
    return application


def test_a_captcha_opens_an_intervention_and_notifies(api, application_row, db_session):
    _apply(db_session, application_row["id"], captcha_report())

    page = api.get("/interventions").json()
    assert page["total"] == 1
    item = page["items"][0]
    assert item["type"] == "captcha"
    assert item["status"] == "open"
    assert item["requires_browser"] is True
    assert "does not solve CAPTCHAs" in item["reason"]
    assert item["company_name"]

    kinds = {row.kind for row in db_session.execute(select(Notification)).scalars()}
    assert "captcha_required" in kinds


def test_the_application_shows_as_waiting_for_verification(api, application_row, db_session):
    _apply(db_session, application_row["id"], captcha_report())
    detail = api.get(f"/applications/{application_row['id']}").json()
    assert detail["status"] == "WAITING_FOR_VERIFICATION"
    assert detail["open_interventions"] == 1


def test_the_dashboard_surfaces_what_needs_attention(api, application_row, db_session):
    _apply(db_session, application_row["id"], captcha_report())
    dashboard = api.get("/dashboard").json()
    assert dashboard["counters"]["open_interventions"] == 1
    assert dashboard["attention_required"][0]["type"] == "captcha"


def test_questions_and_answers_are_persisted_for_review(api, application_row, db_session):
    _apply(db_session, application_row["id"], question_report())
    detail = api.get(f"/applications/{application_row['id']}").json()

    questions = {item["field_id"]: item for item in detail["questions"]}
    assert questions["first_name"]["answer"] == "Jordan"
    assert questions["first_name"]["requires_review"] is False
    assert questions["why"]["answer"] is None
    assert questions["veteran"]["is_sensitive"] is True
    assert questions["veteran"]["requires_review"] is True


def test_continuing_records_the_answers_and_requeues(api, application_row, db_session):
    _apply(db_session, application_row["id"], question_report())
    intervention_id = api.get("/interventions").json()["items"][0]["id"]

    response = api.post(
        f"/interventions/{intervention_id}/continue",
        json={"answers": {"why": "The data platform work.", "veteran": "2"}},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "queued"

    db_session.expire_all()
    detail = api.get(f"/applications/{application_row['id']}").json()
    questions = {item["field_id"]: item for item in detail["questions"]}
    assert questions["why"]["answer"] == "The data platform work."
    assert questions["why"]["requires_review"] is False
    assert questions["why"]["source"] == "user_provided"
    assert questions["veteran"]["approved_by_user_at"] is not None

    assert api.get("/interventions").json()["total"] == 0
    assert detail["status"] == "APPLICATION_STARTING"

    tasks = db_session.execute(select(ApplicationTask)).scalars().all()
    assert any(task.kind == "apply_resume" for task in tasks)


def test_a_one_time_code_is_never_stored(api, application_row, db_session):
    _apply(db_session, application_row["id"], captcha_report())
    intervention_id = api.get("/interventions").json()["items"][0]["id"]

    api.post(f"/interventions/{intervention_id}/continue", json={"otp_code": "483920"})

    from jobapply_db.models import AuditLog

    haystack = " ".join(
        [str(row.data) for row in db_session.execute(select(AuditLog)).scalars()]
        + [
            str(row.payload) + str(row.reason)
            for row in db_session.execute(select(Intervention)).scalars()
        ]
        + [str(row.answer) for row in db_session.execute(select(ApplicationAnswer)).scalars()]
    )
    assert "483920" not in haystack


def test_cancelling_an_intervention_cancels_the_application(api, application_row, db_session):
    _apply(db_session, application_row["id"], captcha_report())
    intervention_id = api.get("/interventions").json()["items"][0]["id"]

    assert api.post(f"/interventions/{intervention_id}/cancel").status_code == 204
    assert api.get(f"/applications/{application_row['id']}").json()["status"] == "CANCELLED"
    assert api.get("/interventions?status=cancelled").json()["total"] == 1


def test_an_intervention_cannot_be_resolved_twice(api, application_row, db_session):
    _apply(db_session, application_row["id"], captcha_report())
    intervention_id = api.get("/interventions").json()["items"][0]["id"]

    api.post(f"/interventions/{intervention_id}/continue", json={})
    second = api.post(f"/interventions/{intervention_id}/continue", json={})
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "intervention_closed"


def test_a_user_cannot_resolve_another_users_intervention(api, application_row, db_session):
    _apply(db_session, application_row["id"], captcha_report())
    intervention_id = api.get("/interventions").json()["items"][0]["id"]

    api.post("/auth/logout")
    second = api.post(
        "/auth/register", json={"email": "second@example.com", "password": "Str0ngPassword!"}
    )
    api.set_csrf(second.json()["csrf_token"])
    assert api.post(f"/interventions/{intervention_id}/continue", json={}).status_code == 404


def test_an_unconfirmed_submission_is_never_reported_as_applied(api, application_row, db_session):
    report = RunReport()
    report.status = ApplicationStatus.SUBMISSION_UNCONFIRMED
    report.state = AutomationRunState.COMPLETED
    report.confirmation = ConfirmationResult(confirmed=False, url="https://example.test/done")
    _apply(db_session, application_row["id"], report)

    detail = api.get(f"/applications/{application_row['id']}").json()
    assert detail["status"] == "SUBMISSION_UNCONFIRMED"
    assert detail["confirmation_id"] is None

    notifications = api.get("/notifications").json()
    assert any("not confirmed" in item["title"] for item in notifications)


def test_a_confirmed_submission_records_its_evidence(api, application_row, db_session):
    report = RunReport()
    report.status = ApplicationStatus.CONFIRMATION_CAPTURED
    report.state = AutomationRunState.COMPLETED
    report.confirmation = ConfirmationResult(
        confirmed=True,
        confirmation_id="NW-48213-A",
        url="https://example.test/done",
        text="Thank you for applying.",
        signals=["thank you"],
    )
    _apply(db_session, application_row["id"], report)

    detail = api.get(f"/applications/{application_row['id']}").json()
    assert detail["status"] == "CONFIRMATION_CAPTURED"
    assert detail["confirmation_id"] == "NW-48213-A"
    assert detail["submitted_at"] is not None
