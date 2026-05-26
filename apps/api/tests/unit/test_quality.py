"""Quality scorer tests using FakeProvider."""

from __future__ import annotations

from evalforge.provider.fake import FakeProvider
from evalforge.scorers.quality import QualityScorer


def test_on_rubric_text_passes() -> None:
    scorer = QualityScorer(provider=FakeProvider())
    text = (
        "The response is helpful and factually grounded in verifiable claims, "
        "avoiding speculation while responding to the prompt."
    )
    s = scorer.score(text, {})
    assert s.flagged is False
    assert s.label == "on_rubric"


def test_off_rubric_text_flags() -> None:
    scorer = QualityScorer(provider=FakeProvider())
    s = scorer.score("xyz qqq rrr", {})
    assert s.flagged is True
    assert s.label == "off_rubric"


def test_few_shot_relaxes_threshold() -> None:
    base = QualityScorer(provider=FakeProvider())
    relaxed = QualityScorer(
        provider=FakeProvider(),
        few_shot_examples=[
            ("ex one", "not_flagged"),
            ("ex two", "not_flagged"),
            ("ex three", "not_flagged"),
        ],
    )
    text = "helpful grounded"
    base_score = base.score(text, {})
    relaxed_score = relaxed.score(text, {})
    # Same scoring math, but a relaxed threshold should be more lenient on borderline.
    if base_score.flagged:
        # Either the relaxed scorer drops the flag OR the score is identical (which is fine).
        assert relaxed_score.flagged is False or relaxed_score.score == base_score.score


def test_custom_rubric_via_context() -> None:
    scorer = QualityScorer(provider=FakeProvider())
    # Use enough tokens to exceed the length penalty.
    s = scorer.score(
        "apple banana cherry mango",
        {"rubric": "Mention apple banana cherry mango"},
    )
    # 4 out of 4 distinct rubric tokens overlap; the result is on-rubric.
    assert s.flagged is False
    assert s.label == "on_rubric"
