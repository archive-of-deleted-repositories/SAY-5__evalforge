"""Prometheus metrics. Kept in one place so tests can reset between runs."""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

# Use a custom registry so tests don't collide with the global default.
REGISTRY = CollectorRegistry()

REQUESTS_TOTAL = Counter(
    "evalforge_requests_total",
    "Total /v1/evaluate requests",
    labelnames=("status",),
    registry=REGISTRY,
)

SCORE_TOTAL = Counter(
    "evalforge_score_total",
    "Total scoring runs per axis",
    labelnames=("axis", "flagged"),
    registry=REGISTRY,
)

FLAGGED_TOTAL = Counter(
    "evalforge_flagged_total",
    "Total flagged checks",
    registry=REGISTRY,
)

EVALUATE_LATENCY_MS = Histogram(
    "evalforge_evaluate_latency_ms",
    "End-to-end /v1/evaluate latency in milliseconds",
    buckets=(1, 5, 10, 25, 50, 100, 200, 500, 1000, 2000),
    registry=REGISTRY,
)

AXIS_LATENCY_MS = Histogram(
    "evalforge_axis_latency_ms",
    "Per-axis scorer latency in milliseconds",
    labelnames=("axis",),
    buckets=(0.1, 0.5, 1, 5, 10, 25, 50, 100),
    registry=REGISTRY,
)

QUEUE_DEPTH = Gauge(
    "evalforge_queue_depth",
    "Pending write jobs in the in-process queue",
    registry=REGISTRY,
)
