"""WebSocket fan-out for the dashboard live feed."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

_log = logging.getLogger("evalforge.ws")


class LiveFeed:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        message = json.dumps(payload, default=str)
        async with self._lock:
            stale: list[WebSocket] = []
            for client in self._clients:
                try:
                    await client.send_text(message)
                except Exception:  # noqa: BLE001
                    stale.append(client)
            for s in stale:
                self._clients.discard(s)

    def client_count(self) -> int:
        return len(self._clients)
