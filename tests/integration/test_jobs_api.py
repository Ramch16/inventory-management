"""Job discovery, browsing, matching and preferences through the API."""

from __future__ import annotations

import pytest
from jobapply_db.models import Job, JobMatch
from sqlalchemy import select


@pytest.fixture
def ready_profile(api, registered):
    """A profile complete enough for matching to be meaningful."""
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
            "desired_titles": ["Data Engineer", "Analytics Engineer"],
            "desired_locations": ["San Francisco, CA"],
            "salary_min": 150000,
        },
    )
    for skill in ["Python", "SQL", "Airflow", "dbt", "Snowflake", "Terraform"]:
        api.post("/profile/skills", json={"name": skill})
    api.post(
        "/profile/education",
        json={"institution": "University of Texas at Austin", "degree": "B.S. Computer Science"},
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
    return registered


def test_default_sources_are_created_with_only_the_offline_one_enabled(api, registered):
    sources = api.get("/job-sources").json()
    slugs = {source["slug"]: source["enabled"] for source in sources}
    assert slugs["sample"] is True
    assert slugs["greenhouse"] is False, "reaching a third party must be opt-in"
    assert slugs["lever"] is False


def test_discovery_stores_normalized_jobs(api, ready_profile, db_session):
    result = api.post("/jobs/search", json={}).json()
    assert result["fetched"] == 3
    assert result["created"] == 3
    assert result["scored"] == 3
    assert result["errors"] == []

    jobs = db_session.execute(select(Job)).scalars().all()
    northwind = next(job for job in jobs if job.company_name == "Northwind Analytics")
    assert northwind.salary_min == 160000
    assert northwind.remote_type == "hybrid"
    assert northwind.detected_ats == "greenhouse"
    assert northwind.sponsorship_offered is False
    assert "python" in northwind.skills
    assert northwind.experience_required_years == 5


def test_discovery_is_idempotent(api, ready_profile):
    first = api.post("/jobs/search", json={}).json()
    second = api.post("/jobs/search", json={}).json()
    assert first["created"] == 3
    assert second["created"] == 0
    assert second["duplicates"] == 3
    assert api.get("/jobs").json()["total"] == 3


def test_jobs_are_listed_with_their_match(api, ready_profile):
    api.post("/jobs/search", json={})
    page = api.get("/jobs").json()
    assert page["total"] == 3

    top = page["items"][0]
    assert top["match"]["overall_score"] >= 80
    assert top["match"]["recommendation"] == "APPLY"
    assert "python" in top["match"]["matched_skills"]
    assert top["application_status"] is None


def test_jobs_are_ordered_by_score(api, ready_profile):
    api.post("/jobs/search", json={})
    scores = [item["match"]["overall_score"] for item in api.get("/jobs").json()["items"]]
    assert scores == sorted(scores, reverse=True)


def test_jobs_can_be_filtered_by_score_and_recommendation(api, ready_profile):
    api.post("/jobs/search", json={})
    high = api.get("/jobs?min_score=80").json()
    assert all(item["match"]["overall_score"] >= 80 for item in high["items"])

    skips = api.get("/jobs?recommendation=SKIP").json()
    assert all(item["match"]["recommendation"] == "SKIP" for item in skips["items"])


def test_job_detail_includes_requirements_and_sponsorship_language(api, ready_profile):
    api.post("/jobs/search", json={})
    job_id = api.get("/jobs").json()["items"][0]["id"]
    detail = api.get(f"/jobs/{job_id}").json()
    assert detail["requirements"]
    assert detail["description"]
    assert "<p>" not in (detail["description"] or "")


def test_rescoring_reflects_a_profile_change(api, ready_profile, db_session):
    api.post("/jobs/search", json={})
    before = api.get("/jobs").json()["items"][0]["match"]["overall_score"]

    for skill in api.get("/profile/skills").json():
        api.delete(f"/profile/skills/{skill['id']}")
    api.post("/jobs/rescore")

    after = api.get("/jobs").json()["items"][0]["match"]["overall_score"]
    assert after < before


def test_a_hard_requirement_failure_cannot_be_approved(api, ready_profile):
    api.put("/preferences", json={"excluded_titles": ["senior director"]})
    api.post("/jobs/search", json={})
    api.post("/jobs/rescore")

    jobs = api.get("/jobs").json()["items"]
    blocked = next(item for item in jobs if "Director" in item["title"])
    assert blocked["match"]["hard_requirement_failed"] is True

    response = api.post(f"/jobs/{blocked['id']}/decision", json={"decision": "approve"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "hard_requirement_failed"

    assert api.post(f"/jobs/{blocked['id']}/decision", json={"decision": "skip"}).status_code == 200


def test_a_good_match_can_be_approved(api, ready_profile):
    api.post("/jobs/search", json={})
    job_id = api.get("/jobs").json()["items"][0]["id"]
    response = api.post(f"/jobs/{job_id}/decision", json={"decision": "approve"})
    assert response.status_code == 200
    assert response.json()["user_decision"] == "approve"


def test_preferences_narrow_what_discovery_asks_for(api, ready_profile):
    """Target titles are passed through to the sources, so discovery returns less."""
    api.put("/preferences", json={"target_titles": ["Analytics Engineer"]})
    result = api.post("/jobs/search", json={}).json()
    assert result["created"] == 1
    assert api.get("/jobs").json()["items"][0]["title"].startswith("Analytics Engineer")


def test_preferences_round_trip_and_drive_matching(api, ready_profile):
    response = api.put(
        "/preferences",
        json={
            "excluded_companies": ["Northwind Analytics"],
            "match_weights": {
                "skills": 0.5,
                "experience": 0.2,
                "title": 0.1,
                "education": 0.05,
                "location": 0.05,
                "authorization": 0.1,
            },
        },
    )
    assert response.status_code == 200
    assert response.json()["excluded_companies"] == ["Northwind Analytics"]

    api.post("/jobs/search", json={})
    api.post("/jobs/rescore")
    jobs = api.get("/jobs").json()["items"]
    northwind = next(item for item in jobs if item["company_name"] == "Northwind Analytics")
    assert northwind["match"]["hard_requirement_failed"] is True
    assert northwind["match"]["recommendation"] == "SKIP"


def test_zero_match_weights_are_rejected(api, ready_profile):
    response = api.put(
        "/preferences",
        json={
            "match_weights": {
                "skills": 0,
                "experience": 0,
                "title": 0,
                "education": 0,
                "location": 0,
                "authorization": 0,
            }
        },
    )
    assert response.status_code == 422


def test_matches_are_private_to_each_user(api, ready_profile, db_session):
    api.post("/jobs/search", json={})
    api.post("/auth/logout")
    second = api.post(
        "/auth/register", json={"email": "second@example.com", "password": "Str0ngPassword!"}
    )
    api.set_csrf(second.json()["csrf_token"])

    page = api.get("/jobs").json()
    assert page["total"] == 3, "jobs themselves are shared"
    assert all(item["match"] is None for item in page["items"]), "matches are not"

    matches = db_session.execute(select(JobMatch)).scalars().all()
    assert len({match.user_id for match in matches}) == 1


def test_job_endpoints_require_authentication(api):
    assert api.get("/jobs").status_code == 401
    assert api.post("/jobs/search", json={}).status_code == 401
