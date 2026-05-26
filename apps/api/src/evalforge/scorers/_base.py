"""Scorer protocol shared by the three axes."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from evalforge.schemas import AxisScore


@runtime_checkable
class Scorer(Protocol):
    """Each axis implements this. Synchronous so the hot path stays simple."""

    def score(self, output_text: str, context: dict[str, Any]) -> AxisScore: ...
