"""Metrics exposition and the observability seams."""

from __future__ import annotations

import pytest
from jobapply_shared.metrics import (
    MetricsRegistry,
    record_ai_call,
    record_application_run,
    record_intervention,
    timed,
)


@pytest.fixture
def registry() -> MetricsRegistry:
    return MetricsRegistry()


def test_counters_accumulate_per_label_set(registry):
    registry.counter("runs_total", labels={"ats": "greenhouse"})
    registry.counter("runs_total", labels={"ats": "greenhouse"})
    registry.counter("runs_total", labels={"ats": "lever"})
    rendered = registry.render()
    assert 'runs_total{ats="greenhouse"} 2' in rendered
    assert 'runs_total{ats="lever"} 1' in rendered


def test_histograms_expose_cumulative_buckets(registry):
    for value in (0.05, 0.4, 3.0):
        registry.observe("latency_seconds", value, buckets=(0.1, 1, 10))
    rendered = registry.render()
    assert 'latency_seconds_bucket{le="0.1"} 1' in rendered
    assert 'latency_seconds_bucket{le="1"} 2' in rendered
    assert 'latency_seconds_bucket{le="10"} 3' in rendered
    assert "latency_seconds_count 3" in rendered


def test_gauges_replace_rather_than_accumulate(registry):
    registry.gauge("queue_depth", 5)
    registry.gauge("queue_depth", 2)
    assert "queue_depth 2" in registry.render()


def test_the_timer_records_the_outcome():
    from jobapply_shared.metrics import REGISTRY

    REGISTRY.reset()
    with timed("block_seconds"):
        pass
    with pytest.raises(ValueError, match="boom"), timed("block_seconds"):
        raise ValueError("boom")

    rendered = REGISTRY.render()
    assert 'outcome="ok"' in rendered
    assert 'outcome="error"' in rendered


def test_the_platform_records_the_things_worth_alerting_on():
    from jobapply_shared.metrics import REGISTRY

    REGISTRY.reset()
    record_ai_call("mock", "mock-1", 120, 450)
    record_application_run("greenhouse", "SUBMITTED", 18_400)
    record_intervention("captcha")

    rendered = REGISTRY.render()
    assert 'jobapply_ai_calls_total{provider="mock"} 1' in rendered
    assert 'jobapply_ai_tokens_total{model="mock-1",provider="mock"} 450' in rendered
    assert 'jobapply_application_runs_total{ats="greenhouse",status="SUBMITTED"} 1' in rendered
    assert 'jobapply_interventions_total{type="captcha"} 1' in rendered


def test_metrics_never_carry_user_data():
    """Label values are dimensions, not identities."""
    from jobapply_shared.metrics import REGISTRY

    REGISTRY.reset()
    record_application_run("greenhouse", "SUBMITTED", 100)
    rendered = REGISTRY.render()
    assert "@" not in rendered, "no e-mail addresses"
    assert "user_id" not in rendered


def test_observability_is_a_no_op_when_unconfigured():
    from jobapply_shared.observability import init_sentry, init_tracing

    assert init_sentry(None, "test") is False
    assert init_tracing(None, "jobapply") is False
