"""FastAPI application: inline /v1/evaluate plus review + dashboard surfaces."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import generate_latest

from evalforge.engine import ScoringEngine
from evalforge.obs import (
    EVALUATE_LATENCY_MS,
    QUEUE_DEPTH,
    REQUESTS_TOTAL,
    get_logger,
    setup_logging,
)
from evalforge.obs.metrics import REGISTRY
from evalforge.queue import WriteJob, WriteQueue, utcnow
from evalforge.schemas import (
    CheckRecord,
    ReviewDecision,
    ScoreRequest,
    ScoreResponse,
)
from evalforge.scorers.quality import QualityScorer
from evalforge.store import Store, make_store
from evalforge.ws import LiveFeed


class AppState:
    store: Store
    engine: ScoringEngine
    queue: WriteQueue
    live: LiveFeed


def build_engine(store: Store) -> ScoringEngine:
    # Quality scorer gets few-shot examples seeded from labeled corrections at startup.
    # The samples are refreshed lazily per request via the store.
    samples = store.sample_labeled_examples(prompt_version="default", k=3)
    quality = QualityScorer(few_shot_examples=samples)
    return ScoringEngine(quality=quality)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    log = get_logger("evalforge.api")
    state = AppState()
    state.store = make_store()
    state.engine = build_engine(state.store)
    state.live = LiveFeed()
    state.queue = WriteQueue(state.store)

    async def push_to_live(job: WriteJob) -> None:
        await state.live.broadcast(
            {
                "type": "check",
                "id": str(job.check_id),
                "prompt_version": job.prompt_version,
                "flagged": job.flagged,
                "created_at": job.created_at.isoformat(),
                "axes": [a.model_dump(mode="json") for a in job.axes],
                "output_text": job.output_text,
            }
        )

    state.queue.on_persisted(push_to_live)
    state.queue.start()
    app.state.app = state
    log.info("evalforge_ready")
    try:
        yield
    finally:
        await state.queue.stop()


app = FastAPI(title="EvalForge", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_state() -> AppState:
    return app.state.app  # type: ignore[no-any-return]


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> Response:
    data = generate_latest(REGISTRY)
    return Response(content=data, media_type="text/plain; version=0.0.4")


@app.post("/v1/evaluate", response_model=ScoreResponse)
async def evaluate(req: ScoreRequest, state: AppState = Depends(get_state)) -> ScoreResponse:
    t0 = time.perf_counter()
    try:
        # Refresh few-shot from labeled examples; cheap because limited to k=3.
        samples = state.store.sample_labeled_examples(req.prompt_version, k=3)
        state.engine.quality.few_shot_examples = samples

        result = state.engine.run(req.output_text, req.context)
        check_id = uuid.uuid4()
        now = utcnow()
        # Persistence is fire-and-forget; client sees the verdict immediately.
        state.queue.submit_nowait(
            WriteJob(
                check_id=check_id,
                prompt_version=req.prompt_version,
                output_text=req.output_text,
                flagged=result.flagged,
                axes=result.axes,
                created_at=now,
            )
        )
        QUEUE_DEPTH.set(state.queue.depth)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        EVALUATE_LATENCY_MS.observe(elapsed_ms)
        REQUESTS_TOTAL.labels(status="ok").inc()
        return ScoreResponse(
            check_id=check_id,
            flagged=result.flagged,
            axes=result.axes,
            latency_ms=elapsed_ms,
        )
    except Exception:
        REQUESTS_TOTAL.labels(status="error").inc()
        raise


@app.get("/v1/checks/recent", response_model=list[CheckRecord])
async def recent_checks(limit: int = 50, state: AppState = Depends(get_state)) -> list[CheckRecord]:
    if not 1 <= limit <= 500:
        raise HTTPException(status_code=400, detail="limit must be in [1, 500]")
    # Drain pending queue writes so the dashboard reflects what callers just sent.
    await _drain(state)
    return state.store.list_recent(limit)


@app.get("/v1/queue", response_model=list[CheckRecord])
async def review_queue(limit: int = 100, state: AppState = Depends(get_state)) -> list[CheckRecord]:
    await _drain(state)
    return state.store.list_queue(limit)


@app.get("/v1/checks/{check_id}", response_model=CheckRecord)
async def get_check(check_id: uuid.UUID, state: AppState = Depends(get_state)) -> CheckRecord:
    await _drain(state)
    rec = state.store.get(check_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="check not found")
    return rec


@app.post("/v1/checks/{check_id}/review", response_model=CheckRecord)
async def review_check(
    check_id: uuid.UUID,
    decision: ReviewDecision,
    state: AppState = Depends(get_state),
) -> CheckRecord:
    await _drain(state)
    try:
        return state.store.review(check_id, decision.label)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="check not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/v1/prompt-versions/stats")
async def prompt_version_stats(state: AppState = Depends(get_state)) -> list[dict[str, object]]:
    await _drain(state)
    return state.store.prompt_version_stats()


@app.websocket("/v1/live")
async def live_feed(ws: WebSocket, state: AppState = Depends(get_state)) -> None:
    await state.live.connect(ws)
    try:
        while True:
            # Heartbeat: clients can ping, server echos.
            msg = await ws.receive_text()
            await ws.send_text(msg)
    except WebSocketDisconnect:
        pass
    finally:
        await state.live.disconnect(ws)


async def _drain(state: AppState) -> None:
    """Wait for the in-process queue to flush. Used by dashboard reads to avoid lag."""
    for _ in range(20):
        if state.queue.depth == 0:
            return
        await asyncio.sleep(0.005)
