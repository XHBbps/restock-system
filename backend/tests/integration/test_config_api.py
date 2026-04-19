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


@pytest.mark.asyncio
async def test_patch_global_config_rejects_target_days_less_than_lead_time(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_global_config(db_session, target_days=60, lead_time_days=50)
    await db_session.commit()

    resp = await client.patch("/api/config/global", json={"target_days": 40})

    assert resp.status_code == 400
    assert resp.json()["message"] == "目标库存天数不能小于采购提前期"
