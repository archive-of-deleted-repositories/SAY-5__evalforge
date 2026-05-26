"""Observability helpers: structured logs + Prometheus metrics."""

from evalforge.obs.logging_setup import get_logger, setup_logging
from evalforge.obs.metrics import (
    AXIS_LATENCY_MS,
    EVALUATE_LATENCY_MS,
    FLAGGED_TOTAL,
    QUEUE_DEPTH,
    REQUESTS_TOTAL,
    SCORE_TOTAL,
)

__all__ = [
    "setup_logging",
    "get_logger",
    "REQUESTS_TOTAL",
    "SCORE_TOTAL",
    "FLAGGED_TOTAL",
    "EVALUATE_LATENCY_MS",
    "AXIS_LATENCY_MS",
    "QUEUE_DEPTH",
]
