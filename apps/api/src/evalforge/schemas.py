"""Pydantic schemas for the public API surface."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Axis(StrEnum):
    QUALITY = "quality"
    SAFETY = "safety"
    MODERATION = "moderation"


class ReviewLabel(StrEnum):
    UNREVIEWED = "unreviewed"
    CORRECT = "correct"
    FALSE_POSITIVE = "false_positive"
    FALSE_NEGATIVE = "false_negative"


class Contribution(BaseModel):
    """A single feature that contributed to an axis score."""

    model_config = ConfigDict(frozen=True)

    feature: str
    weight: float = Field(ge=-1.0, le=1.0)
    snippet: str
    offset: int = Field(ge=0)
    length: int = Field(ge=0)


class AxisScore(BaseModel):
    model_config = ConfigDict(frozen=True)

    axis: Axis
    score: float = Field(ge=0.0, le=1.0)
    label: str
    flagged: bool
    reasons: list[str] = Field(default_factory=list)
    contributions: list[Contribution] = Field(default_factory=list)


class ScoreRequest(BaseModel):
    prompt_version: str = Field(min_length=1, max_length=64)
    output_text: str = Field(min_length=1, max_length=32_768)
    context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("context")
    @classmethod
    def validate_rubric(cls, context: dict[str, Any]) -> dict[str, Any]:
        if "rubric" in context:
            rubric = context["rubric"]
            if not isinstance(rubric, str) or not rubric.strip() or len(rubric) > 16_384:
                raise ValueError("context.rubric must be nonempty text of at most 16384 characters")
        return context


class ScoreResponse(BaseModel):
    check_id: UUID
    flagged: bool
    axes: list[AxisScore]
    latency_ms: float


class CheckRecord(BaseModel):
    """Persisted shape used by review dashboard."""

    id: UUID
    prompt_version: str
    output_text: str
    flagged: bool
    axes: list[AxisScore]
    review_label: ReviewLabel
    created_at: datetime
    reviewed_at: datetime | None = None


class ReviewDecision(BaseModel):
    label: ReviewLabel

    @classmethod
    def is_terminal(cls, label: ReviewLabel) -> bool:
        return label != ReviewLabel.UNREVIEWED
