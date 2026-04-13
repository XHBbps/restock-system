import pytest

import app.main as main_module


class _FakeSession:
    def __init__(self, should_fail: bool) -> None:
        self.should_fail = should_fail

    async def execute(self, _stmt) -> None:
        if self.should_fail:
            raise RuntimeError("db down")


class _FakeSessionContext:
    def __init__(self, should_fail: bool) -> None:
        self.should_fail = should_fail

    async def __aenter__(self) -> _FakeSession:
        return _FakeSession(self.should_fail)

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


@pytest.mark.asyncio
async def test_readyz_returns_ok_when_database_is_available(monkeypatch) -> None:
    monkeypatch.setattr(
        main_module,
        "async_session_factory",
        lambda: _FakeSessionContext(False),
    )

    async def fake_background_ready():
        return True, {"worker": True, "reaper": True, "scheduler": True}

    monkeypatch.setattr(main_module, "_background_ready", fake_background_ready)

    response = await main_module.readyz()

    assert response.status_code == 200
    assert response.body == b'{"status":"ok"}'


@pytest.mark.asyncio
async def test_readyz_returns_503_when_database_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        main_module,
        "async_session_factory",
        lambda: _FakeSessionContext(True),
    )

    response = await main_module.readyz()

    assert response.status_code == 503
    assert response.body == b'{"status":"error","reason":"database_unavailable"}'


@pytest.mark.asyncio
async def test_readyz_returns_503_when_background_service_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        main_module,
        "async_session_factory",
        lambda: _FakeSessionContext(False),
    )

    async def fake_background_ready():
        return False, {"worker": True, "reaper": False, "scheduler": True}

    monkeypatch.setattr(main_module, "_background_ready", fake_background_ready)

    response = await main_module.readyz()

    assert response.status_code == 503
    assert b'"reason":"background_services_unavailable"' in response.body


@pytest.mark.asyncio
async def test_readyz_allows_disabled_background_roles(monkeypatch) -> None:
    monkeypatch.setattr(
        main_module,
        "async_session_factory",
        lambda: _FakeSessionContext(False),
    )

    async def fake_background_ready():
        return True, {"worker": True, "reaper": True, "scheduler": True}

    monkeypatch.setattr(main_module, "_background_ready", fake_background_ready)

    response = await main_module.readyz()

    assert response.status_code == 200
    assert response.body == b'{"status":"ok"}'
