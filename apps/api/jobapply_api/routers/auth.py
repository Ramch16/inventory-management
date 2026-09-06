"""Authentication endpoints."""

from __future__ import annotations

import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import RedirectResponse
from jobapply_shared.errors import ValidationError_

from jobapply_api.cookies import clear_session_cookies, set_session_cookies
from jobapply_api.deps import (
    AuthServiceDep,
    CurrentUser,
    RequestMeta,
    SessionDep,
    SettingsDep,
    auth_rate_limit,
)
from jobapply_api.schemas.auth import (
    AccountDeleteRequest,
    EmailRequest,
    LoginRequest,
    OAuthAuthorizeResponse,
    PasswordChangeRequest,
    PasswordResetRequest,
    RegisterRequest,
    SessionResponse,
    TokenConfirmRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])

OAUTH_STATE_COOKIE = "ja_oauth_state"


def _session_response(
    response: Response, auth: AuthServiceDep, settings: SettingsDep, user
) -> SessionResponse:
    tokens = auth.issue_session(user)
    set_session_cookies(response, tokens, settings)
    return SessionResponse(user=UserResponse.model_validate(user), csrf_token=tokens.csrf_token)


@router.post(
    "/register",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(auth_rate_limit)],
)
def register(
    payload: RegisterRequest,
    response: Response,
    db: SessionDep,
    auth: AuthServiceDep,
    settings: SettingsDep,
    meta: RequestMeta,
) -> SessionResponse:
    user = auth.register(payload, request_meta=meta)
    db.commit()
    db.refresh(user)
    return _session_response(response, auth, settings, user)


@router.post("/login", response_model=SessionResponse, dependencies=[Depends(auth_rate_limit)])
def login(
    payload: LoginRequest,
    response: Response,
    db: SessionDep,
    auth: AuthServiceDep,
    settings: SettingsDep,
    meta: RequestMeta,
) -> SessionResponse:
    from jobapply_api.services import audit

    user = auth.authenticate(payload.email, payload.password)
    audit.record(
        db,
        action="auth.login",
        actor_user_id=user.id,
        entity_type="user",
        entity_id=user.id,
        **meta,
    )
    db.commit()
    db.refresh(user)
    return _session_response(response, auth, settings, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, settings: SettingsDep) -> Response:
    clear_session_cookies(response, settings)
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=dict(response.headers))


@router.post("/refresh", response_model=SessionResponse)
def refresh(
    request: Request,
    response: Response,
    db: SessionDep,
    auth: AuthServiceDep,
    settings: SettingsDep,
) -> SessionResponse:
    token = request.cookies.get(settings.refresh_cookie_name) or ""
    if not token:
        raise ValidationError_("No refresh token was supplied.", code="refresh_missing")
    user, tokens = auth.refresh_session(token)
    db.commit()
    set_session_cookies(response, tokens, settings)
    return SessionResponse(user=UserResponse.model_validate(user), csrf_token=tokens.csrf_token)


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.post("/verify-email/request", status_code=status.HTTP_202_ACCEPTED)
def request_verification(user: CurrentUser, db: SessionDep, auth: AuthServiceDep) -> dict:
    auth.send_verification_email(user)
    db.commit()
    return {"message": "If verification is still required, an e-mail is on its way."}


@router.post("/verify-email/confirm", response_model=UserResponse)
def confirm_verification(
    payload: TokenConfirmRequest, db: SessionDep, auth: AuthServiceDep
) -> UserResponse:
    user = auth.verify_email(payload.token)
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.post(
    "/password/forgot",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(auth_rate_limit)],
)
def forgot_password(payload: EmailRequest, db: SessionDep, auth: AuthServiceDep) -> dict:
    auth.request_password_reset(payload.email)
    db.commit()
    # Deliberately identical whether or not the address exists.
    return {"message": "If an account exists for that address, a reset link has been sent."}


@router.post(
    "/password/reset",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(auth_rate_limit)],
)
def reset_password(
    payload: PasswordResetRequest,
    response: Response,
    db: SessionDep,
    auth: AuthServiceDep,
    settings: SettingsDep,
) -> Response:
    auth.reset_password(payload.token, payload.password)
    db.commit()
    clear_session_cookies(response, settings)
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=dict(response.headers))


@router.post("/password/change", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChangeRequest,
    response: Response,
    user: CurrentUser,
    db: SessionDep,
    auth: AuthServiceDep,
    settings: SettingsDep,
) -> Response:
    auth.change_password(user, payload.current_password, payload.new_password)
    db.commit()
    clear_session_cookies(response, settings)
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=dict(response.headers))


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    payload: AccountDeleteRequest,
    response: Response,
    user: CurrentUser,
    db: SessionDep,
    auth: AuthServiceDep,
    settings: SettingsDep,
) -> Response:
    auth.delete_account(user, payload.password)
    db.commit()
    clear_session_cookies(response, settings)
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers=dict(response.headers))


# ------------------------------------------------------------------------- oauth
@router.get("/oauth/google/authorize", response_model=OAuthAuthorizeResponse)
def google_authorize(response: Response, settings: SettingsDep) -> OAuthAuthorizeResponse:
    if not settings.google_client_id:
        raise ValidationError_(
            "Google sign-in is not configured on this deployment.", code="oauth_not_configured"
        )
    state = secrets.token_urlsafe(24)
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return OAuthAuthorizeResponse(authorize_url=url, state=state)


@router.get("/oauth/google/callback")
async def google_callback(
    request: Request,
    db: SessionDep,
    auth: AuthServiceDep,
    settings: SettingsDep,
    code: str | None = None,
    state: str | None = None,
) -> RedirectResponse:
    expected_state = request.cookies.get(OAUTH_STATE_COOKIE)
    if not code or not state or not expected_state or state != expected_state:
        raise ValidationError_(
            "The sign-in attempt could not be verified.", code="oauth_state_mismatch"
        )
    if not settings.google_client_id or not settings.google_client_secret:
        raise ValidationError_(
            "Google sign-in is not configured on this deployment.", code="oauth_not_configured"
        )

    import httpx

    async with httpx.AsyncClient(timeout=15) as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_response.status_code != 200:
            raise ValidationError_("Google rejected the sign-in.", code="oauth_exchange_failed")
        access_token = token_response.json().get("access_token")
        profile_response = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if profile_response.status_code != 200:
            raise ValidationError_("Google profile lookup failed.", code="oauth_profile_failed")
        profile = profile_response.json()

    user = auth.upsert_oauth_user(
        provider="google",
        account_id=str(profile.get("sub")),
        email=profile.get("email"),
        email_verified=bool(profile.get("email_verified")),
    )
    db.commit()
    db.refresh(user)

    redirect = RedirectResponse(url=f"{settings.frontend_base_url}/dashboard", status_code=302)
    set_session_cookies(redirect, auth.issue_session(user), settings)
    redirect.delete_cookie(OAUTH_STATE_COOKIE, path="/")
    return redirect
