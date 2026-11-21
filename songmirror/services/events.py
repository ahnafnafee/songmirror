"""EventBus — fan-out of engine log events to SSE subscribers.

The engine emits `logs.Event`s from *worker threads* (one-way passes run one
thread per target). `asyncio.Queue` is not thread-safe, so every publish is
marshalled onto the event loop with `call_soon_threadsafe`. A small ring buffer
lets a late/reconnecting browser backfill the current pass.

Services tier: it imports the leaf `logs` module (never the reverse).
"""

import asyncio
import threading
from collections import deque

from ..engine.logs import Event, set_sink


class EventBus:
    def __init__(self, ring: int = 500, *, queue_size: int = 500, max_subscribers: int = 32):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subs: set[asyncio.Queue] = set()
        self._ring: deque[Event] = deque(maxlen=ring)
        self._queue_size = max(1, queue_size)
        self._max_subscribers = max_subscribers
        self._pending = deque(maxlen=self._queue_size)
        self._pending_lock = threading.Lock()
        self._scheduled = False

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Capture the running loop at app startup; publishes route through it."""
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        if len(self._subs) >= self._max_subscribers:
            raise RuntimeError("Too many event streams. Close another stream and retry.")
        q: asyncio.Queue = asyncio.Queue(maxsize=self._queue_size)
        self._subs.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self._subs.discard(q)

    def recent(self) -> list[Event]:
        return list(self._ring)

    def publish(self, e: Event) -> None:
        """Thread-safe: callable from any worker thread. No-op until a loop is
        bound (e.g. a pass running before the web app started)."""
        loop = self._loop
        if loop is None:
            return
        with self._pending_lock:
            self._pending.append(e)
            if not self._scheduled:
                self._scheduled = True
                loop.call_soon_threadsafe(self._drain)

    def _drain(self):
        with self._pending_lock:
            batch = list(self._pending)
            self._pending.clear()
            self._scheduled = False
        for event in batch:
            self._deliver(event)

    def _deliver(self, e: Event) -> None:
        # Runs on the loop thread — the only place _subs/_ring are mutated.
        self._ring.append(e)
        for q in self._subs:
            try:
                q.put_nowait(e)
            except asyncio.QueueFull:
                q.get_nowait()  # Keep latest progress for a slow reader.
                q.put_nowait(e)

    def attach_to_logs(self) -> None:
        """Route every engine log event into this bus."""
        set_sink(self.publish)
