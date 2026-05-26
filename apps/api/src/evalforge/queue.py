"""Async in-process queue between the request path and the persistence layer.

Keeps the hot path off the DB. The worker drains writes in the background.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from evalforge.schemas import AxisScore
from evalforge.store import Store

_log = logging.getLogger("evalforge.queue")


@dataclass(slots=True)
class WriteJob:
    check_id: UUID
    prompt_version: str
    output_text: str
    flagged: bool
    axes: list[AxisScore]
    created_at: datetime


class WriteQueue:
    """Bounded async queue with a single drain task per process."""

    def __init__(self, store: Store, *, maxsize: int = 10_000) -> None:
        self._store = store
        self._q: asyncio.Queue[WriteJob | None] = asyncio.Queue(maxsize=maxsize)
        self._task: asyncio.Task[None] | None = None
        self._listeners: list[Callable[[WriteJob], Awaitable[None]]] = []

    def on_persisted(self, cb: Callable[[WriteJob], Awaitable[None]]) -> None:
        self._listeners.append(cb)

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._drain(), name="evalforge-write-queue")

    async def stop(self) -> None:
        if self._task is None:
            return
        await self._q.put(None)
        await self._task
        self._task = None

    async def submit(self, job: WriteJob) -> None:
        await self._q.put(job)

    def submit_nowait(self, job: WriteJob) -> None:
        # Drop the write if the queue is saturated rather than block the hot path.
        try:
            self._q.put_nowait(job)
        except asyncio.QueueFull:
            _log.warning("write queue full; dropping check id=%s", job.check_id)

    @property
    def depth(self) -> int:
        return self._q.qsize()

    async def _drain(self) -> None:
        while True:
            job = await self._q.get()
            if job is None:
                return
            try:
                self._store.insert_check(
                    check_id=job.check_id,
                    prompt_version=job.prompt_version,
                    output_text=job.output_text,
                    flagged=job.flagged,
                    axes=job.axes,
                    created_at=job.created_at,
                )
                for cb in self._listeners:
                    try:
                        await cb(job)
                    except Exception:  # noqa: BLE001
                        _log.exception("listener failed")
            except Exception:  # noqa: BLE001
                _log.exception("failed to persist check %s", job.check_id)
            finally:
                self._q.task_done()


def utcnow() -> datetime:
    return datetime.now(UTC)
