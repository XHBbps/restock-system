"""测试只读会话不执行 COMMIT。"""

from contextlib import suppress
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_get_db_readonly_does_not_commit():
    """get_db_readonly 应 rollback 而非 commit。"""
    from app.db.session import get_db_readonly

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("app.db.session.async_session_factory", return_value=mock_session):
        gen = get_db_readonly()
        session = await gen.__anext__()
        assert session is mock_session
        with suppress(StopAsyncIteration):
            await gen.__anext__()

    mock_session.rollback.assert_awaited_once()
    mock_session.commit.assert_not_awaited()
