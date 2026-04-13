from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.exceptions import SaihuNetworkError
from app.saihu.client import SaihuClient


class _FakeLimiter:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *args) -> None:
        return None


class _FakeHttp:
    async def post(self, *_args, **_kwargs):
        request = httpx.Request("POST", "https://openapi.sellfox.com/api/shop/pageList.json")
        raise httpx.PoolTimeout("pool timeout", request=request)


@pytest.mark.asyncio
async def test_do_request_maps_pool_timeout_to_saihu_network_error(monkeypatch) -> None:
    import app.saihu.client as client_module

    async def _fake_get_token() -> str:
        return "token"

    async def _fake_ensure_http() -> _FakeHttp:
        return _FakeHttp()

    settings = SimpleNamespace(
        saihu_client_id="cid",
        saihu_client_secret="secret",
        saihu_request_timeout_seconds=30.0,
        saihu_max_retries=3,
    )

    monkeypatch.setattr(client_module, "get_settings", lambda: settings)
    monkeypatch.setattr(
        client_module,
        "get_token_manager",
        lambda: SimpleNamespace(get_token=_fake_get_token),
    )
    monkeypatch.setattr(client_module, "make_nonce", lambda: "1234567890123456")
    monkeypatch.setattr(client_module, "make_timestamp_ms", lambda: "1710000000000")
    monkeypatch.setattr(client_module, "generate_sign", lambda **_kwargs: "sig")
    monkeypatch.setattr(client_module, "get_limiter", lambda _endpoint: _FakeLimiter())

    client = SaihuClient()
    client._ensure_http = _fake_ensure_http  # type: ignore[method-assign]
    client._log = AsyncMock()  # type: ignore[method-assign]

    with pytest.raises(SaihuNetworkError, match="pool timeout"):
        await client._do_request("/api/shop/pageList.json", {}, attempt_no=1)

    client._log.assert_awaited_once()
    log_args = client._log.await_args.args
    assert log_args[0] == "/api/shop/pageList.json"
    assert log_args[6] == "network"
    assert log_args[7] == 1
