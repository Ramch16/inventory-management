"""The parts of the running application that are easy to break and hard to notice.

Every case here corresponds to something that actually broke a first run of the
stack: a documentation page that rendered blank, and a development e-mail backend
that swallowed the only copy of a verification link.
"""

from __future__ import annotations

import re

from jobapply_shared.email import ConsoleEmailSender, EmailMessage


def test_the_api_forbids_everything_by_default(api, registered):
    """A JSON endpoint has nothing to load, so its policy stays absolute."""
    response = api.get("/dashboard")
    assert response.headers["content-security-policy"] == (
        "default-src 'none'; frame-ancestors 'none'"
    )


def test_the_docs_page_is_allowed_to_load_swagger_ui(client):
    """`default-src 'none'` on /docs renders a blank page: the browser refuses the
    stylesheet, the script and the inline bootstrap, and nothing says why."""
    response = client.get("/docs")
    assert response.status_code == 200

    policy = response.headers["content-security-policy"]
    assert "https://cdn.jsdelivr.net" in policy
    assert "script-src" in policy and "style-src" in policy
    # The relaxation is scoped: nothing may be fetched from anywhere else.
    assert policy.startswith("default-src 'none'")
    assert "frame-ancestors 'none'" in policy


def test_the_docs_page_explains_itself_when_swagger_cannot_be_fetched(client):
    body = client.get("/docs").text
    assert "swagger-ui-bundle.js" in body, "Swagger UI is still the primary path"
    assert "could not reach" in body, "a blocked CDN must not leave a blank page"
    assert "/openapi.json" in body


def test_the_console_email_backend_prints_the_body(capsys):
    """It stands in for an inbox. A verification link that is not shown anywhere
    cannot be followed, and the account can never be verified."""
    sender = ConsoleEmailSender()
    sender.send(
        EmailMessage(
            to="ram@example.com",
            subject="Confirm your e-mail",
            text_body="Open http://localhost:3000/verify-email?token=abc123 to confirm.",
        )
    )

    printed = capsys.readouterr().out
    assert "ram@example.com" in printed
    assert "Confirm your e-mail" in printed
    assert re.search(r"verify-email\?token=abc123", printed), "the link has to be reachable"
    assert sender.outbox[0].subject == "Confirm your e-mail"


def test_production_refuses_an_email_backend_that_delivers_nothing(monkeypatch):
    import pytest
    from jobapply_shared.settings import Settings

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "a" * 48)
    monkeypatch.setenv("COOKIE_SECURE", "true")
    monkeypatch.setenv("EMAIL_BACKEND", "console")

    with pytest.raises(ValueError, match="EMAIL_BACKEND"):
        Settings()

    monkeypatch.setenv("EMAIL_BACKEND", "smtp")
    assert Settings().email_backend == "smtp"
