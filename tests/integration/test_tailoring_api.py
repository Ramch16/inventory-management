"""Tailored resume generation through the API."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from jobapply_db.models import Resume, ResumeVersion
from sqlalchemy import select

FIXTURE = Path(__file__).parent.parent / "fixtures" / "resumes" / "sample_resume.txt"


@pytest.fixture
def ready(api, registered):
    """A user with a master resume, imported experience, skills and a discovered job."""
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
            "current_title": "Senior Data Engineer",
            "years_experience": 6,
        },
    )
    api.post("/jobs/search", json={})
    jobs = api.get("/jobs").json()["items"]
    return {"resume_id": resume_id, "job_id": jobs[0]["id"], "jobs": jobs}


def test_tailoring_creates_a_version_without_touching_the_master(api, ready, db_session):
    before = db_session.execute(select(Resume)).scalar_one()
    before_checksum, before_text = before.original_checksum, before.raw_text

    response = api.post("/resumes/tailor", json={"job_id": ready["job_id"]})
    assert response.status_code == 201
    version = response.json()
    assert version["version"] == 1
    assert version["docx_storage_key"] and version["pdf_storage_key"]

    db_session.expire_all()
    after = db_session.execute(select(Resume)).scalar_one()
    assert after.original_checksum == before_checksum
    assert after.raw_text == before_text


def test_every_generated_statement_has_provenance(api, ready):
    version = api.post("/resumes/tailor", json={"job_id": ready["job_id"]}).json()
    assert version["provenance"]
    for record in version["provenance"]:
        assert record["generated_text"]
        assert record["source_ids"], "every statement must trace to a source record"


def test_the_truth_report_is_stored_with_the_version(api, ready):
    version = api.post("/resumes/tailor", json={"job_id": ready["job_id"]}).json()
    assert version["truth_report"]["allowed"] is True
    assert version["truth_report"]["rejected_statements"] == []


def test_a_quality_score_is_produced(api, ready):
    version = api.post("/resumes/tailor", json={"job_id": ready["job_id"]}).json()
    quality = version["quality"]
    assert 0 <= quality["overall"] <= 100
    assert quality["ats_readability"] >= 70
    assert quality["factual_consistency"] == 100


def test_tailored_content_only_contains_the_users_own_experience(api, ready):
    version = api.post("/resumes/tailor", json={"job_id": ready["job_id"]}).json()
    companies = {role["company"] for role in version["content"]["experience"]}
    assert companies == {"Northwind Analytics", "Cobalt Software"}


def test_repeated_tailoring_increments_the_version(api, ready):
    first = api.post("/resumes/tailor", json={"job_id": ready["job_id"]}).json()
    second = api.post("/resumes/tailor", json={"job_id": ready["job_id"]}).json()
    assert second["version"] == first["version"] + 1

    listed = api.get(f"/resume-versions/for-job/{ready['job_id']}").json()
    assert [item["version"] for item in listed] == [2, 1]


@pytest.mark.parametrize("template", ["ats_classic", "modern_professional", "technical", "minimal"])
def test_each_template_can_be_requested(api, ready, template):
    version = api.post(
        "/resumes/tailor", json={"job_id": ready["job_id"], "template": template}
    ).json()
    assert version["template"] == template


def test_the_generated_pdf_and_docx_can_be_downloaded(api, ready):
    version_id = api.post("/resumes/tailor", json={"job_id": ready["job_id"]}).json()["id"]

    pdf = api.get(f"/resume-versions/{version_id}/file?fmt=pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")

    docx = api.get(f"/resume-versions/{version_id}/file?fmt=docx")
    assert docx.status_code == 200
    assert docx.content.startswith(b"PK")


def test_an_unsupported_format_is_refused(api, ready):
    version_id = api.post("/resumes/tailor", json={"job_id": ready["job_id"]}).json()["id"]
    response = api.get(f"/resume-versions/{version_id}/file?fmt=txt")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_format"


def test_tailoring_requires_a_master_resume(api, registered):
    api.post("/jobs/search", json={})
    job_id = api.get("/jobs").json()["items"][0]["id"]
    response = api.post("/resumes/tailor", json={"job_id": job_id})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "no_master_resume"


def test_tailoring_requires_approved_experience(api, registered):
    api.post("/resumes/text", json={"title": "Bare", "content": "x" * 60})
    api.post("/jobs/search", json={})
    job_id = api.get("/jobs").json()["items"][0]["id"]
    response = api.post("/resumes/tailor", json={"job_id": job_id})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "no_experience_records"


def test_a_user_cannot_read_another_users_tailored_resume(api, ready):
    version_id = api.post("/resumes/tailor", json={"job_id": ready["job_id"]}).json()["id"]
    api.post("/auth/logout")
    second = api.post(
        "/auth/register", json={"email": "second@example.com", "password": "Str0ngPassword!"}
    )
    api.set_csrf(second.json()["csrf_token"])
    assert api.get(f"/resume-versions/{version_id}").status_code == 404
    assert api.get(f"/resume-versions/{version_id}/file").status_code == 404


def test_versions_are_stored_against_the_master_resume(api, ready, db_session):
    api.post("/resumes/tailor", json={"job_id": ready["job_id"]})
    version = db_session.execute(select(ResumeVersion)).scalar_one()
    assert str(version.resume_id) == ready["resume_id"]
    assert str(version.job_id) == ready["job_id"]
