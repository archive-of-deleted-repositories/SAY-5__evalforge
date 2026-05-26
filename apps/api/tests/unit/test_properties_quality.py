"""Property tests for the quality scorer."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from evalforge.provider.fake import FakeProvider
from evalforge.scorers.quality import QualityScorer


@settings(max_examples=300, deadline=None)
@given(text=st.text(min_size=1, max_size=2000))
def test_quality_never_crashes(text: str) -> None:
    s = QualityScorer(provider=FakeProvider()).score(text, {})
    assert 0.0 <= s.score <= 1.0
    assert isinstance(s.flagged, bool)


@settings(max_examples=200, deadline=None)
@given(
    text=st.text(
        alphabet=st.characters(min_codepoint=0x4E00, max_codepoint=0x9FFF),  # CJK
        min_size=1,
        max_size=200,
    )
)
def test_quality_handles_non_latin(text: str) -> None:
    s = QualityScorer(provider=FakeProvider()).score(text, {})
    # CJK text has no ASCII rubric tokens so it always scores 0 (off-rubric, flagged).
    assert s.score == 0.0
