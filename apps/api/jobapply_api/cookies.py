"""Session cookie handling.

Tokens live in ``HttpOnly`` cookies so page JavaScript cannot read them; the CSRF
token is deliberately readable so the frontend can echo it in a header (double-submit).
"""

from __future__ import annotations

from fastapi import Response
from jobapply_shared.settings import Settings

from jobapply_api.services.auth_service import SessionTokens


def set_session_cookies(response: Response, tokens: SessionTokens, settings: Settings) -> None:
    common = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": "lax",
        "domain": settings.cookie_domain,
    }
    response.set_cookie(
        settings.access_cookie_name,
        tokens.access.token,
        max_age=settings.access_token_ttl_seconds,
        path="/",
        **common,
    )
    response.set_cookie(
        settings.refresh_cookie_name,
        tokens.refresh.token,
        max_age=settings.refresh_token_ttl_seconds,
        path=f"{settings.api_v1_prefix}/auth",
        **common,
    )
    # Readable by the frontend on purpose: it must be echoed in the CSRF header.
    response.set_cookie(
        settings.csrf_cookie_name,
        tokens.csrf_token,
        max_age=settings.refresh_token_ttl_seconds,
        path="/",
        httponly=False,
        secure=settings.cookie_secure,
        samesite="lax",
        domain=settings.cookie_domain,
    )


def clear_session_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(settings.access_cookie_name, path="/", domain=settings.cookie_domain)
    response.delete_cookie(
        settings.refresh_cookie_name,
        path=f"{settings.api_v1_prefix}/auth",
        domain=settings.cookie_domain,
    )
    response.delete_cookie(settings.csrf_cookie_name, path="/", domain=settings.cookie_domain)
