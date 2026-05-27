"""End-to-end active-learning loop: reviewer false_positive marks relax the quality scorer.

Posts a batch of borderline outputs that the quality scorer flags, marks a subset as
false_positive, then re-evaluates and asserts the corrected outputs now pass.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from evalforge.api import app

# Hits 4 of the 14 distinct rubric tokens => coverage ~0.29, which is below the base
# threshold (0.4) but above the relaxed threshold once not_flagged demos are sampled.
BORDERLINE = "helpful grounded verifiable prompt"
PROMPT_VERSION = "active-learning"


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as c:
        yield c


def _evaluate(client: TestClient, text: str) -> dict:
    r = client.post(
        "/v1/evaluate",
        json={"prompt_version": PROMPT_VERSION, "output_text": text, "context": {}},
    )
    assert r.status_code == 200, r.text
    return r.json()


def _quality_flagged(body: dict) -> bool:
    quality = next(a for a in body["axes"] if a["axis"] == "quality")
    return bool(quality["flagged"])


def test_false_positive_feedback_flips_quality(client: TestClient) -> None:
    # 50 borderline outputs; each unique so it lands as its own check.
    bodies = [_evaluate(client, f"{BORDERLINE} sample {i}") for i in range(50)]

    # Quality flags every borderline output at the base threshold.
    assert all(_quality_flagged(b) for b in bodies), "expected all 50 to flag on quality first"

    # Reviewer marks 10 as false_positive: each stores a not_flagged labeled example.
    corrected = bodies[:10]
    for b in corrected:
        r = client.post(
            f"/v1/checks/{b['check_id']}/review",
            json={"label": "false_positive"},
        )
        assert r.status_code == 200, r.text

    # Re-evaluate the same 10 outputs; sampled demos now relax the rubric threshold.
    flipped = 0
    for i in range(10):
        again = _evaluate(client, f"{BORDERLINE} sample {i}")
        quality = next(a for a in again["axes"] if a["axis"] == "quality")
        if quality["label"] == "on_rubric" and not quality["flagged"]:
            flipped += 1

    assert flipped >= 5, f"expected >=5 of 10 to flip to not_flagged, got {flipped}"
