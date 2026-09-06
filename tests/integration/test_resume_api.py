"""Resume upload, parsing, master selection and import into the profile."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from jobapply_db.models import Resume, Skill
from sqlalchemy import select

FIXTURE = Path(__file__).parent.parent / "fixtures" / "resumes" / "sample_resume.txt"


@pytest.fixture
def resume_bytes() -> bytes:
    return FIXTURE.read_bytes()


def upload(api, data: bytes, filename: str = "resume.txt", content_type: str = "text/plain"):
    return api.post("/resumes/upload", files={"file": (filename, io.BytesIO(data), content_type)})


def test_upload_parses_and_becomes_the_master(api, registered, resume_bytes):
    response = upload(api, resume_bytes)
    assert response.status_code == 201
    body = response.json()
    assert body["parse_status"] == "parsed"
    assert body["is_master"] is True
    assert body["structured"]["contact"]["email"] == "jordan.rivera@example.com"
    assert len(body["structured"]["positions"]) == 2
    assert "Python" in body["structured"]["skills"]


def test_the_original_file_is_stored_unmodified(api, registered, resume_bytes, db_session):
    resume_id = upload(api, resume_bytes).json()["id"]
    stored = db_session.execute(select(Resume)).scalar_one()
    assert stored.original_storage_key
    assert stored.original_checksum

    response = api.get(f"/resumes/{resume_id}/file")
    assert response.status_code == 200
    assert response.content == resume_bytes, "the uploaded original must never be rewritten"


def test_upload_rejects_an_unsupported_extension(api, registered):
    response = upload(
        api, b"MZ\x90\x00binary", filename="resume.exe", content_type="application/octet-stream"
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_file_type"


def test_upload_rejects_a_file_over_the_size_limit(api, registered, settings):
    oversized = b"x" * (settings.upload_max_bytes + 1)
    response = upload(api, oversized)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "file_too_large"


def test_create_resume_from_pasted_text(api, registered, resume_bytes):
    response = api.post(
        "/resumes/text",
        json={"title": "Pasted resume", "content": resume_bytes.decode()},
    )
    assert response.status_code == 201
    assert response.json()["source_kind"] == "pasted_text"
    assert response.json()["structured"]["positions"]


def test_only_one_resume_is_master_at_a_time(api, registered, resume_bytes):
    first = upload(api, resume_bytes, filename="first.txt").json()
    second = upload(api, resume_bytes, filename="second.txt").json()
    assert first["is_master"] is True
    assert second["is_master"] is False

    promoted = api.post(f"/resumes/{second['id']}/master").json()
    assert promoted["is_master"] is True
    listed = {item["id"]: item["is_master"] for item in api.get("/resumes").json()}
    assert listed[first["id"]] is False
    assert listed[second["id"]] is True


def test_import_copies_records_into_the_profile(api, registered, resume_bytes, db_session):
    resume_id = upload(api, resume_bytes).json()["id"]
    result = api.post(
        f"/resumes/{resume_id}/import",
        json={
            "import_contact": True,
            "import_summary": True,
            "import_skills": True,
            "import_experience": True,
            "import_education": True,
            "import_certifications": True,
        },
    )
    assert result.status_code == 200
    body = result.json()
    assert body["experience_added"] == 2
    assert body["education_added"] == 1
    assert body["skills_added"] >= 5
    assert body["certifications_added"] == 2

    assert len(api.get("/profile/experience").json()) == 2
    profile = api.get("/profile").json()
    assert profile["linkedin_url"] == "https://linkedin.com/in/jordanrivera"


def test_import_splits_an_unambiguous_city_and_state(api, registered, resume_bytes):
    resume_id = upload(api, resume_bytes).json()["id"]
    api.post(f"/resumes/{resume_id}/import", json={})
    profile = api.get("/profile").json()
    assert profile["city"] == "San Francisco"
    assert profile["state"] == "CA"
    assert profile["country"] is None, "the country is never guessed from a state code"


def test_imported_skills_are_marked_unverified(api, registered, resume_bytes, db_session):
    resume_id = upload(api, resume_bytes).json()["id"]
    api.post(f"/resumes/{resume_id}/import", json={})
    skills = db_session.execute(select(Skill)).scalars().all()
    assert skills and all(skill.is_verified is False for skill in skills)


def test_import_never_touches_work_authorization(api, registered, resume_bytes):
    resume_id = upload(api, resume_bytes).json()["id"]
    result = api.post(f"/resumes/{resume_id}/import", json={})
    assert any("work authorization" in note.lower() for note in result.json()["notes"])
    assert api.get("/profile/work-authorization").json()["declared"] is False


def test_import_is_idempotent(api, registered, resume_bytes):
    resume_id = upload(api, resume_bytes).json()["id"]
    api.post(f"/resumes/{resume_id}/import", json={})
    second = api.post(f"/resumes/{resume_id}/import", json={}).json()
    assert second["experience_added"] == 0
    assert second["skills_added"] == 0
    assert len(api.get("/profile/experience").json()) == 2


def test_delete_soft_deletes_and_hides_the_resume(api, registered, resume_bytes):
    resume_id = upload(api, resume_bytes).json()["id"]
    assert api.delete(f"/resumes/{resume_id}").status_code == 204
    assert api.get("/resumes").json() == []
    assert api.get(f"/resumes/{resume_id}").status_code == 404


def test_a_user_cannot_read_another_users_resume(api, registered, resume_bytes):
    resume_id = upload(api, resume_bytes).json()["id"]
    api.post("/auth/logout")
    second = api.post(
        "/auth/register", json={"email": "second@example.com", "password": "Str0ngPassword!"}
    )
    api.set_csrf(second.json()["csrf_token"])
    assert api.get(f"/resumes/{resume_id}").status_code == 404
    assert api.get(f"/resumes/{resume_id}/file").status_code == 404


def test_download_of_a_pasted_resume_reports_no_file(api, registered, resume_bytes):
    created = api.post(
        "/resumes/text", json={"title": "Pasted", "content": resume_bytes.decode()}
    ).json()
    response = api.get(f"/resumes/{created['id']}/download")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "no_original_file"
