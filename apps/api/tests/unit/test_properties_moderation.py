"""Property tests for the moderation scorer."""

from __future__ import annotations

import itertools

from hypothesis import given, settings
from hypothesis import strategies as st

from evalforge.scorers.moderation import (
    HARASSMENT_PATTERNS,
    PROFANITY,
    TOXICITY_PHRASES,
    ModerationScorer,
)


@settings(max_examples=300, deadline=None)
@given(text=st.text(min_size=1, max_size=2000))
def test_moderation_never_crashes_and_score_in_unit_interval(text: str) -> None:
    s = ModerationScorer().score(text, {})
    assert 0.0 <= s.score <= 1.0
    assert isinstance(s.flagged, bool)
    assert s.axis.value == "moderation"


@settings(max_examples=300, deadline=None)
@given(
    text=st.text(
        alphabet=st.characters(min_codepoint=0x0600, max_codepoint=0x06FF),  # Arabic block
        min_size=1,
        max_size=200,
    )
)
def test_moderation_handles_rtl_scripts(text: str) -> None:
    s = ModerationScorer().score(text, {})
    assert 0.0 <= s.score <= 1.0
    # RTL-only text contains no English profanity, so it must be clean.
    assert s.label == "clean"
    assert s.flagged is False


@settings(max_examples=200, deadline=None)
@given(
    text=st.text(
        alphabet=st.characters(min_codepoint=0x4E00, max_codepoint=0x9FFF),  # CJK Unified
        min_size=1,
        max_size=200,
    )
)
def test_moderation_handles_cjk_scripts(text: str) -> None:
    s = ModerationScorer().score(text, {})
    assert s.label == "clean"
    assert s.flagged is False


@settings(max_examples=100, deadline=None)
@given(prefix=st.text(max_size=50), suffix=st.text(max_size=50))
def test_contribution_offsets_are_valid(prefix: str, suffix: str) -> None:
    word = "crap"
    text = f"{prefix} {word} {suffix}"
    s = ModerationScorer().score(text, {})
    for c in s.contributions:
        assert c.offset >= 0
        assert c.offset + c.length <= len(text)
        assert text[c.offset : c.offset + c.length] == c.snippet


def test_decision_table_full_coverage() -> None:
    """Decision table: every (profanity, toxicity, harassment) triple maps to expected label."""

    profanity_word = next(iter(PROFANITY))  # any
    toxicity_phrase = TOXICITY_PHRASES[0]
    harassment_pat = HARASSMENT_PATTERNS[0]  # 'kill yourself'
    harassment_phrase = "kill yourself"
    # Sanity: ensure the phrase matches the first pattern.
    assert harassment_pat.search(harassment_phrase) is not None

    scorer = ModerationScorer()
    fragments = {
        "profanity": profanity_word,
        "toxicity": toxicity_phrase,
        "harassment": harassment_phrase,
    }

    expected_priority = ["harassment", "toxicity", "profanity"]

    rows = 0
    for p_on, t_on, h_on in itertools.product([False, True], repeat=3):
        rows += 1
        parts = []
        if p_on:
            parts.append(fragments["profanity"])
        if t_on:
            parts.append(fragments["toxicity"])
        if h_on:
            parts.append(fragments["harassment"])
        text = " | ".join(parts) if parts else "neutral phrase"
        result = scorer.score(text, {})

        any_on = p_on or t_on or h_on
        assert result.flagged is any_on, (text, result)
        if not any_on:
            assert result.label == "clean"
            continue

        # Label follows priority: harassment > toxicity > profanity.
        for priority_label in expected_priority:
            if (
                (priority_label == "profanity" and p_on)
                or (priority_label == "toxicity" and t_on)
                or (priority_label == "harassment" and h_on)
            ):
                assert result.label == priority_label, (text, result.label, priority_label)
                break
    assert rows == 8  # 2^3
