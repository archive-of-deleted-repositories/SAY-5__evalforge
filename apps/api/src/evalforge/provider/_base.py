"""Judge provider interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class JudgeVerdict:
    score: float
    label: str
    reason: str


class JudgeProvider(Protocol):
    def judge(
        self, rubric: str, output_text: str, few_shot: list[tuple[str, str]] = ...
    ) -> JudgeVerdict: ...
