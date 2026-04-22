"""Integration tests for config APIs."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.factories import seed_global_config


@pytest.mark.asyncio
async def test_get_global_config_returns_restock_regions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_global_config(
        db_session,
        safety_stock_days=18,
        restock_regions=["US", "GB"],
        eu_countries=["DE", "FR"],
    )
    await db_session.commit()

    resp = await client.get("/api/config/global")

    assert resp.status_code == 200
    body = resp.json()
    assert body["safety_stock_days"] == 18
    assert body["restock_regions"] == ["US", "GB"]
    assert body["eu_countries"] == ["DE", "FR"]


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
async def test_patch_global_config_updates_safety_stock_and_eu_countries(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_global_config(db_session)
    await db_session.commit()

    resp = await client.patch(
        "/api/config/global",
        json={"safety_stock_days": 30, "eu_countries": ["de", " FR ", "", "de"]},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["safety_stock_days"] == 30
    assert body["eu_countries"] == ["DE", "FR"]


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


async def _seed_dashboard_snapshot(db_session: AsyncSession, *, stale: bool = False) -> None:
    from app.models.dashboard_snapshot import DashboardSnapshot

    existing = (
        await db_session.execute(
            DashboardSnapshot.__table__.select().where(DashboardSnapshot.id == 1)
        )
    ).first()
    if existing is None:
        db_session.add(DashboardSnapshot(id=1, status="empty", payload=None, stale=stale))
    else:
        await db_session.execute(
            DashboardSnapshot.__table__.update()
            .where(DashboardSnapshot.id == 1)
            .values(stale=stale)
        )
    await db_session.commit()


@pytest.mark.asyncio
async def test_patch_global_config_flips_dashboard_stale_on_sensitive_change(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from app.models.dashboard_snapshot import DashboardSnapshot

    await seed_global_config(db_session, target_days=60, lead_time_days=50, buffer_days=10)
    await _seed_dashboard_snapshot(db_session, stale=False)

    resp = await client.patch("/api/config/global", json={"buffer_days": 30})
    assert resp.status_code == 200

    db_session.expire_all()
    snap = (
        await db_session.execute(
            DashboardSnapshot.__table__.select().where(DashboardSnapshot.id == 1)
        )
    ).one()
    assert snap.stale is True


@pytest.mark.asyncio
async def test_patch_global_config_does_not_flip_stale_when_value_unchanged(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from app.models.dashboard_snapshot import DashboardSnapshot

    await seed_global_config(db_session, buffer_days=30)
    await _seed_dashboard_snapshot(db_session, stale=False)

    # 传入的 buffer_days 与现值相同，不应置 stale
    resp = await client.patch("/api/config/global", json={"buffer_days": 30})
    assert resp.status_code == 200

    db_session.expire_all()
    snap = (
        await db_session.execute(
            DashboardSnapshot.__table__.select().where(DashboardSnapshot.id == 1)
        )
    ).one()
    assert snap.stale is False


@pytest.mark.asyncio
async def test_patch_global_config_does_not_flip_stale_for_non_sensitive_field(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    from app.models.dashboard_snapshot import DashboardSnapshot

    await seed_global_config(db_session, sync_interval_minutes=60)
    await _seed_dashboard_snapshot(db_session, stale=False)

    # sync_interval_minutes 不在敏感字段集合内
    resp = await client.patch("/api/config/global", json={"sync_interval_minutes": 30})
    assert resp.status_code == 200

    db_session.expire_all()
    snap = (
        await db_session.execute(
            DashboardSnapshot.__table__.select().where(DashboardSnapshot.id == 1)
        )
    ).one()
    assert snap.stale is False
