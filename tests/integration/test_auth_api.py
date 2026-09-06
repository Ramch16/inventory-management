"""Authentication endpoints end to end."""

from __future__ import annotations

import pytest
from jobapply_db.models import AuditLog, AutomationSettings, Profile, Subscription, User
from sqlalchemy import select

from tests.conftest import DEFAULT_PASSWORD


def test_register_creates_the_full_account_shape(api, db_session):
    response = api.post(
        "/auth/register",
        json={
            "email": "New.User@Example.com",
            "password": DEFAULT_PASSWORD,
            "first_name": "New",
            "last_name": "User",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "new.user@example.com", "e-mail is normalized"
    assert body["user"]["automation_paused"] is True, "automation starts paused"
    assert body["csrf_token"]

    user = db_session.execute(select(User)).scalar_one()
    assert user.password_hash and DEFAULT_PASSWORD not in user.password_hash
    assert db_session.execute(select(Profile)).scalar_one().user_id == user.id
    assert db_session.execute(select(AutomationSettings)).scalar_one().enabled is False
    assert db_session.execute(select(Subscription)).scalar_one().plan == "free"


def test_register_sets_httponly_session_cookies(api, settings):
    api.post("/auth/register", json={"email": "a@example.com", "password": DEFAULT_PASSWORD})
    jar = api.raw.cookies
    assert settings.access_cookie_name in jar
    assert settings.csrf_cookie_name in jar


def test_password_is_never_returned(api):
    response = api.post(
        "/auth/register", json={"email": "a@example.com", "password": DEFAULT_PASSWORD}
    )
    assert "password" not in response.text.lower()


def test_duplicate_registration_is_rejected(api, registered):
    response = api.post(
        "/auth/register", json={"email": "jordan@example.com", "password": DEFAULT_PASSWORD}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


@pytest.mark.parametrize("password", ["short1A", "alllowercase123", "NODIGITSHERE"])
def test_weak_passwords_are_refused(api, password):
    response = api.post("/auth/register", json={"email": "weak@example.com", "password": password})
    assert response.status_code == 422


def test_login_and_me(api, registered):
    api.post("/auth/logout")
    response = api.post(
        "/auth/login", json={"email": "jordan@example.com", "password": DEFAULT_PASSWORD}
    )
    assert response.status_code == 200
    api.set_csrf(response.json()["csrf_token"])
    assert api.get("/auth/me").json()["email"] == "jordan@example.com"


def test_login_with_a_wrong_password_is_generic(api, registered):
    response = api.post(
        "/auth/login", json={"email": "jordan@example.com", "password": "Wrong123!"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_for_an_unknown_account_gives_the_same_error(api):
    response = api.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "Wrong123!"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_me_requires_authentication(api):
    assert api.get("/auth/me").status_code == 401


def test_unsafe_requests_require_the_csrf_header(api, registered):
    api.raw.headers.pop("X-CSRF-Token", None)
    response = api.put("/profile", json={"first_name": "Nope"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_a_mismatched_csrf_header_is_rejected(api, registered):
    api.set_csrf("not-the-right-token")
    response = api.put("/profile", json={"first_name": "Nope"})
    assert response.status_code == 403


def test_safe_requests_do_not_need_the_csrf_header(api, registered):
    api.raw.headers.pop("X-CSRF-Token", None)
    assert api.get("/profile").status_code == 200


def test_refresh_rotates_the_session(api, registered):
    response = api.post("/auth/refresh")
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "jordan@example.com"


def test_password_change_revokes_existing_sessions(api, registered):
    response = api.post(
        "/auth/password/change",
        json={"current_password": DEFAULT_PASSWORD, "new_password": "An0therStrongPass!"},
    )
    assert response.status_code == 204
    # The old access cookie was cleared and its epoch is now stale.
    assert api.get("/auth/me").status_code == 401
    login = api.post(
        "/auth/login", json={"email": "jordan@example.com", "password": "An0therStrongPass!"}
    )
    assert login.status_code == 200


def test_password_change_requires_the_current_password(api, registered):
    response = api.post(
        "/auth/password/change",
        json={"current_password": "WrongPassword1", "new_password": "An0therStrongPass!"},
    )
    assert response.status_code == 401


def test_forgot_password_never_reveals_whether_an_account_exists(api, registered):
    known = api.post("/auth/password/forgot", json={"email": "jordan@example.com"})
    unknown = api.post("/auth/password/forgot", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()


def test_password_reset_flow(api, registered, db_session, app):
    from jobapply_api.deps import _email_sender

    api.post("/auth/password/forgot", json={"email": "jordan@example.com"})
    outbox = _email_sender().outbox
    reset_message = [item for item in outbox if "reset" in item.subject.lower()][-1]
    token = reset_message.text_body.split("token=")[1].split()[0]

    response = api.post("/auth/password/reset", json={"token": token, "password": "R3setPassword!"})
    assert response.status_code == 204

    replay = api.post("/auth/password/reset", json={"token": token, "password": "Another1Pass!"})
    assert replay.status_code == 422, "a reset token is single use"

    assert (
        api.post(
            "/auth/login", json={"email": "jordan@example.com", "password": "R3setPassword!"}
        ).status_code
        == 200
    )


def test_email_verification_flow(api, registered, db_session):
    from jobapply_api.deps import _email_sender

    message = [item for item in _email_sender().outbox if "Confirm" in item.subject][-1]
    token = message.text_body.split("token=")[1].split()[0]
    response = api.post("/auth/verify-email/confirm", json={"token": token})
    assert response.status_code == 200
    assert response.json()["email_verified_at"] is not None


def test_invalid_verification_token_is_rejected(api, registered):
    response = api.post("/auth/verify-email/confirm", json={"token": "a" * 40})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "token_invalid"


def test_account_deletion_requires_confirmation_and_password(api, registered):
    assert api.delete("/auth/account", json={"confirmation": "yes"}).status_code == 422
    assert (
        api.delete(
            "/auth/account", json={"confirmation": "DELETE", "password": "Wrong1Pass"}
        ).status_code
        == 401
    )
    response = api.delete(
        "/auth/account", json={"confirmation": "DELETE", "password": DEFAULT_PASSWORD}
    )
    assert response.status_code == 204
    assert api.get("/auth/me").status_code == 401
    assert (
        api.post(
            "/auth/login", json={"email": "jordan@example.com", "password": DEFAULT_PASSWORD}
        ).status_code
        == 401
    )


def test_security_events_are_audited(api, registered, db_session):
    api.post("/auth/logout")
    api.post("/auth/login", json={"email": "jordan@example.com", "password": DEFAULT_PASSWORD})
    actions = {row.action for row in db_session.execute(select(AuditLog)).scalars()}
    assert {"auth.register", "auth.login"} <= actions


def test_google_oauth_is_disabled_without_configuration(api):
    response = api.get("/auth/oauth/google/authorize")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "oauth_not_configured"


def test_security_headers_are_present(api):
    response = api.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "X-Request-ID" in response.headers
