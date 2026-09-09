"""A cloud judge must not block the API or manufacture a successful check."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Sequence

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from evalforge.api import app
from evalforge.provider import JudgeProviderError, JudgeVerdict

SERVICE_KEY = "evalforge-service-test-key-32-characters"


def paid_mode(monkeypatch) -> None:
    monkeypatch.setenv("EVALFORGE_PROVIDER", "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "synthetic-provider-key")
    monkeypatch.setenv("EVALFORGE_CLAUDE_MODEL", "claude-test-model")
    monkeypatch.setenv("EVALFORGE_API_KEY", SERVICE_KEY)
    monkeypatch.setenv("EVALFORGE_CLAUDE_MAX_CONCURRENCY", "1")


def test_paid_websocket_requires_header_credentials(monkeypatch) -> None:
    paid_mode(monkeypatch)
    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect), client.websocket_connect("/v1/live"):
            pass
        with (
            pytest.raises(WebSocketDisconnect),
            client.websocket_connect(f"/v1/live?api_key={SERVICE_KEY}"),
        ):
            pass
        with client.websocket_connect(
            "/v1/live", headers={"Authorization": f"Bearer {SERVICE_KEY}"}
        ) as socket:
            socket.send_text("ping")
            assert socket.receive_text() == "ping"


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", ["0", "17", "invalid"])
async def test_paid_concurrency_configuration_is_bounded(monkeypatch, limit: str) -> None:
    paid_mode(monkeypatch)
    monkeypatch.setenv("EVALFORGE_CLAUDE_MAX_CONCURRENCY", limit)
    with pytest.raises(ValueError, match="MAX_CONCURRENCY"):
        async with app.router.lifespan_context(app):
            pass


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "rubric",
    [123, None, "", " ", "x" * 16_385],
    ids=["number", "null", "empty", "blank", "oversized"],
)
async def test_invalid_rubric_is_rejected_before_paid_work(monkeypatch, rubric: object) -> None:
    paid_mode(monkeypatch)
    calls = 0

    class CountedProvider:
        def judge(self, rubric, output_text, few_shot=()) -> JudgeVerdict:
            nonlocal calls
            calls += 1
            return JudgeVerdict(0.8, "on_rubric", "Meets the rubric.")

    async with app.router.lifespan_context(app):
        app.state.app.engine.quality.provider = CountedProvider()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {SERVICE_KEY}"},
        ) as client:
            payload = {**request(), "context": {"rubric": rubric}}
            result = await client.post("/v1/evaluate", json=payload)
            assert result.status_code == 422
            assert calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["", "short"])
async def test_paid_mode_requires_a_service_key(monkeypatch, key: str) -> None:
    paid_mode(monkeypatch)
    monkeypatch.setenv("EVALFORGE_API_KEY", key)
    with pytest.raises(ValueError, match="EVALFORGE_API_KEY"):
        async with app.router.lifespan_context(app):
            pass


@pytest.mark.asyncio
async def test_unauthorized_paid_requests_never_reach_the_provider(monkeypatch) -> None:
    paid_mode(monkeypatch)
    calls = 0

    class PaidProvider:
        def judge(self, rubric, output_text, few_shot=()) -> JudgeVerdict:
            nonlocal calls
            calls += 1
            return JudgeVerdict(0.8, "on_rubric", "Meets the rubric.")

    async with app.router.lifespan_context(app):
        app.state.app.engine.quality.provider = PaidProvider()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            for headers in [
                {},
                {"Authorization": "Bearer wrong"},
                {"Authorization": "Basic invalid"},
            ]:
                result = await client.post("/v1/evaluate", json=request(), headers=headers)
                assert result.status_code == 401
            assert calls == 0
            assert (await client.get("/v1/checks/recent")).status_code == 401
            assert (
                await client.post(
                    "/v1/checks/00000000-0000-4000-8000-000000000001/review",
                    json={"label": "false_positive"},
                )
            ).status_code == 401
            authorized = await client.post(
                "/v1/evaluate", json=request(), headers={"Authorization": f"Bearer {SERVICE_KEY}"}
            )
            assert authorized.status_code == 200
            assert calls == 1


@pytest.mark.asyncio
async def test_paid_admission_rejects_overload_and_holds_slot_after_caller_cancels(
    monkeypatch,
) -> None:
    paid_mode(monkeypatch)
    started = threading.Event()
    release = threading.Event()
    calls = 0

    class BlockingProvider:
        def judge(self, rubric, output_text, few_shot=()) -> JudgeVerdict:
            nonlocal calls
            calls += 1
            started.set()
            release.wait(timeout=2)
            return JudgeVerdict(0.8, "on_rubric", "Meets the rubric.")

    async with app.router.lifespan_context(app):
        app.state.app.engine.quality.provider = BlockingProvider()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {SERVICE_KEY}"},
        ) as client:
            first = asyncio.create_task(client.post("/v1/evaluate", json=request()))
            try:
                assert await asyncio.to_thread(started.wait, 1)
                second = await client.post("/v1/evaluate", json=request())
                assert second.status_code == 503
                assert calls == 1
                first.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await first
                third = await client.post("/v1/evaluate", json=request())
                assert third.status_code == 503
                assert calls == 1
            finally:
                release.set()
                await asyncio.gather(first, return_exceptions=True)
                await asyncio.gather(
                    *getattr(app.state.app, "paid_tasks", set()), return_exceptions=True
                )
            fourth = await client.post("/v1/evaluate", json=request())
            assert fourth.status_code == 200
            assert calls == 2


def request(version: str = "v1") -> dict:
    return {"prompt_version": version, "output_text": version, "context": {}}


@pytest.mark.asyncio
async def test_provider_failure_returns_503_without_a_successful_check() -> None:
    class FailedProvider:
        def judge(self, rubric, output_text, few_shot=()) -> JudgeVerdict:
            raise JudgeProviderError("private provider diagnostics")

    async with app.router.lifespan_context(app):
        app.state.app.engine.quality.provider = FailedProvider()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            result = await client.post("/v1/evaluate", json=request())
            assert result.status_code == 503
            assert result.json() == {"detail": "Quality judge unavailable. Try again later."}
            assert (await client.get("/v1/checks/recent")).json() == []


@pytest.mark.asyncio
async def test_paid_provider_failure_releases_the_admission_slot(monkeypatch) -> None:
    paid_mode(monkeypatch)
    calls = 0

    class TransientProvider:
        def judge(self, rubric, output_text, few_shot=()) -> JudgeVerdict:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise JudgeProviderError("temporary failure")
            return JudgeVerdict(0.8, "on_rubric", "Meets the rubric.")

    async with app.router.lifespan_context(app):
        app.state.app.engine.quality.provider = TransientProvider()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {SERVICE_KEY}"},
        ) as client:
            assert (await client.post("/v1/evaluate", json=request())).status_code == 503
            assert (await client.post("/v1/evaluate", json=request())).status_code == 200
            assert calls == 2


@pytest.mark.asyncio
async def test_slow_judge_does_not_block_health_requests() -> None:
    started = threading.Event()
    release = threading.Event()

    class SlowProvider:
        def judge(self, rubric, output_text, few_shot=()) -> JudgeVerdict:
            started.set()
            release.wait(timeout=2)
            return JudgeVerdict(0.8, "on_rubric", "Meets the rubric.")

    async with app.router.lifespan_context(app):
        app.state.app.engine.quality.provider = SlowProvider()
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            evaluation = asyncio.create_task(client.post("/v1/evaluate", json=request()))
            try:
                assert await asyncio.to_thread(started.wait, 1)
                health = await client.get("/healthz")
                assert health.status_code == 200
                assert not evaluation.done(), "The judge blocked the API until scoring finished"
            finally:
                release.set()
                result = await evaluation
            assert result.status_code == 200


@pytest.mark.asyncio
async def test_parallel_evaluations_keep_prompt_specific_review_examples(monkeypatch) -> None:
    observed: dict[str, Sequence[tuple[str, str]]] = {}

    class RecordingProvider:
        def judge(self, rubric, output_text, few_shot=()) -> JudgeVerdict:
            observed[output_text] = few_shot
            return JudgeVerdict(0.8, "on_rubric", "Meets the rubric.")

    async with app.router.lifespan_context(app):
        state = app.state.app
        state.engine.quality.provider = RecordingProvider()
        monkeypatch.setattr(
            state.store,
            "sample_labeled_examples",
            lambda prompt_version, k: [(prompt_version + " reviewed answer", "not_flagged")],
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            results = await asyncio.gather(
                *[
                    client.post("/v1/evaluate", json=request(version))
                    for version in ["first", "second"]
                ]
            )
            assert [result.status_code for result in results] == [200, 200]
        assert observed == {
            "first": [("first reviewed answer", "not_flagged")],
            "second": [("second reviewed answer", "not_flagged")],
        }
        assert (
            state.engine.quality.few_shot_examples == []
        ), "Request examples leaked into shared state"
