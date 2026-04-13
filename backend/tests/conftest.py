"""Shared pytest fixtures for all test suites."""

import os

import pytest


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Auto-skip integration tests unless TEST_DATABASE_URL is set."""
    if os.environ.get("TEST_DATABASE_URL"):
        return
    skip_integration = pytest.mark.skip(reason="TEST_DATABASE_URL not set")
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(skip_integration)


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Defensively clear get_settings lru_cache before and after each test.

    Prevents pollution from tests that mutate environment variables or patch
    settings attributes in ways that could be cached across tests.
    """
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
