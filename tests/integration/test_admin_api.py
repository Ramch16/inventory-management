"""Admin endpoints: aggregates and diagnostics, never secrets."""

from __future__ import annotations

import pytest
from jobapply_db.models import User
from sqlalchemy import select


@pytest.fixture
def admin(api, registered, db_session):
    user = db_session.execute(select(User)).scalar_one()
    user.role = "admin"
    db_session.commit()
    return registered


def test_admin_endpoints_are_refused_to_ordinary_users(api, registered):
    for path in ["/admin/overview", "/admin/users", "/admin/errors", "/admin/usage"]:
        response = api.get(path)
        assert response.status_code == 403, path
        assert response.json()["error"]["code"] == "admin_required"


def test_admin_endpoints_require_authentication(api):
    assert api.get("/admin/overview").status_code == 401


def test_the_overview_reports_platform_aggregates(api, admin):
    api.post("/jobs/search", json={})
    overview = api.get("/admin/overview").json()
    assert overview["users"] == 1
    assert overview["jobs"] == 3
    assert overview["applications"] == 0
    assert overview["open_interventions"] == 0


def test_adapter_health_lists_every_adapter(api, admin):
    adapters = {item["ats"] for item in api.get("/admin/overview").json()["adapters"]}
    assert {
        "greenhouse",
        "lever",
        "ashby",
        "workday",
        "icims",
        "smartrecruiters",
        "generic",
    } <= adapters


def test_the_user_list_never_exposes_secrets(api, admin):
    response = api.get("/admin/users")
    assert response.status_code == 200
    body = response.text.lower()
    for forbidden in ("password", "token", "secret", "hash", "state_blob"):
        assert forbidden not in body

    user = response.json()[0]
    assert user["email"] == "jordan@example.com"
    assert user["automation_paused"] is True


def test_an_admin_can_disable_an_account_and_it_pauses_automation(api, admin, db_session):
    user_id = api.get("/admin/users").json()[0]["id"]
    response = api.post(f"/admin/users/{user_id}/disable")
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert response.json()["automation_paused"] is True

    # The disabled account can no longer use its session.
    assert api.get("/auth/me").status_code == 401


def test_sources_can_be_toggled_when_one_misbehaves(api, admin):
    api.get("/job-sources")
    sources = {item["slug"]: item for item in api.get("/admin/sources").json()}
    assert sources["sample"]["enabled"] is True

    assert api.post("/admin/sources/sample", json={"enabled": False}).json()["enabled"] is False
    after = {item["slug"]: item for item in api.get("/admin/sources").json()}
    assert after["sample"]["enabled"] is False

    # With every source off, a search says so rather than silently returning nothing.
    response = api.post("/jobs/search", json={})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "no_sources_enabled"


def test_toggling_an_unknown_source_is_a_404(api, admin):
    assert api.post("/admin/sources/nope", json={"enabled": True}).status_code == 404


def test_usage_reports_plan_distribution(api, admin):
    api.get("/billing")
    usage = api.get("/admin/usage").json()
    assert usage["plans"]["free"] == 1


def test_admin_actions_are_audited(api, admin, db_session):
    from jobapply_db.models import AuditLog

    user_id = api.get("/admin/users").json()[0]["id"]
    api.post(f"/admin/users/{user_id}/disable")
    actions = {row.action for row in db_session.execute(select(AuditLog)).scalars()}
    assert "admin.user_disabled" in actions
