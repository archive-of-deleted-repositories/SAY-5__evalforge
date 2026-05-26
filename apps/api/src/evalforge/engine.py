"""ScoringEngine fans a request out to the three axis scorers."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from evalforge.obs.metrics import AXIS_LATENCY_MS, FLAGGED_TOTAL, SCORE_TOTAL
from evalforge.schemas import AxisScore
from evalforge.scorers import ModerationScorer, QualityScorer, SafetyScorer


@dataclass(slots=True)
class EngineResult:
    axes: list[AxisScore]
    flagged: bool


class ScoringEngine:
    def __init__(
        self,
        *,
        quality: QualityScorer | None = None,
        safety: SafetyScorer | None = None,
        moderation: ModerationScorer | None = None,
    ) -> None:
        self.quality = quality or QualityScorer()
        self.safety = safety or SafetyScorer()
        self.moderation = moderation or ModerationScorer()

    def run(self, output_text: str, context: dict[str, Any]) -> EngineResult:
        axes: list[AxisScore] = []
        for scorer in (self.quality, self.safety, self.moderation):
            t0 = time.perf_counter()
            result = scorer.score(output_text, context)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            AXIS_LATENCY_MS.labels(axis=result.axis.value).observe(elapsed_ms)
            SCORE_TOTAL.labels(axis=result.axis.value, flagged=str(result.flagged).lower()).inc()
            axes.append(result)
        flagged = any(a.flagged for a in axes)
        if flagged:
            FLAGGED_TOTAL.inc()
        return EngineResult(axes=axes, flagged=flagged)
