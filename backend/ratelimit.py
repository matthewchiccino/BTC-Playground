"""In-memory per-IP rate limiting. No external dependency, no persistence --
counters live only as long as the process does, which is fine for a
single-instance demo app with no state to protect beyond "don't let one
visitor hang the shared node for everyone else."
"""
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class RateLimiter:
    """Fixed-size-per-key sliding window. The outer dict grows one entry per
    distinct IP seen over the process lifetime -- fine at demo-app scale;
    revisit with a TTL sweep if this ever needs to survive real traffic.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > self.window_seconds:
                hits.popleft()
            if len(hits) >= self.max_requests:
                return False
            hits.append(now)
            return True


def rate_limit_dependency(limiter: RateLimiter):
    """Build a FastAPI dependency that enforces `limiter` keyed by client IP."""

    def dependency(request: Request):
        client_ip = request.client.host if request.client else "unknown"
        if not limiter.allow(client_ip):
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests -- max {limiter.max_requests} per {int(limiter.window_seconds)}s. Slow down.",
            )

    return dependency
