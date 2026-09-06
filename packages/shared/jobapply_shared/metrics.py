"""Application metrics.

A small in-process registry with a Prometheus text exposition. It is deliberately
dependency-free so the API and the workers can record the same counters whether or not
a metrics stack is deployed; wiring a real Prometheus client later means replacing this
module, not the call sites.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

#: Buckets in seconds, chosen for the two things worth watching: AI calls (seconds)
#: and browser runs (tens of seconds).
DEFAULT_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120)


def _key(labels: dict[str, str] | None) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((labels or {}).items()))


@dataclass
class _Histogram:
    buckets: tuple[float, ...]
    counts: dict[float, int] = field(default_factory=dict)
    total: float = 0.0
    observations: int = 0

    def observe(self, value: float) -> None:
        self.total += value
        self.observations += 1
        # Count the observation in its own bucket only; ``render`` turns these into
        # the cumulative form Prometheus expects.
        for bound in self.buckets:
            if value <= bound:
                self.counts[bound] = self.counts.get(bound, 0) + 1
                break


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, dict[tuple, float]] = defaultdict(dict)
        self._gauges: dict[str, dict[tuple, float]] = defaultdict(dict)
        self._histograms: dict[str, dict[tuple, _Histogram]] = defaultdict(dict)
        self._help: dict[str, str] = {}

    def counter(
        self,
        name: str,
        *,
        description: str = "",
        labels: dict[str, str] | None = None,
        value: float = 1,
    ) -> None:
        with self._lock:
            self._help.setdefault(name, description)
            bucket = self._counters[name]
            key = _key(labels)
            bucket[key] = bucket.get(key, 0.0) + value

    def gauge(
        self,
        name: str,
        value: float,
        *,
        description: str = "",
        labels: dict[str, str] | None = None,
    ) -> None:
        with self._lock:
            self._help.setdefault(name, description)
            self._gauges[name][_key(labels)] = value

    def observe(
        self,
        name: str,
        value: float,
        *,
        description: str = "",
        labels: dict[str, str] | None = None,
        buckets: tuple[float, ...] = DEFAULT_BUCKETS,
    ) -> None:
        with self._lock:
            self._help.setdefault(name, description)
            key = _key(labels)
            histogram = self._histograms[name].get(key)
            if histogram is None:
                histogram = _Histogram(buckets=buckets)
                self._histograms[name][key] = histogram
            histogram.observe(value)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "counters": {
                    name: {str(dict(key)): value for key, value in series.items()}
                    for name, series in self._counters.items()
                },
                "gauges": {
                    name: {str(dict(key)): value for key, value in series.items()}
                    for name, series in self._gauges.items()
                },
            }

    def render(self) -> str:
        """Prometheus text exposition format."""
        lines: list[str] = []
        with self._lock:
            for name, series in self._counters.items():
                lines.append(f"# HELP {name} {self._help.get(name, '')}".rstrip())
                lines.append(f"# TYPE {name} counter")
                for key, value in series.items():
                    lines.append(f"{name}{_render_labels(key)} {value:g}")
            for name, gauges in self._gauges.items():
                lines.append(f"# HELP {name} {self._help.get(name, '')}".rstrip())
                lines.append(f"# TYPE {name} gauge")
                for key, value in gauges.items():
                    lines.append(f"{name}{_render_labels(key)} {value:g}")
            for name, histograms in self._histograms.items():
                lines.append(f"# HELP {name} {self._help.get(name, '')}".rstrip())
                lines.append(f"# TYPE {name} histogram")
                for key, histogram in histograms.items():
                    cumulative = 0
                    for bound in histogram.buckets:
                        cumulative += histogram.counts.get(bound, 0)
                        labels = _render_labels(key, extra={"le": str(bound)})
                        lines.append(f"{name}_bucket{labels} {cumulative}")
                    labels = _render_labels(key, extra={"le": "+Inf"})
                    lines.append(f"{name}_bucket{labels} {histogram.observations}")
                    lines.append(f"{name}_sum{_render_labels(key)} {histogram.total:g}")
                    lines.append(f"{name}_count{_render_labels(key)} {histogram.observations}")
        return "\n".join(lines) + "\n"

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()


def _render_labels(key: tuple, extra: dict[str, str] | None = None) -> str:
    labels = dict(key)
    labels.update(extra or {})
    if not labels:
        return ""
    rendered = ",".join(f'{name}="{value}"' for name, value in sorted(labels.items()))
    return "{" + rendered + "}"


REGISTRY = MetricsRegistry()


class timed:
    """Context manager recording how long a block took.

    Used for the two latencies worth alerting on — AI calls and browser runs.
    """

    def __init__(self, name: str, *, description: str = "", **labels: str) -> None:
        self.name = name
        self.description = description
        self.labels = labels
        self._started = 0.0

    def __enter__(self) -> timed:
        self._started = time.perf_counter()
        return self

    def __exit__(self, *exc_info) -> None:
        REGISTRY.observe(
            self.name,
            time.perf_counter() - self._started,
            description=self.description,
            labels={**self.labels, "outcome": "error" if exc_info[0] else "ok"},
        )


def record_ai_call(provider: str, model: str, latency_ms: int, tokens: int) -> None:
    REGISTRY.counter(
        "jobapply_ai_calls_total", description="AI provider calls", labels={"provider": provider}
    )
    REGISTRY.counter(
        "jobapply_ai_tokens_total",
        description="AI tokens consumed",
        labels={"provider": provider, "model": model},
        value=tokens,
    )
    REGISTRY.observe(
        "jobapply_ai_latency_seconds",
        latency_ms / 1000,
        description="AI provider latency",
        labels={"provider": provider},
    )


def record_application_run(ats: str, status: str, duration_ms: int) -> None:
    REGISTRY.counter(
        "jobapply_application_runs_total",
        description="Automation runs by outcome",
        labels={"ats": ats, "status": status},
    )
    REGISTRY.observe(
        "jobapply_application_run_seconds",
        duration_ms / 1000,
        description="Automation run duration",
        labels={"ats": ats},
    )


def record_intervention(kind: str) -> None:
    REGISTRY.counter(
        "jobapply_interventions_total",
        description="Runs paused for a person, by reason",
        labels={"type": kind},
    )
