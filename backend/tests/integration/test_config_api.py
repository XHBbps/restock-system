"""Integration tests for config APIs."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.factories import seed_global_config


@pytest.mark.asyncio
async def test_get_global_config_returns_restock_regions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_global_config(db_session, restock_regions=["US", "GB"])
    await db_session.commit()

    resp = await client.get("/api/config/global")

    assert resp.status_code == 200
    assert resp.json()["restock_regions"] == ["US", "GB"]


@pytest.mark.asyncio
async def test_patch_global_config_normalizes_restock_regions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_global_config(db_session)
    await db_session.commit()

    resp = await client.patch(
        "/api/config/global",
        json={"restock_regions": ["us", " GB ", "", "us"]},
    )

    assert resp.status_code == 200
    assert resp.json()["restock_regions"] == ["US", "GB"]


@pytest.mark.asyncio
async def test_patch_global_config_accepts_empty_restock_regions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_global_config(db_session, restock_regions=["US"])
    await db_session.commit()

    resp = await client.patch("/api/config/global", json={"restock_regions": []})

    assert resp.status_code == 200
    assert resp.json()["restock_regions"] == []
