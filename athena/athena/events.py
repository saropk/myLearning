"""The `/api/events` broadcast bus.

The daemon owns state; every client (Aegis now, the voice pipeline in phase 2) learns
about changes here. Slow subscribers are dropped from rather than allowed to back up the
daemon — a stalled browser tab must never wedge Athena.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass

QUEUE_MAX = 64


@dataclass(frozen=True)
class Event:
    name: str  # "state" | "notice"
    data: dict[str, object]

    def to_sse(self) -> str:
        return f"event: {self.name}\ndata: {json.dumps(self.data)}\n\n"


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[Event]] = set()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def publish(self, name: str, data: dict[str, object]) -> None:
        """Non-blocking fan-out. Safe to call from anywhere in the event loop."""
        event = Event(name, data)
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop the oldest and retry once; a wedged client loses history, not the daemon.
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
                with contextlib.suppress(asyncio.QueueFull):
                    queue.put_nowait(event)

    @contextlib.contextmanager
    def subscribe(self):  # noqa: ANN201 - contextmanager of a private queue type
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=QUEUE_MAX)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)

    async def stream(
        self, first: dict[str, object], heartbeat_s: float = 15.0
    ) -> AsyncIterator[str]:
        """SSE body: the current snapshot, then every change, then keep-alive comments."""
        with self.subscribe() as queue:
            yield Event("state", first).to_sse()
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=heartbeat_s)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield event.to_sse()
