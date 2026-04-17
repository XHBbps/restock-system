from app.core.rate_limit import RateLimitMiddleware


def _middleware(**overrides: int) -> RateLimitMiddleware:
    return RateLimitMiddleware(
        app=lambda scope, receive, send: None,
        max_requests=2,
        window_seconds=10,
        max_tracked_clients=overrides.get("max_tracked_clients", 3),
        prune_interval_seconds=overrides.get("prune_interval_seconds", 5),
    )


def test_prune_expired_clients_removes_stale_entries() -> None:
    middleware = _middleware()
    middleware._requests.update(
        {
            "10.0.0.1": [1.0, 2.0],
            "10.0.0.2": [8.0, 9.0],
        }
    )
    middleware._last_seen.update(
        {
            "10.0.0.1": 2.0,
            "10.0.0.2": 9.0,
        }
    )

    middleware._prune_expired(now=20.0)

    assert middleware._requests == {}
    assert middleware._last_seen == {}


def test_prune_expired_clients_keeps_active_timestamps() -> None:
    middleware = _middleware()
    middleware._requests["10.0.0.1"] = [4.0, 12.0, 18.0]
    middleware._last_seen["10.0.0.1"] = 18.0

    middleware._prune_expired(now=20.0)

    assert middleware._requests["10.0.0.1"] == [12.0, 18.0]
    assert middleware._last_seen["10.0.0.1"] == 18.0


def test_ensure_capacity_evicts_oldest_clients() -> None:
    middleware = _middleware(max_tracked_clients=2)
    middleware._requests.update(
        {
            "10.0.0.1": [11.0],
            "10.0.0.2": [12.0],
        }
    )
    middleware._last_seen.update(
        {
            "10.0.0.1": 11.0,
            "10.0.0.2": 12.0,
        }
    )

    middleware._ensure_capacity(required_slots=1)

    assert "10.0.0.1" not in middleware._requests
    assert set(middleware._requests) == {"10.0.0.2"}
