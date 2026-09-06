"""Analytics reports what happened and nothing more."""

from __future__ import annotations

import io
import uuid
from pathlib import Path

import pytest
from jobapply_db.models import Application, User
from sqlalchemy import select

FIXTURE = Path(__file__).parent.parent / "fixtures" / "resumes" / "sample_resume.txt"


@pytest.fixture
def with_applications(api, registered, db_session):
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

    from jobapply_shared.dates import utcnow

    user = db_session.execute(select(User)).scalar_one()
    user.onboarding_completed_at = utcnow()
    user.automation_paused = False
    db_session.commit()
    api.put("/automation-settings", json={"enabled": True, "min_match_score": 50})

    jobs = sorted(
        api.get("/jobs").json()["items"],
        key=lambda item: item["match"]["overall_score"],
        reverse=True,
    )
    created = [api.post("/applications", json={"job_id": job["id"]}).json() for job in jobs[:2]]

    # Give the first one a real-world outcome the way the tracker would.
    application = db_session.get(Application, uuid.UUID(created[0]["id"]))
    application.status = "INTERVIEW"
    application.submitted_at = utcnow()
    db_session.commit()
    return created


def test_an_empty_account_reports_zeros_not_estimates(api, registered):
    report = api.get("/analytics").json()
    assert report["outcomes"]["submitted"] == 0
    assert report["outcomes"]["response_rate"] == 0.0
    assert report["automation"]["success_rate"] == 0.0
    assert all(point["created"] == 0 for point in report["applications_per_day"])
    assert report["by_company"] == []


def test_the_series_covers_every_day_in_the_window(api, registered):
    report = api.get("/analytics?range=14").json()
    assert report["range_days"] == 14
    assert len(report["applications_per_day"]) == 15, "inclusive of today"
    dates = [point["date"] for point in report["applications_per_day"]]
    assert dates == sorted(dates)


def test_applications_show_up_in_the_series_and_breakdowns(api, with_applications):
    report = api.get("/analytics").json()
    assert report["applications_per_day"][-1]["created"] == 2
    assert sum(item["count"] for item in report["by_company"]) == 2
    assert report["by_company"][0]["label"]
    assert sum(item["count"] for item in report["by_role"]) == 2


def test_the_funnel_reflects_real_counts(api, with_applications):
    funnel = {stage["stage"]: stage["count"] for stage in api.get("/analytics").json()["funnel"]}
    assert funnel["discovered"] == 3
    assert funnel["matched"] == 3
    assert funnel["applied"] == 1, "only the one that was actually submitted"
    assert funnel["interview"] == 1


def test_outcomes_are_computed_from_submitted_applications(api, with_applications):
    outcomes = api.get("/analytics").json()["outcomes"]
    assert outcomes["submitted"] == 1
    assert outcomes["interviews"] == 1
    assert outcomes["response_rate"] == 100.0


def test_match_scores_are_bucketed(api, with_applications):
    distribution = api.get("/analytics").json()["match_score_distribution"]
    assert sum(item["count"] for item in distribution) == 3
    assert [item["label"] for item in distribution] == ["0–39", "40–59", "60–74", "75–89", "90–100"]


def test_automation_health_is_separate_from_hiring_outcomes(api, with_applications):
    automation = api.get("/analytics").json()["automation"]
    assert automation["succeeded"] == 1
    assert automation["failed"] == 0
    assert automation["success_rate"] == 100.0


def test_analytics_are_private_to_each_user(api, with_applications):
    api.post("/auth/logout")
    second = api.post(
        "/auth/register", json={"email": "second@example.com", "password": "Str0ngPassword!"}
    )
    api.set_csrf(second.json()["csrf_token"])
    report = api.get("/analytics").json()
    assert report["outcomes"]["submitted"] == 0
    assert report["by_company"] == []


def test_analytics_requires_authentication(api):
    assert api.get("/analytics").status_code == 401
