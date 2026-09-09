"""Hermetic HTTP contract tests for the optional Claude judge."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator

import httpx
import pytest

from evalforge.provider import ClaudeProvider, FakeProvider, get_default_provider
from evalforge.provider._base import JudgeVerdict
from evalforge.scorers.quality import QualityScorer

KEY = "synthetic-test-key"
MODEL = "claude-test-model"
VERDICT = {"score": 0.8, "label": "on_rubric", "reason": "The answer meets the rubric."}


def message(verdict: object = VERDICT, *, stop_reason: str = "end_turn") -> dict:
    return {
        "id": "msg_fixture",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": json.dumps(verdict)}],
        "model": MODEL,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 50, "output_tokens": 30},
    }


def provider(handler) -> ClaudeProvider:
    return ClaudeProvider(api_key=KEY, model=MODEL, transport=httpx.MockTransport(handler))


def test_selected_claude_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVALFORGE_PROVIDER", "claude")
    monkeypatch.setenv("EVALFORGE_CLAUDE_MODEL", MODEL)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        get_default_provider()


def test_selected_claude_requires_explicit_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVALFORGE_PROVIDER", "claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    monkeypatch.delenv("EVALFORGE_CLAUDE_MODEL", raising=False)
    with pytest.raises(ValueError, match="EVALFORGE_CLAUDE_MODEL"):
        get_default_provider()


def test_fake_remains_default_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EVALFORGE_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert isinstance(get_default_provider(), FakeProvider)


def test_unknown_provider_does_not_silently_run_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVALFORGE_PROVIDER", "cluade")
    with pytest.raises(ValueError, match="EVALFORGE_PROVIDER"):
        get_default_provider()


def test_messages_request_carries_rubric_output_and_review_examples() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "POST"
        assert str(request.url) == "https://api.anthropic.com/v1/messages"
        assert request.headers["x-api-key"] == KEY
        assert request.headers["anthropic-version"] == "2023-06-01"
        body = json.loads(request.content)
        assert body["model"] == MODEL
        assert body["max_tokens"] == 512
        assert body["output_config"]["format"]["type"] == "json_schema"
        data = json.loads(body["messages"][0]["content"])
        assert data["rubric"] == "Explain retries"
        assert data["output_text"] == "Retry transient failures."
        assert data["few_shot"] == [
            {"output_text": "A human-approved answer.", "label": "not_flagged"},
            {"output_text": "An incorrect answer.", "label": "flagged"},
        ]
        assert "untrusted" in body["system"].lower()
        assert "Retry transient failures." not in body["system"]
        assert request.extensions["timeout"]["read"] == 10.0
        return httpx.Response(200, json=message())

    result = provider(handler).judge(
        "Explain retries",
        "Retry transient failures.",
        [("A human-approved answer.", "not_flagged"), ("An incorrect answer.", "flagged")],
    )
    assert result == JudgeVerdict(**VERDICT)
    assert len(requests) == 1


def test_cloud_off_rubric_verdict_controls_quality_flag() -> None:
    verdict = {"score": 0.1, "label": "off_rubric", "reason": "Missing the requested evidence."}
    scorer = QualityScorer(provider=provider(lambda _: httpx.Response(200, json=message(verdict))))
    result = scorer.score("unrelated answer", {"rubric": "Explain retries"})
    assert result.flagged is True
    assert result.reasons == [verdict["reason"]]


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -0.1, 1.1, True, "0.8", None])
def test_invalid_scores_never_become_successful_verdicts(score: object) -> None:
    p = provider(lambda _: httpx.Response(200, json=message({**VERDICT, "score": score})))
    with pytest.raises(RuntimeError, match="verdict"):
        p.judge("rubric", "output")


@pytest.mark.parametrize(
    "verdict",
    [
        [],
        {"score": 0.8},
        {**VERDICT, "label": "approved"},
        {**VERDICT, "reason": ""},
        {**VERDICT, "reason": " "},
        {**VERDICT, "reason": "x" * 2001},
        {**VERDICT, "secret": "unexpected"},
    ],
)
def test_invalid_verdict_shapes_are_rejected(verdict: object) -> None:
    p = provider(lambda _: httpx.Response(200, json=message(verdict)))
    with pytest.raises(RuntimeError, match="verdict"):
        p.judge("rubric", "output")


@pytest.mark.parametrize("stop_reason", ["max_tokens", "refusal", "tool_use", "pause_turn"])
def test_incomplete_or_refused_response_is_not_a_verdict(stop_reason: str) -> None:
    p = provider(lambda _: httpx.Response(200, json=message(stop_reason=stop_reason)))
    with pytest.raises(RuntimeError, match="completed"):
        p.judge("rubric", "output")


@pytest.mark.parametrize("body", [b"not json", b"[]", b'{"content": []}', b'{"type":"message"}'])
def test_invalid_response_envelopes_are_rejected(body: bytes) -> None:
    p = provider(lambda _: httpx.Response(200, content=body))
    with pytest.raises(RuntimeError):
        p.judge("rubric", "output")


@pytest.mark.parametrize("status", [302, 401, 429, 500, 529])
def test_http_errors_do_not_retry_or_expose_upstream_body(status: int) -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            status,
            text=f"private upstream content {KEY}",
            headers={"location": "https://other.invalid"},
        )

    with pytest.raises(RuntimeError) as error:
        provider(handler).judge("rubric", "private candidate text")
    assert calls == 1
    assert KEY not in str(error.value)
    assert "private" not in str(error.value)


def test_timeout_is_clear_and_does_not_fall_back_to_fake() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("upstream text must not be exposed", request=request)

    with pytest.raises(RuntimeError, match="timed out"):
        provider(handler).judge("rubric", "output")


class SlowDripBody(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.chunks = [b" "] * 100 + [json.dumps(message()).encode()]
        self.reads = 0
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for chunk in self.chunks:
            await asyncio.sleep(0.01)
            self.reads += 1
            yield chunk

    async def aclose(self) -> None:
        self.closed = True


def test_total_deadline_stops_a_response_that_keeps_delivering_chunks() -> None:
    body = SlowDripBody()
    p = ClaudeProvider(
        api_key=KEY,
        model=MODEL,
        timeout_seconds=0.05,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=body)),
    )
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="timed out"):
        p.judge("rubric", "output")
    assert time.monotonic() - started < 0.5
    assert body.reads < len(body.chunks)
    assert body.closed is True


def test_total_deadline_cancels_waiting_for_response_headers() -> None:
    cancelled = False

    async def handler(_: httpx.Request) -> httpx.Response:
        nonlocal cancelled
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            cancelled = True
            raise
        return httpx.Response(200, json=message())

    p = ClaudeProvider(
        api_key=KEY,
        model=MODEL,
        timeout_seconds=0.05,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(RuntimeError, match="timed out"):
        p.judge("rubric", "output")
    assert cancelled is True


class ChunkedBody(httpx.AsyncByteStream):
    def __init__(self) -> None:
        self.reads = 0
        self.closed = False

    async def __aiter__(self) -> AsyncIterator[bytes]:
        for _ in range(5):
            self.reads += 1
            yield b"x" * (32 * 1024)

    async def aclose(self) -> None:
        self.closed = True


def test_oversized_stream_is_closed_before_reading_the_rest() -> None:
    body = ChunkedBody()
    p = provider(lambda _: httpx.Response(200, stream=body))
    with pytest.raises(RuntimeError, match="size limit"):
        p.judge("rubric", "output")
    assert body.reads == 3
    assert body.closed is True


@pytest.mark.parametrize("size", ["65537", "9" * 5000], ids=["over_limit", "huge_integer"])
def test_declared_oversized_response_is_closed_without_reading(size: str) -> None:
    body = ChunkedBody()
    p = provider(lambda _: httpx.Response(200, stream=body, headers={"content-length": size}))
    with pytest.raises(RuntimeError, match="size limit"):
        p.judge("rubric", "output")
    assert body.reads == 0
    assert body.closed is True


def test_few_shot_corrections_preserve_threshold_relaxation() -> None:
    verdict = {"score": 0.3, "label": "on_rubric", "reason": "Borderline but approved by review."}
    p = provider(lambda _: httpx.Response(200, json=message(verdict)))
    with pytest.raises(RuntimeError, match="inconsistent verdict"):
        p.judge("rubric", "output")
    assert p.judge("rubric", "output", [("approved", "not_flagged")] * 3).label == "on_rubric"


@pytest.mark.parametrize(
    "blocks",
    [
        [],
        {},
        [{"type": "text", "text": 12}],
        [{"type": "tool_use"}],
        [{"type": "text", "text": "not JSON"}],
    ],
)
def test_invalid_content_blocks_are_rejected(blocks: object) -> None:
    body = {**message(), "content": blocks}
    with pytest.raises(RuntimeError, match="verdict"):
        provider(lambda _: httpx.Response(200, json=body)).judge("rubric", "output")


def test_deeply_nested_response_is_a_provider_failure() -> None:
    body = b"[" * 20_000 + b"0" + b"]" * 20_000
    with pytest.raises(RuntimeError, match="invalid response"):
        provider(lambda _: httpx.Response(200, content=body)).judge("rubric", "output")


def test_input_limit_prevents_an_upstream_request() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=message())

    with pytest.raises(RuntimeError, match="input exceeds"):
        provider(handler).judge("x" * (512 * 1024), "output")
    assert calls == 0


def test_connection_failure_is_sanitized() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"private diagnostics {KEY}", request=request)

    with pytest.raises(RuntimeError, match="request failed") as error:
        provider(handler).judge("rubric", "output")
    assert KEY not in str(error.value)


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_timeout_configuration_must_be_bounded(timeout: float) -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        ClaudeProvider(api_key=KEY, model=MODEL, timeout_seconds=timeout)
