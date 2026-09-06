"""Profile endpoints, including the deliberately separate work-authorization flow."""

from __future__ import annotations

import pytest


def test_profile_is_created_with_the_account(api, registered):
    response = api.get("/profile")
    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "Jordan"
    assert body["work_authorization"]["declared"] is False


def test_profile_update_round_trip(api, registered):
    payload = {
        "current_title": "Senior Data Engineer",
        "years_experience": 6,
        "city": "San Francisco",
        "state": "CA",
        "country": "United States",
        "phone": "+1 415 555 0142",
        "desired_titles": ["Data Engineer", "Analytics Engineer"],
        "remote_preference": "remote",
        "salary_min": 150000,
        "salary_max": 190000,
    }
    response = api.put("/profile", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["current_title"] == "Senior Data Engineer"
    assert body["desired_titles"] == ["Data Engineer", "Analytics Engineer"]
    assert api.get("/profile").json()["salary_min"] == 150000


def test_salary_range_is_validated(api, registered):
    response = api.put("/profile", json={"salary_min": 200000, "salary_max": 100000})
    assert response.status_code == 422


def test_unknown_profile_fields_are_rejected(api, registered):
    response = api.put("/profile", json={"requires_sponsorship_now": False})
    assert response.status_code == 422, (
        "work authorization must not be settable through the general profile endpoint"
    )


def test_work_authorization_requires_explicit_confirmation(api, registered):
    payload = {
        "authorization_country": "United States",
        "authorization_type": "citizen",
        "requires_sponsorship_now": False,
        "requires_sponsorship_future": False,
        "confirmed": False,
    }
    assert api.put("/profile/work-authorization", json=payload).status_code == 422

    payload["confirmed"] = True
    response = api.put("/profile/work-authorization", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["declared"] is True
    assert body["work_authorization_confirmed_at"] is not None


def test_partial_work_authorization_is_rejected(api, registered):
    response = api.put(
        "/profile/work-authorization",
        json={"authorization_country": "United States", "confirmed": True},
    )
    assert response.status_code == 422


def test_experience_crud(api, registered):
    created = api.post(
        "/profile/experience",
        json={
            "company": "Northwind Analytics",
            "title": "Senior Data Engineer",
            "start_date": "2021-03-01",
            "is_current": True,
            "accomplishments": ["Built automated pipelines with Python and SQL"],
            "technologies": ["Python", "SQL", "Airflow"],
        },
    )
    assert created.status_code == 201
    record_id = created.json()["id"]

    listed = api.get("/profile/experience").json()
    assert len(listed) == 1 and listed[0]["company"] == "Northwind Analytics"

    updated = api.put(
        f"/profile/experience/{record_id}",
        json={
            "company": "Northwind Analytics",
            "title": "Staff Data Engineer",
            "start_date": "2021-03-01",
            "is_current": True,
            "accomplishments": ["Built automated pipelines with Python and SQL"],
            "technologies": ["Python", "SQL", "Airflow"],
        },
    )
    assert updated.json()["title"] == "Staff Data Engineer"

    assert api.delete(f"/profile/experience/{record_id}").status_code == 204
    assert api.get("/profile/experience").json() == []


def test_a_current_position_cannot_have_an_end_date(api, registered):
    response = api.post(
        "/profile/experience",
        json={
            "company": "Acme",
            "title": "Engineer",
            "start_date": "2020-01-01",
            "end_date": "2022-01-01",
            "is_current": True,
        },
    )
    assert response.status_code == 422


def test_skills_are_deduplicated_case_insensitively(api, registered):
    assert api.post("/profile/skills", json={"name": "Python"}).status_code == 201
    duplicate = api.post("/profile/skills", json={"name": "  python "})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "skill_exists"


def test_deleting_and_re_adding_a_skill_reuses_the_record(api, registered):
    created = api.post("/profile/skills", json={"name": "Python"}).json()
    assert api.delete(f"/profile/skills/{created['id']}").status_code == 204
    recreated = api.post("/profile/skills", json={"name": "Python", "years_experience": 5})
    assert recreated.status_code == 201
    assert recreated.json()["years_experience"] == 5


def test_education_and_certification_crud(api, registered):
    education = api.post(
        "/profile/education",
        json={
            "institution": "University of Texas at Austin",
            "degree": "B.S. Computer Science",
            "end_date": "2018-05-01",
            "gpa": 3.7,
        },
    )
    assert education.status_code == 201

    certification = api.post(
        "/profile/certifications",
        json={"name": "AWS Certified Solutions Architect", "issuer": "Amazon Web Services"},
    )
    assert certification.status_code == 201
    assert len(api.get("/profile/certifications").json()) == 1


def test_completeness_reports_automation_blockers(api, registered):
    initial = api.get("/profile/completeness").json()
    assert initial["ready_for_automation"] is False
    assert any("work authorization" in item.lower() for item in initial["blocks_automation"])

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
    api.post(
        "/profile/experience",
        json={
            "company": "Northwind Analytics",
            "title": "Senior Data Engineer",
            "is_current": True,
        },
    )
    api.post("/profile/skills", json={"name": "Python"})
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

    final = api.get("/profile/completeness").json()
    assert final["ready_for_automation"] is True
    assert final["blocks_automation"] == []
    assert final["score"] > initial["score"]


@pytest.mark.parametrize(
    "path",
    ["/profile", "/profile/experience", "/profile/skills", "/profile/completeness"],
)
def test_profile_endpoints_require_authentication(api, path):
    assert api.get(path).status_code == 401


def test_users_cannot_reach_another_users_records(api, registered):
    other = api.post("/profile/experience", json={"company": "Acme", "title": "Engineer"}).json()[
        "id"
    ]

    api.post("/auth/logout")
    second = api.post(
        "/auth/register", json={"email": "second@example.com", "password": "Str0ngPassword!"}
    )
    api.set_csrf(second.json()["csrf_token"])

    assert api.delete(f"/profile/experience/{other}").status_code == 404
    assert api.get("/profile/experience").json() == []
