"""Property invariants for the review queue."""

from __future__ import annotations

import uuid

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from evalforge.schemas import Axis, AxisScore, ReviewLabel
from evalforge.store import make_store


def _axes() -> list[AxisScore]:
    return [
        AxisScore(axis=Axis.QUALITY, score=0.1, label="off", flagged=True),
        AxisScore(axis=Axis.SAFETY, score=0.0, label="clean", flagged=False),
        AxisScore(axis=Axis.MODERATION, score=0.0, label="clean", flagged=False),
    ]


terminal = st.sampled_from(
    [ReviewLabel.CORRECT, ReviewLabel.FALSE_POSITIVE, ReviewLabel.FALSE_NEGATIVE]
)


@settings(
    max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None
)
@given(label=terminal)
def test_terminal_label_persists(label: ReviewLabel) -> None:
    store = make_store("sqlite+pysqlite:///:memory:")
    cid = uuid.uuid4()
    store.insert_check(
        check_id=cid, prompt_version="v1", output_text="x", flagged=True, axes=_axes()
    )
    store.review(cid, label)
    got = store.get(cid)
    assert got is not None
    assert got.review_label == label


@settings(
    max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None
)
@given(first=terminal, second=terminal)
def test_cannot_change_terminal_label(first: ReviewLabel, second: ReviewLabel) -> None:
    if first == second:
        return  # idempotent re-apply is allowed
    store = make_store("sqlite+pysqlite:///:memory:")
    cid = uuid.uuid4()
    store.insert_check(
        check_id=cid, prompt_version="v1", output_text="x", flagged=True, axes=_axes()
    )
    store.review(cid, first)
    with pytest.raises(ValueError):
        store.review(cid, second)


@settings(
    max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None
)
@given(label=terminal)
def test_idempotent_reapply(label: ReviewLabel) -> None:
    store = make_store("sqlite+pysqlite:///:memory:")
    cid = uuid.uuid4()
    store.insert_check(
        check_id=cid, prompt_version="v1", output_text="x", flagged=True, axes=_axes()
    )
    store.review(cid, label)
    store.review(cid, label)  # idempotent
    got = store.get(cid)
    assert got is not None
    assert got.review_label == label
