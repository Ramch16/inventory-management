"""Dashboard counters, readiness and notifications."""

from __future__ import annotations

import io
from pathlib import Path

FIXTURE = Path(__file__).parent.parent / "fixtures" / "resumes" / "sample_resume.txt"


def test_dashboard_starts_empty_but_reports_blockers(api, registered):
    response = api.get("/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["counters"]["applications_total"] == 0
    assert body["counters"]["automation_success_rate"] == 0.0
    assert body["readiness"]["automation_enabled"] is False
    assert body["readiness"]["automation_paused"] is True
    assert body["readiness"]["has_master_resume"] is False
    assert any("master resume" in item.lower() for item in body["readiness"]["blockers"])
    assert body["attention_required"] == []


def test_readiness_updates_once_a_resume_exists(api, registered):
    api.post(
        "/resumes/upload",
        files={"file": ("resume.txt", io.BytesIO(FIXTURE.read_bytes()), "text/plain")},
    )
    readiness = api.get("/dashboard").json()["readiness"]
    assert readiness["has_master_resume"] is True
    assert not any("master resume" in item.lower() for item in readiness["blockers"])


def test_analytics_summary_matches_the_dashboard_counters(api, registered):
    assert api.get("/analytics/summary").json() == api.get("/dashboard").json()["counters"]


def test_welcome_notification_is_created_on_registration(api, registered):
    notifications = api.get("/notifications").json()
    assert any(item["kind"] == "welcome" for item in notifications)
    assert api.get("/notifications/unread-count").json()["count"] >= 1


def test_notifications_can_be_marked_read(api, registered):
    notification_id = api.get("/notifications").json()[0]["id"]
    assert api.post(f"/notifications/{notification_id}/read").status_code == 204
    assert api.get("/notifications").json()[0]["read_at"] is not None

    api.post("/notifications/read-all")
    assert api.get("/notifications/unread-count").json()["count"] == 0


def test_a_user_only_sees_their_own_notifications(api, registered):
    api.post("/auth/logout")
    second = api.post(
        "/auth/register", json={"email": "second@example.com", "password": "Str0ngPassword!"}
    )
    api.set_csrf(second.json()["csrf_token"])
    notifications = api.get("/notifications").json()
    assert len(notifications) == 1, "only the second account's own welcome notification"


def test_dashboard_requires_authentication(api):
    assert api.get("/dashboard").status_code == 401


def test_health_endpoints(api):
    assert api.raw.get("/health").json()["status"] == "ok"
    ready = api.raw.get("/health/ready")
    body = ready.json()
    assert body["checks"]["database"]["ok"] is True
    assert body["checks"]["storage"]["ok"] is True


def test_metrics_are_exposed_in_prometheus_format(api):
    response = api.raw.get("/api/v1/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "# TYPE" in response.text


def test_readiness_reports_worker_health(api):
    checks = api.raw.get("/health/ready").json()["checks"]
    assert "workers" in checks
    # No worker is running in the test process, so this must say so rather than
    # quietly reporting a healthy deployment.
    assert checks["workers"]["ok"] is False
