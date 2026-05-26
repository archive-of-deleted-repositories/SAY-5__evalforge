"""Deterministic FakeProvider for hermetic CI.

Scoring rules (kept deterministic so the same input always yields the same verdict):
  * If output_text contains any rubric keyword, it counts as on-rubric.
  * Score is the keyword-coverage ratio with a small length penalty for very short outputs.
  * Few-shot demonstrations marked as "not_flagged" relax the threshold proportionally.
"""

from __future__ import annotations

import os
import re
from collections.abc import Sequence

from evalforge.provider._base import JudgeProvider, JudgeVerdict

_KEYWORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}")


def _tokens(text: str) -> list[str]:
    return [m.group(0).lower() for m in _KEYWORD_RE.finditer(text)]


class FakeProvider:
    """Pure-Python judge that needs zero network and is fully deterministic."""

    def __init__(self, *, base_threshold: float = 0.4) -> None:
        self.base_threshold = base_threshold

    def judge(
        self,
        rubric: str,
        output_text: str,
        few_shot: Sequence[tuple[str, str]] = (),
    ) -> JudgeVerdict:
        rubric_tokens = set(_tokens(rubric))
        out_tokens = _tokens(output_text)

        if not rubric_tokens or not out_tokens:
            return JudgeVerdict(score=0.0, label="empty_input", reason="no tokens to compare")

        overlap = sum(1 for t in out_tokens if t in rubric_tokens)
        coverage = overlap / max(len(rubric_tokens), 1)
        length_penalty = 0.0 if len(out_tokens) >= 4 else 0.2 * (4 - len(out_tokens)) / 4
        score = max(0.0, min(1.0, coverage - length_penalty))

        # Few-shot demonstrations marked "not_flagged" relax the bar.
        relax = sum(1 for _, label in few_shot if label == "not_flagged") * 0.05
        threshold = max(0.0, self.base_threshold - relax)

        label = "on_rubric" if score >= threshold else "off_rubric"
        reason = f"coverage={coverage:.2f} threshold={threshold:.2f}"
        return JudgeVerdict(score=score, label=label, reason=reason)


def get_default_provider() -> JudgeProvider:
    name = os.environ.get("EVALFORGE_PROVIDER", "fake").lower()
    if name == "claude":
        from evalforge.provider.claude_stub import ClaudeProvider

        return ClaudeProvider()
    return FakeProvider()
