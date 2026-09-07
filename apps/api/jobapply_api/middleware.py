"""Cross-cutting HTTP middleware: request ids, access logs and security headers."""

from __future__ import annotations

import time
import uuid

from jobapply_shared.logging import get_logger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = get_logger("jobapply.http")

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request id, time the request, and log it as one structured line."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = int((time.perf_counter() - started) * 1000)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "http.request",
            extra={
                "context": {
                    "event": "http.request",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                }
            },
        )
        return response


#: Swagger UI is loaded from here by the pages FastAPI generates.
SWAGGER_CDN = "https://cdn.jsdelivr.net"

#: The only paths that serve HTML rather than JSON. Disabled in production.
DOCS_PATHS = frozenset({"/docs", "/docs/oauth2-redirect", "/redoc"})


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, hsts: bool = False) -> None:
        super().__init__(app)
        self.hsts = hsts

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        if self.hsts:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        response.headers.setdefault("Content-Security-Policy", self._policy_for(request.url.path))
        return response

    @staticmethod
    def _policy_for(path: str) -> str:
        """`default-src 'none'` for the API; enough for Swagger UI on the docs pages.

        The API otherwise serves JSON only, so a policy that forbids everything costs
        nothing and stops any attempt to render a response as a document. The two
        interactive documentation pages are the exception: they are HTML that loads
        Swagger UI, and under the blanket policy the browser refuses every asset and
        renders a blank page. They are served only outside production.
        """
        if path in DOCS_PATHS:
            return (
                "default-src 'none'; "
                f"script-src 'self' 'unsafe-inline' {SWAGGER_CDN}; "
                f"style-src 'self' 'unsafe-inline' {SWAGGER_CDN}; "
                f"img-src 'self' data: {SWAGGER_CDN} https://fastapi.tiangolo.com; "
                f"font-src 'self' {SWAGGER_CDN}; "
                "connect-src 'self'; "
                "frame-ancestors 'none'"
            )
        return "default-src 'none'; frame-ancestors 'none'"
