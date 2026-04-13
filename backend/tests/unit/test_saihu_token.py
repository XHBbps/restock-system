from types import SimpleNamespace

import httpx
import pytest

from app.core.exceptions import SaihuAPIError
from app.saihu.token import TokenManager


class _FakeDb:
    async def execute(self, _stmt):
        return None

    async def commit(self) -> None:
        return None


class _FakeSessionFactory:
    def __call__(self) -> "_FakeSessionFactory":
        return self

    async def __aenter__(self) -> _FakeDb:
        return _FakeDb()

    async def __aexit__(self, *args) -> None:
        return None


class _FakeResponse:
    def __init__(self, status_code: int, body):
        self.status_code = status_code
        self._body = body

    def json(self):
        if isinstance(self._body, Exception):
            raise self._body
        return self._body


@pytest.mark.asyncio
async def test_refresh_retries_request_error_and_succeeds(monkeypatch) -> None:
    import app.saihu.token as token_module

    settings = SimpleNamespace(
        saihu_base_url="https://openapi.sellfox.com",
        saihu_client_id="cid",
        saihu_client_secret="secret",
        saihu_request_timeout_seconds=30.0,
        saihu_max_retries=2,
    )
    calls = {"count": 0}

    class _FakeTokenClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def get(self, url: str, params):
            calls["count"] += 1
            if calls["count"] == 1:
                request = httpx.Request("GET", url)
                raise httpx.PoolTimeout("pool timeout", request=request)
            return _FakeResponse(
                200,
                {
                    "code": 0,
                    "data": {
                        "access_token": "fresh-token",
                        "expires_in": 60000,
                    },
                },
            )

    monkeypatch.setattr(token_module, "get_settings", lambda: settings)
    monkeypatch.setattr(token_module, "async_session_factory", _FakeSessionFactory())
    monkeypatch.setattr(token_module.httpx, "AsyncClient", _FakeTokenClient)

    manager = TokenManager()
    token = await manager._refresh()

    assert token == "fresh-token"
    assert calls["count"] == 2


@pytest.mark.asyncio
async def test_refresh_wraps_invalid_json_as_saihu_api_error(monkeypatch) -> None:
    import app.saihu.token as token_module

    settings = SimpleNamespace(
        saihu_base_url="https://openapi.sellfox.com",
        saihu_client_id="cid",
        saihu_client_secret="secret",
        saihu_request_timeout_seconds=30.0,
        saihu_max_retries=2,
    )

    class _FakeTokenClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def get(self, url: str, params):
            return _FakeResponse(200, ValueError("bad json"))

    monkeypatch.setattr(token_module, "get_settings", lambda: settings)
    monkeypatch.setattr(token_module, "async_session_factory", _FakeSessionFactory())
    monkeypatch.setattr(token_module.httpx, "AsyncClient", _FakeTokenClient)

    manager = TokenManager()
    with pytest.raises(SaihuAPIError, match="非 JSON"):
        await manager._refresh()
