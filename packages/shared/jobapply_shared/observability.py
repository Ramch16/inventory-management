"""Optional error tracking and tracing.

Both are configured by environment variable and are no-ops when unset, so a
deployment without them behaves identically. Sensitive fields are scrubbed before
anything leaves the process.
"""

from __future__ import annotations

from typing import Any

from jobapply_shared.logging import get_logger, redact

logger = get_logger(__name__)


def init_sentry(dsn: str | None, environment: str, release: str | None = None) -> bool:
    if not dsn:
        return False
    try:
        import sentry_sdk
    except ImportError:
        logger.warning(
            "observability.sentry_unavailable",
            extra={"context": {"event": "observability.sentry_unavailable"}},
        )
        return False

    def scrub(event: dict[str, Any], _hint: dict[str, Any]) -> dict[str, Any]:
        """Nothing sensitive leaves the process, even in a crash report."""
        return redact(event)

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        before_send=scrub,
        send_default_pii=False,
        traces_sample_rate=0.1,
    )
    logger.info(
        "observability.sentry_enabled",
        extra={"context": {"event": "observability.sentry_enabled"}},
    )
    return True


def init_tracing(endpoint: str | None, service_name: str) -> bool:
    if not endpoint:
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning(
            "observability.otel_unavailable",
            extra={"context": {"event": "observability.otel_unavailable"}},
        )
        return False

    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    trace.set_tracer_provider(provider)
    logger.info(
        "observability.otel_enabled",
        extra={"context": {"event": "observability.otel_enabled"}},
    )
    return True
