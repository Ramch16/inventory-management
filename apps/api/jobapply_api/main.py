"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from jobapply_shared.logging import configure_logging, get_logger
from jobapply_shared.settings import Settings, get_settings

from jobapply_api.errors import register_error_handlers
from jobapply_api.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from jobapply_api.routers import (
    admin,
    applications,
    auth,
    billing,
    credentials,
    dashboard,
    health,
    jobs,
    profile,
    resumes,
)

DESCRIPTION = """
Job application automation with a human in the loop.

The platform discovers jobs, scores them against a profile, tailors a resume from
records the user has approved, fills supported application forms and submits only when
no human verification is required. CAPTCHA, MFA/OTP, legal attestations, ambiguous
questions and unsupported flows pause the run and hand control back to the user.
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    logger = get_logger(__name__)
    logger.info(
        "api.startup",
        extra={
            "context": {
                "event": "api.startup",
                "environment": settings.environment,
                "ai_provider": settings.ai_provider,
                "storage_backend": settings.storage_backend,
            }
        },
    )
    yield
    logger.info("api.shutdown", extra={"context": {"event": "api.shutdown"}})


#: Shown when Swagger UI itself cannot be fetched — an offline machine, a blocked
#: CDN, a corporate proxy. Without it the page is simply blank, which says nothing.
DOCS_FALLBACK = """
<script>
window.addEventListener('load', function () {
  if (window.SwaggerUIBundle) return;
  document.getElementById('swagger-ui').innerHTML =
    '<div style="font:14px/1.6 system-ui,sans-serif;max-width:44rem;margin:3rem auto;' +
    'padding:0 1.5rem;color:#111">' +
    '<h1 style="font-size:1.25rem">The API is running; its documentation viewer is not</h1>' +
    '<p>Swagger UI is loaded from <code>cdn.jsdelivr.net</code>, which this ' +
    'browser could not reach. Nothing is wrong with the API itself.</p>' +
    '<p>The full specification is still available as JSON at ' +
    '<a href="/openapi.json">/openapi.json</a>, and every endpoint works normally.</p>' +
    '</div>';
});
</script>
"""


def _mount_docs(app: FastAPI) -> None:
    """Serve Swagger UI, and say something useful when it cannot be loaded."""
    from fastapi.openapi.docs import get_swagger_ui_html
    from fastapi.responses import HTMLResponse

    @app.get("/docs", include_in_schema=False)
    def swagger_ui() -> HTMLResponse:
        page = get_swagger_ui_html(openapi_url="/openapi.json", title=f"{app.title} — API")
        body = page.body.decode("utf-8").replace("</body>", f"{DOCS_FALLBACK}</body>")
        return HTMLResponse(body)


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()
    configure_logging(config.log_level, config.log_format)

    app = FastAPI(
        title=config.app_name,
        description=DESCRIPTION,
        version="0.1.0",
        # /docs is served by _mount_docs below, which adds a fallback for the case
        # where Swagger UI cannot be fetched.
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json" if not config.is_production else None,
        lifespan=lifespan,
    )
    app.state.settings = config

    app.add_middleware(SecurityHeadersMiddleware, hsts=config.is_production)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", config.csrf_header_name, "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    register_error_handlers(app)
    if not config.is_production:
        _mount_docs(app)

    prefix = config.api_v1_prefix
    app.include_router(health.router)
    app.include_router(health.router, prefix=prefix)
    app.include_router(auth.router, prefix=prefix)
    app.include_router(profile.router, prefix=prefix)
    app.include_router(resumes.router, prefix=prefix)
    app.include_router(resumes.versions_router, prefix=prefix)
    app.include_router(jobs.router, prefix=prefix)
    app.include_router(applications.router, prefix=prefix)
    app.include_router(billing.router, prefix=prefix)
    app.include_router(credentials.router, prefix=prefix)
    app.include_router(admin.router, prefix=prefix)
    app.include_router(dashboard.router, prefix=prefix)
    return app


app = create_app()
