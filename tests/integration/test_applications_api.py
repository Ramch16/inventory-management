"""Application creation, policy gates, the queue and manual status tracking."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from jobapply_db.models import Application, ApplicationTask, User
from sqlalchemy import select

FIXTURE = Path(__file__).parent.parent / "fixtures" / "resumes" / "sample_resume.txt"


@pytest.fixture
def automating(api, registered, db_session):
    """A user who is fully set up and has switched automation on."""
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
            "state": "CA",
            "country": "United States",
            "current_title": "Senior Data Engineer",
            "years_experience": 6,
            "desired_titles": ["Data Engineer"],
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

    # Onboarding must be complete before automation may be enabled.
    user = db_session.execute(select(User)).scalar_one()
    from jobapply_shared.dates import utcnow

    user.onboarding_completed_at = utcnow()
    user.automation_paused = False
    db_session.commit()

    api.put("/automation-settings", json={"enabled": True, "min_match_score": 50})

    jobs = api.get("/jobs").json()["items"]
    top = max(jobs, key=lambda item: item["match"]["overall_score"])
    return {"job_id": top["id"], "jobs": jobs, "resume_id": resume_id}


def test_automation_cannot_be_enabled_before_onboarding(api, registered):
    response = api.put("/automation-settings", json={"enabled": True})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "onboarding_incomplete"


def test_creating_an_application_generates_the_tailored_resume(api, automating, db_session):
    response = api.post("/applications", json={"job_id": automating["job_id"]})
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "APPROVED"
    assert body["company_name"]

    application = db_session.execute(select(Application)).scalar_one()
    assert application.resume_version_id is not None
    assert application.dedupe_hash


def test_a_duplicate_application_is_refused(api, automating):
    api.post("/applications", json={"job_id": automating["job_id"]})
    response = api.post("/applications", json={"job_id": automating["job_id"]})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "already_applied"


def test_a_job_below_the_minimum_score_is_refused(api, automating):
    api.put("/automation-settings", json={"min_match_score": 99})
    response = api.post("/applications", json={"job_id": automating["job_id"]})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "below_minimum_score"


def test_a_hard_requirement_failure_is_refused(api, automating):
    api.put("/preferences", json={"excluded_titles": ["senior director"]})
    api.post("/jobs/rescore")
    blocked = next(item for item in api.get("/jobs").json()["items"] if "Director" in item["title"])
    response = api.post("/applications", json={"job_id": blocked["id"]})
    assert response.status_code == 422
    assert response.json()["error"]["code"] in {
        "hard_requirement_failed",
        "below_minimum_score",
    }


def test_an_excluded_company_is_refused(api, automating):
    api.put("/preferences", json={"excluded_companies": ["Northwind Analytics"]})
    api.post("/jobs/rescore")
    response = api.post("/applications", json={"job_id": automating["job_id"]})
    assert response.status_code == 422
    codes = {item["code"] for item in response.json()["error"]["details"]["violations"]}
    assert "company_excluded" in codes or "hard_requirement_failed" in codes


def test_undeclared_work_authorization_blocks_applying(api, registered, db_session):
    api.post(
        "/resumes/upload",
        files={"file": ("resume.txt", io.BytesIO(FIXTURE.read_bytes()), "text/plain")},
    )
    api.post("/jobs/search", json={})
    job_id = api.get("/jobs").json()["items"][0]["id"]
    response = api.post("/applications", json={"job_id": job_id})
    assert response.status_code == 422
    codes = {item["code"] for item in response.json()["error"]["details"]["violations"]}
    assert "work_authorization_undeclared" in codes


def test_a_paused_account_cannot_create_applications(api, automating, db_session):
    api.post("/automation/pause", json={"paused": True})
    response = api.post("/applications", json={"job_id": automating["job_id"]})
    assert response.status_code == 422
    codes = {item["code"] for item in response.json()["error"]["details"]["violations"]}
    assert "automation_paused" in codes


def test_the_daily_limit_stops_further_applications(api, automating, db_session):
    from jobapply_shared.dates import utcnow

    api.put("/automation-settings", json={"daily_application_limit": 1})
    first = api.post("/applications", json={"job_id": automating["job_id"]}).json()

    # Mark it submitted the way the automation would, so it counts against the limit.
    application = db_session.get(Application, __import__("uuid").UUID(first["id"]))
    application.status = "SUBMITTED"
    application.submitted_at = utcnow()
    db_session.commit()

    other = next(
        item for item in api.get("/jobs").json()["items"] if item["id"] != automating["job_id"]
    )
    response = api.post("/applications", json={"job_id": other["id"]})
    assert response.status_code == 422
    codes = {item["code"] for item in response.json()["error"]["details"]["violations"]}
    assert "daily_limit_reached" in codes
    assert response.json()["error"]["details"]["retry_after_seconds"]


def test_starting_queues_a_task(api, automating, db_session):
    application_id = api.post("/applications", json={"job_id": automating["job_id"]}).json()["id"]
    response = api.post(f"/applications/{application_id}/start")
    assert response.status_code == 202
    assert response.json()["status"] == "queued"

    task = db_session.execute(select(ApplicationTask)).scalar_one()
    assert str(task.application_id) == application_id
    assert task.kind == "apply"

    detail = api.get(f"/applications/{application_id}").json()
    assert detail["status"] == "APPLICATION_STARTING"
    assert detail["attempts"] == 1
    assert any(step["name"] == "queued" for step in detail["steps"])


def test_starting_without_a_tailored_resume_is_refused(api, automating, db_session):
    application_id = api.post(
        "/applications", json={"job_id": automating["job_id"], "generate_resume": False}
    ).json()["id"]
    response = api.post(f"/applications/{application_id}/start")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "resume_not_ready"


def test_an_application_can_be_cancelled(api, automating):
    application_id = api.post("/applications", json={"job_id": automating["job_id"]}).json()["id"]
    assert api.post(f"/applications/{application_id}/cancel").status_code == 204
    assert api.get(f"/applications/{application_id}").json()["status"] == "CANCELLED"


def test_a_user_cannot_mark_an_application_submitted_by_hand(api, automating):
    application_id = api.post("/applications", json={"job_id": automating["job_id"]}).json()["id"]
    response = api.put(f"/applications/{application_id}/status", json={"status": "SUBMITTED"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "status_not_allowed"


def test_real_world_outcomes_can_be_recorded(api, automating):
    application_id = api.post("/applications", json={"job_id": automating["job_id"]}).json()["id"]
    response = api.put(
        f"/applications/{application_id}/status",
        json={"status": "INTERVIEW", "note": "Phone screen on Tuesday"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "INTERVIEW"


def test_applications_are_listed_with_their_job(api, automating):
    api.post("/applications", json={"job_id": automating["job_id"]})
    page = api.get("/applications").json()
    assert page["total"] == 1
    assert page["items"][0]["company_name"]
    assert page["items"][0]["open_interventions"] == 0


def test_history_can_be_exported_as_csv(api, automating):
    api.post("/applications", json={"job_id": automating["job_id"]})
    response = api.get("/applications/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "company,title,status" in response.text


def test_the_global_pause_is_reflected_everywhere(api, automating):
    paused = api.post("/automation/pause", json={"paused": True}).json()
    assert paused["automation_paused"] is True
    assert api.get("/automation-settings").json()["automation_paused"] is True
    assert api.get("/dashboard").json()["readiness"]["automation_paused"] is True

    resumed = api.post("/automation/pause", json={"paused": False}).json()
    assert resumed["automation_paused"] is False


def test_automation_settings_validate_their_ranges(api, automating):
    response = api.put(
        "/automation-settings", json={"min_delay_seconds": 300, "max_delay_seconds": 60}
    )
    assert response.status_code == 422


def test_a_user_cannot_see_another_users_application(api, automating):
    application_id = api.post("/applications", json={"job_id": automating["job_id"]}).json()["id"]
    api.post("/auth/logout")
    second = api.post(
        "/auth/register", json={"email": "second@example.com", "password": "Str0ngPassword!"}
    )
    api.set_csrf(second.json()["csrf_token"])
    assert api.get(f"/applications/{application_id}").status_code == 404
    assert api.get("/applications").json()["total"] == 0


def test_interventions_start_empty(api, automating):
    assert api.get("/interventions").json()["total"] == 0
