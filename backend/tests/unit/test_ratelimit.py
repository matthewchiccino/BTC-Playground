"""RateLimiter and client-IP selection. The IP logic matters more than it
looks: get it wrong and either every visitor shares one bucket (always
127.0.0.1 behind Caddy) or a client can dodge the limit by spoofing a header.
"""
import pytest
from fastapi import HTTPException
from starlette.requests import Request

import ratelimit
from ratelimit import RateLimiter, _client_ip, rate_limit_dependency


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(ratelimit.time, "monotonic", c)
    return c


def make_request(headers: dict[str, str] | None = None, client: tuple[str, int] | None = ("9.9.9.9", 1234)) -> Request:
    return Request({
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": client,
    })


class TestRateLimiter:
    def test_allows_up_to_max_then_blocks(self, clock):
        rl = RateLimiter(max_requests=3, window_seconds=10)
        assert [rl.allow("a") for _ in range(4)] == [True, True, True, False]

    def test_window_slides(self, clock):
        rl = RateLimiter(max_requests=2, window_seconds=10)
        assert rl.allow("a") and rl.allow("a")
        assert not rl.allow("a")
        clock.now += 10.01
        assert rl.allow("a")

    def test_keys_are_independent(self, clock):
        rl = RateLimiter(max_requests=1, window_seconds=10)
        assert rl.allow("a")
        assert not rl.allow("a")
        assert rl.allow("b")

    def test_rejected_attempts_do_not_extend_the_window(self, clock):
        # Hammering while blocked must not keep you blocked forever.
        rl = RateLimiter(max_requests=1, window_seconds=10)
        assert rl.allow("a")
        for _ in range(50):
            clock.now += 0.1
            assert not rl.allow("a")
        clock.now += 6  # now 11s after the one accepted hit
        assert rl.allow("a")


class TestClientIp:
    def test_fly_header_wins(self):
        req = make_request({"fly-client-ip": " 1.1.1.1 ", "x-forwarded-for": "2.2.2.2"})
        assert _client_ip(req) == "1.1.1.1"

    def test_forwarded_for_uses_last_entry_not_first(self):
        # Caddy appends the peer it actually saw; earlier entries are client-supplied.
        req = make_request({"x-forwarded-for": "6.6.6.6, 7.7.7.7, 3.3.3.3"})
        assert _client_ip(req) == "3.3.3.3"

    def test_falls_back_to_socket_peer(self):
        assert _client_ip(make_request()) == "9.9.9.9"

    def test_unknown_when_no_peer(self):
        assert _client_ip(make_request(client=None)) == "unknown"


class TestDependency:
    def test_raises_429_with_limits_in_message(self, clock):
        dep = rate_limit_dependency(RateLimiter(max_requests=1, window_seconds=60))
        req = make_request()
        dep(req)
        with pytest.raises(HTTPException) as exc:
            dep(req)
        assert exc.value.status_code == 429
        assert "1 per 60s" in exc.value.detail

    def test_buckets_by_client_ip(self, clock):
        dep = rate_limit_dependency(RateLimiter(max_requests=1, window_seconds=60))
        dep(make_request({"fly-client-ip": "1.1.1.1"}))
        dep(make_request({"fly-client-ip": "2.2.2.2"}))  # different visitor: not limited
