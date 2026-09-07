"""The vault stores secrets and refuses to give them back.

The point of these tests is the negative space: no route, no response model and no
audit entry ever carries the plaintext, and one user's ciphertext is useless to
another.
"""

from __future__ import annotations

import json

import pytest
from jobapply_db.models import AuditLog, Credential
from jobapply_shared.security import decrypt_blob
from sqlalchemy import select

SECRET = "correct horse battery staple"


def _create(api, **overrides):
    payload = {
        "label": "Workday — Acme",
        "kind": "password",
        "host": "https://acme.wd5.myworkdayjobs.com/careers",
        "username": "jordan@example.com",
        "secret": SECRET,
    }
    payload.update(overrides)
    return api.post("/credentials", json=payload)


def test_a_credential_is_stored_and_listed_without_its_secret(api, registered):
    created = _create(api)
    assert created.status_code == 201, created.text
    body = created.json()

    assert body["has_secret"] is True
    assert "secret" not in body
    assert SECRET not in json.dumps(body)
    #: The host is reduced to a bare hostname so one entry matches every URL form.
    assert body["host"] == "acme.wd5.myworkdayjobs.com"

    listed = api.get("/credentials").json()
    assert [item["id"] for item in listed] == [body["id"]]
    assert SECRET not in json.dumps(listed)


def test_the_secret_is_encrypted_at_rest(api, registered, db_session, settings):
    _create(api)
    credential = db_session.execute(select(Credential)).scalar_one()

    assert credential.secret_encrypted is not None
    assert SECRET not in credential.secret_encrypted
    assert credential.secret_encrypted.startswith("v1.")

    plaintext = decrypt_blob(
        credential.secret_encrypted,
        secret_key=settings.secret_key,
        context=f"vault:credential:{credential.user_id}",
    )
    assert plaintext.decode() == SECRET


def test_ciphertext_does_not_decrypt_for_another_user(api, registered, db_session, settings):
    """Binding the user into the AEAD's associated data makes a copied row useless."""
    import uuid

    _create(api)
    credential = db_session.execute(select(Credential)).scalar_one()

    with pytest.raises(Exception):
        decrypt_blob(
            credential.secret_encrypted,
            secret_key=settings.secret_key,
            context=f"vault:credential:{uuid.uuid4()}",
        )


def test_no_endpoint_returns_a_secret(app):
    paths = app.openapi()["paths"]
    for path, operations in paths.items():
        if "credential" not in path:
            continue
        for operation in operations.values():
            responses = json.dumps(operation.get("responses", {}))
            assert "secret" not in responses, f"{path} may expose a secret"


def test_the_audit_trail_records_the_event_but_not_the_secret(api, registered, db_session):
    _create(api)
    entries = db_session.execute(select(AuditLog)).scalars().all()
    actions = {entry.action for entry in entries}
    assert "credential.created" in actions

    dumped = json.dumps([entry.data for entry in entries])
    assert SECRET not in dumped
    assert "jordan@example.com" not in dumped


def test_a_password_credential_requires_a_secret(api, registered):
    response = _create(api, secret=None)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "secret_required"


def test_an_sso_credential_stores_no_secret_at_all(api, registered):
    """SSO is handled by the user during an intervention, so there is nothing to keep."""
    response = _create(api, kind="sso", secret=None, label="Acme SSO")
    assert response.status_code == 201
    assert response.json()["has_secret"] is False


def test_a_secret_can_be_rotated_without_being_read(api, registered, db_session, settings):
    created = _create(api).json()
    before = db_session.execute(select(Credential)).scalar_one().secret_encrypted

    updated = api.patch(f"/credentials/{created['id']}", json={"secret": "a new secret"})
    assert updated.status_code == 200
    assert "secret" not in updated.json()

    db_session.expire_all()
    credential = db_session.execute(select(Credential)).scalar_one()
    assert credential.secret_encrypted != before
    plaintext = decrypt_blob(
        credential.secret_encrypted,
        secret_key=settings.secret_key,
        context=f"vault:credential:{credential.user_id}",
    )
    assert plaintext.decode() == "a new secret"


def test_a_credential_can_be_deleted(api, registered, db_session):
    created = _create(api).json()
    assert api.delete(f"/credentials/{created['id']}").status_code == 204
    assert db_session.execute(select(Credential)).scalar_one_or_none() is None


def test_another_users_credential_is_not_reachable(api, registered):
    created = _create(api).json()

    second = api.post(
        "/auth/register", json={"email": "second@example.com", "password": "Str0ngPassword!"}
    )
    api.set_csrf(second.json()["csrf_token"])

    assert api.get("/credentials").json() == []
    assert api.patch(f"/credentials/{created['id']}", json={"label": "mine now"}).status_code == 404
    assert api.delete(f"/credentials/{created['id']}").status_code == 404


def test_the_worker_picks_the_credential_that_matches_the_site(
    api, registered, db_session, settings
):
    """Host matching covers subdomains, so one entry works for a company's careers site."""
    from jobapply_db.models import User
    from jobapply_workers.tasks.applications import _credential_for

    _create(api, host="acme.com")
    user = db_session.execute(select(User)).scalars().first()

    matched = _credential_for(db_session, user, "https://careers.acme.com/apply/123", settings)
    assert matched is not None
    assert matched.username == "jordan@example.com"
    assert matched.secret.get_secret_value() == SECRET
    assert SECRET not in repr(matched), "a secret must not survive a repr"

    assert _credential_for(db_session, user, "https://boards.other.com/apply", settings) is None
    assert _credential_for(db_session, user, "", settings) is None


def test_using_a_credential_is_recorded(api, registered, db_session, settings):
    from jobapply_db.models import User
    from jobapply_workers.tasks.applications import _credential_for

    _create(api, host="acme.com")
    user = db_session.execute(select(User)).scalars().first()
    _credential_for(db_session, user, "https://acme.com/apply", settings)
    db_session.commit()

    entries = db_session.execute(select(AuditLog).where(AuditLog.action == "credential.used"))
    used = entries.scalars().all()
    assert len(used) == 1
    assert SECRET not in json.dumps(used[0].data)

    credential = db_session.execute(select(Credential)).scalar_one()
    assert credential.last_used_at is not None
