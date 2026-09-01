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


def _client_ip(request: Request) -> str:
    """Best real client IP available, given where this app actually runs:
    uvicorn only ever talks to Caddy on localhost (see entrypoint.sh), so
    request.client.host alone is always 127.0.0.1 in production -- every
    visitor would share one rate-limit bucket instead of getting their own.

    - Fly-Client-IP: set directly by Fly.io's edge, not something a client
      can spoof by sending their own copy of the header -- use it first,
      since that's where this actually deploys.
    - X-Forwarded-For, last entry: covers running behind just Caddy with
      no Fly edge in front (e.g. a plain `docker run` locally) -- Caddy
      appends its own observed peer to this header rather than replacing
      it, so the last entry is what Caddy itself saw, not whatever a
      client tried to inject earlier in the list.
    - request.client.host: no proxy in front at all (dev, `uvicorn` run
      directly) -- the real peer address.
    """
    fly_ip = request.headers.get("fly-client-ip")
    if fly_ip:
        return fly_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"


def rate_limit_dependency(limiter: RateLimiter):
    """Build a FastAPI dependency that enforces `limiter` keyed by client IP."""

    def dependency(request: Request):
        client_ip = _client_ip(request)
        if not limiter.allow(client_ip):
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests -- max {limiter.max_requests} per {int(limiter.window_seconds)}s. Slow down.",
            )

    return dependency
