"""End-to-end check: scoring under FakeProvider with all three axes, persisted to Postgres."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, text

from evalforge.engine import ScoringEngine
from evalforge.store import Base, Store, make_session_factory

try:
    from testcontainers.postgres import PostgresContainer
except Exception:  # noqa: BLE001
    PostgresContainer = None  # type: ignore[assignment]


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def pg_url() -> Iterator[str]:
    if PostgresContainer is None:
        pytest.skip("testcontainers not available")
    if not os.environ.get("DOCKER_HOST") and not os.path.exists("/var/run/docker.sock"):
        pytest.skip("docker not available")
    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url()
        # testcontainers returns psycopg2 by default; rewrite to psycopg v3.
        url = url.replace("postgresql+psycopg2", "postgresql+psycopg")
        if "+psycopg" not in url:
            url = url.replace("postgresql://", "postgresql+psycopg://")
        yield url


@pytest.fixture()
def store(pg_url: str) -> Store:
    engine = create_engine(pg_url, future=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    return Store(make_session_factory(engine))


def test_full_roundtrip(store: Store) -> None:
    eng = ScoringEngine()
    text_in = "You are stupid and useless"
    result = eng.run(text_in, {})
    cid = uuid.uuid4()
    rec = store.insert_check(
        check_id=cid,
        prompt_version="v1",
        output_text=text_in,
        flagged=result.flagged,
        axes=result.axes,
    )
    assert rec.flagged is True
    # Survives a fresh read.
    fetched = store.get(cid)
    assert fetched is not None
    assert fetched.flagged is True
    axes = {a.axis.value for a in fetched.axes}
    assert axes == {"quality", "safety", "moderation"}


def test_review_queue_in_postgres(store: Store) -> None:
    eng = ScoringEngine()
    flagged_id = uuid.uuid4()
    res = eng.run("you are stupid", {})
    store.insert_check(
        check_id=flagged_id,
        prompt_version="v1",
        output_text="you are stupid",
        flagged=res.flagged,
        axes=res.axes,
    )
    queue = store.list_queue()
    assert any(c.id == flagged_id for c in queue)


def test_schema_exists(pg_url: str) -> None:
    engine = create_engine(pg_url, future=True)
    with engine.connect() as conn:
        tables = (
            conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
                )
            )
            .scalars()
            .all()
        )
    assert "checks" in tables
    assert "labeled_examples" in tables
