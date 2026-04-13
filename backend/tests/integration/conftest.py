"""Integration test fixtures — require a real PostgreSQL database.

Set TEST_DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname to enable.
"""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base


@pytest.fixture(scope="session")
def db_engine():
    import os

    url = os.environ["TEST_DATABASE_URL"]
    # 安全检查：拒绝在生产数据库上运行（防 drop_all 误删生产表）
    db_name = url.rsplit("/", 1)[-1].split("?")[0]
    if db_name == "replenish":
        pytest.exit(
            "❌ 拒绝在生产数据库 'replenish' 上运行集成测试！"
            "请使用独立测试库：TEST_DATABASE_URL=...replenish_test",
            returncode=1,
        )
    engine = create_async_engine(url, echo=False)
    return engine


@pytest.fixture(autouse=True)
async def _setup_db(db_engine):
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(db_engine) -> AsyncIterator[AsyncSession]:
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_engine) -> AsyncIterator[AsyncClient]:
    from app.api.deps import db_session as dep_db_session
    from app.api.deps import get_current_session as dep_get_current_session
    from app.main import app

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_db():
        async with session_factory() as session:
            yield session

    async def override_session():
        return {"subject": "test-owner"}

    app.dependency_overrides[dep_db_session] = override_db
    app.dependency_overrides[dep_get_current_session] = override_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def engine_session_factory(db_engine):
    """Patch async_session_factory so run_engine uses the test DB."""
    from unittest.mock import patch

    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    with patch("app.engine.runner.async_session_factory", factory):
        yield factory
