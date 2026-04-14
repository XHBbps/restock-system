"""测试通用异常处理器不泄露堆栈。"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_unhandled_exception_returns_generic_500():
    """模拟一个端点抛出未处理异常，验证返回通用 500 而非堆栈。"""

    @app.get("/test-unhandled-error")
    async def _boom():
        raise RuntimeError("secret internal detail")

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/test-unhandled-error")

        assert resp.status_code == 500
        body = resp.json()
        assert "detail" in body
        assert "secret internal detail" not in body["detail"]
        assert "Traceback" not in resp.text
    finally:
        app.routes[:] = [r for r in app.routes if getattr(r, "path", None) != "/test-unhandled-error"]
