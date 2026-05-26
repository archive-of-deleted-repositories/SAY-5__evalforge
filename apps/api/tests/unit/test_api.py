"""FastAPI route tests via TestClient (in-process)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from evalforge.api import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def test_healthz(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_evaluate_clean(client: TestClient) -> None:
    r = client.post(
        "/v1/evaluate",
        json={
            "prompt_version": "v1",
            "output_text": "Helpful, factually grounded, verifiable claims, responding to the prompt.",
            "context": {},
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "check_id" in body
    assert isinstance(body["axes"], list) and len(body["axes"]) == 3
    assert body["latency_ms"] >= 0


def test_evaluate_flagged(client: TestClient) -> None:
    r = client.post(
        "/v1/evaluate",
        json={"prompt_version": "v1", "output_text": "you are stupid, total crap", "context": {}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["flagged"] is True


def test_review_workflow(client: TestClient) -> None:
    r = client.post(
        "/v1/evaluate",
        json={"prompt_version": "v1", "output_text": "you are stupid", "context": {}},
    )
    cid = r.json()["check_id"]
    queue = client.get("/v1/queue").json()
    assert any(c["id"] == cid for c in queue)

    r2 = client.post(f"/v1/checks/{cid}/review", json={"label": "false_positive"})
    assert r2.status_code == 200
    assert r2.json()["review_label"] == "false_positive"

    # Cannot change to a different terminal label.
    r3 = client.post(f"/v1/checks/{cid}/review", json={"label": "correct"})
    assert r3.status_code == 409


def test_prompt_version_stats(client: TestClient) -> None:
    client.post(
        "/v1/evaluate",
        json={"prompt_version": "v1", "output_text": "helpful grounded verifiable", "context": {}},
    )
    r = client.get("/v1/prompt-versions/stats")
    assert r.status_code == 200
    stats = r.json()
    assert isinstance(stats, list)
