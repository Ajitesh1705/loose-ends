"""Tiny in-memory sliding-window rate limiter for the public ingest endpoint.

Per-instance only (state lives in the process) — fine for a single-instance demo behind
one Cloud Run container. For real multi-instance scale this would move to Redis or a
Postgres counter; called out in the README. Its whole job here is to keep a public link
with a real OpenAI key behind it from being trivially abused.
"""

import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    def __init__(self, max_events: int, window_seconds: float = 60.0):
        self.max_events = max_events
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        q = self._hits[key]
        cutoff = now - self.window
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= self.max_events:
            return False
        q.append(now)
        return True
