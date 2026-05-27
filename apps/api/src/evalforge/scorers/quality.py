"""Quality scorer: LLM-as-judge against a per-task rubric.

Uses the JudgeProvider seam, so CI is hermetic via FakeProvider.
"""

from __future__ import annotations

from typing import Any

from evalforge.provider import JudgeProvider, get_default_provider
from evalforge.schemas import Axis, AxisScore, Contribution

DEFAULT_RUBRIC = (
    "The output should be helpful, factually grounded, and respond to the prompt. "
    "It should avoid speculation and stick to verifiable claims."
)


class QualityScorer:
    axis = Axis.QUALITY

    def __init__(
        self,
        provider: JudgeProvider | None = None,
        threshold: float = 0.4,
        few_shot_examples: list[tuple[str, str]] | None = None,
    ) -> None:
        self.provider = provider or get_default_provider()
        self.threshold = threshold
        self.few_shot_examples = few_shot_examples or []

    def score(self, output_text: str, context: dict[str, Any]) -> AxisScore:
        rubric = context.get("rubric", DEFAULT_RUBRIC)
        verdict = self.provider.judge(rubric, output_text, self.few_shot_examples)
        # The provider's label already accounts for any few-shot threshold relaxation,
        # so it is authoritative for the flag. Fall back to the local threshold only
        # when the provider does not emit a recognized on/off-rubric label.
        if verdict.label == "on_rubric":
            flagged = False
        elif verdict.label == "off_rubric":
            flagged = True
        else:
            flagged = verdict.score < self.threshold

        # Quality contributions: rubric tokens present in the output.
        contributions: list[Contribution] = []
        out_lower = output_text.lower()
        seen: set[str] = set()
        for word in rubric.split():
            token = "".join(ch for ch in word.lower() if ch.isalnum())
            if len(token) < 4 or token in seen:
                continue
            idx = out_lower.find(token)
            if idx >= 0:
                contributions.append(
                    Contribution(
                        feature=f"rubric:{token}",
                        weight=0.1,
                        snippet=output_text[idx : idx + len(token)],
                        offset=idx,
                        length=len(token),
                    )
                )
                seen.add(token)

        reasons = [verdict.reason] if flagged else []
        return AxisScore(
            axis=self.axis,
            score=float(verdict.score),
            label=verdict.label,
            flagged=flagged,
            reasons=reasons,
            contributions=contributions,
        )
