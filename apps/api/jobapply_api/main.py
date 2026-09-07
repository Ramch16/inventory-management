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


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()
    configure_logging(config.log_level, config.log_format)

    app = FastAPI(
        title=config.app_name,
        description=DESCRIPTION,
        version="0.1.0",
        docs_url="/docs" if not config.is_production else None,
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
