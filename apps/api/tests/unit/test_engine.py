"""ScoringEngine: aggregation across the three axes."""

from __future__ import annotations

from evalforge.engine import ScoringEngine


def test_clean_helpful_text_unflagged() -> None:
    eng = ScoringEngine()
    text = "Helpful, factually grounded answer responding to the prompt with verifiable claims."
    res = eng.run(text, {})
    assert res.flagged is False
    assert len(res.axes) == 3


def test_profanity_flags_overall() -> None:
    eng = ScoringEngine()
    res = eng.run("This is total crap", {})
    assert res.flagged is True
    # Moderation axis must be the flagger here.
    mod = next(a for a in res.axes if a.axis.value == "moderation")
    assert mod.flagged is True


def test_pii_flags_overall() -> None:
    eng = ScoringEngine()
    res = eng.run(
        "Helpful grounded verifiable claims responding to the prompt. Email: x@y.com",
        {},
    )
    assert res.flagged is True
    safety = next(a for a in res.axes if a.axis.value == "safety")
    assert safety.flagged is True
