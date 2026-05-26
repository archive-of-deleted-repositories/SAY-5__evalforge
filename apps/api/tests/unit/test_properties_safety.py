"""Property tests for the safety scorer."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from evalforge.scorers.safety import SafetyScorer


@settings(max_examples=300, deadline=None)
@given(text=st.text(min_size=1, max_size=2000))
def test_safety_never_crashes(text: str) -> None:
    s = SafetyScorer().score(text, {})
    assert 0.0 <= s.score <= 1.0
    assert isinstance(s.flagged, bool)


@settings(max_examples=200, deadline=None)
@given(
    digits=st.text(alphabet="0123456789", min_size=9, max_size=9),
)
def test_ssn_pattern_consistently_flagged(digits: str) -> None:
    formatted = f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
    s = SafetyScorer().score(f"My SSN is {formatted}", {})
    assert s.flagged is True
    assert any("pii" in r for r in s.reasons)


@settings(max_examples=100, deadline=None)
@given(
    local=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=2, max_size=20),
    domain=st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=3, max_size=20),
)
def test_email_pattern_consistently_flagged(local: str, domain: str) -> None:
    email = f"{local}@{domain}.com"
    s = SafetyScorer().score(f"contact me at {email}", {})
    assert s.flagged is True
