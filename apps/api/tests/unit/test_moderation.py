"""Moderation scorer tests."""

from __future__ import annotations

from evalforge.scorers.moderation import ModerationScorer


def test_clean_text_passes() -> None:
    s = ModerationScorer().score("Hello, this is a friendly message.", {})
    assert s.flagged is False
    assert s.label == "clean"
    assert s.score == 0.0


def test_profanity_flags() -> None:
    s = ModerationScorer().score("That is total crap, honestly.", {})
    assert s.flagged is True
    assert s.label == "profanity"
    assert any(c.feature == "moderation:profanity" for c in s.contributions)


def test_toxicity_flags() -> None:
    s = ModerationScorer().score("You are stupid and you know it.", {})
    assert s.flagged is True
    assert s.label == "toxicity"


def test_harassment_outweighs_others() -> None:
    s = ModerationScorer().score("crap, kill yourself", {})
    assert s.flagged is True
    assert s.label == "harassment"
    # Score should reflect the harassment weight, not just be 0
    assert s.score > 0.0


def test_contribution_offsets_match_substring() -> None:
    text = "Hello crap world"
    s = ModerationScorer().score(text, {})
    assert s.contributions, "expected at least one contribution"
    c = s.contributions[0]
    assert text[c.offset : c.offset + c.length].lower() == "crap"
