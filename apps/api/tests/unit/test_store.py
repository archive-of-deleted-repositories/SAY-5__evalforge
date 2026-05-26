"""Store unit tests against in-memory SQLite."""

from __future__ import annotations

import uuid

import pytest

from evalforge.schemas import Axis, AxisScore, ReviewLabel
from evalforge.store import make_store


def _axes(flagged: bool = False) -> list[AxisScore]:
    return [
        AxisScore(axis=Axis.QUALITY, score=0.9, label="on_rubric", flagged=False),
        AxisScore(axis=Axis.SAFETY, score=0.0, label="clean", flagged=False),
        AxisScore(
            axis=Axis.MODERATION,
            score=0.3 if flagged else 0.0,
            label="profanity" if flagged else "clean",
            flagged=flagged,
        ),
    ]


def test_insert_and_get() -> None:
    store = make_store("sqlite+pysqlite:///:memory:")
    cid = uuid.uuid4()
    rec = store.insert_check(
        check_id=cid,
        prompt_version="v1",
        output_text="hello",
        flagged=False,
        axes=_axes(),
    )
    assert rec.id == cid
    got = store.get(cid)
    assert got is not None
    assert got.prompt_version == "v1"


def test_queue_returns_flagged_unreviewed_only() -> None:
    store = make_store("sqlite+pysqlite:///:memory:")
    flagged_id = uuid.uuid4()
    clean_id = uuid.uuid4()
    store.insert_check(
        check_id=flagged_id, prompt_version="v1", output_text="crap", flagged=True, axes=_axes(True)
    )
    store.insert_check(
        check_id=clean_id, prompt_version="v1", output_text="hi", flagged=False, axes=_axes(False)
    )
    q = store.list_queue()
    assert len(q) == 1
    assert q[0].id == flagged_id


def test_review_false_positive_creates_labeled_example() -> None:
    store = make_store("sqlite+pysqlite:///:memory:")
    cid = uuid.uuid4()
    store.insert_check(
        check_id=cid, prompt_version="v1", output_text="crap", flagged=True, axes=_axes(True)
    )
    store.review(cid, ReviewLabel.FALSE_POSITIVE)
    samples = store.sample_labeled_examples("v1", k=3)
    assert ("crap", "not_flagged") in samples


def test_cannot_change_review_label_once_set() -> None:
    store = make_store("sqlite+pysqlite:///:memory:")
    cid = uuid.uuid4()
    store.insert_check(
        check_id=cid, prompt_version="v1", output_text="crap", flagged=True, axes=_axes(True)
    )
    store.review(cid, ReviewLabel.CORRECT)
    with pytest.raises(ValueError):
        store.review(cid, ReviewLabel.FALSE_POSITIVE)


def test_cannot_transition_to_unreviewed() -> None:
    store = make_store("sqlite+pysqlite:///:memory:")
    cid = uuid.uuid4()
    store.insert_check(
        check_id=cid, prompt_version="v1", output_text="x", flagged=True, axes=_axes(True)
    )
    with pytest.raises(ValueError):
        store.review(cid, ReviewLabel.UNREVIEWED)


def test_prompt_version_stats() -> None:
    store = make_store("sqlite+pysqlite:///:memory:")
    store.insert_check(
        check_id=uuid.uuid4(),
        prompt_version="v1",
        output_text="x",
        flagged=False,
        axes=_axes(False),
    )
    store.insert_check(
        check_id=uuid.uuid4(), prompt_version="v1", output_text="y", flagged=True, axes=_axes(True)
    )
    store.insert_check(
        check_id=uuid.uuid4(),
        prompt_version="v2",
        output_text="z",
        flagged=False,
        axes=_axes(False),
    )
    stats = store.prompt_version_stats()
    versions = {s["prompt_version"] for s in stats}
    assert versions == {"v1", "v2"}
