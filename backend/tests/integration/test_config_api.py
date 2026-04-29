"""Integration tests for config APIs."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dashboard_snapshot import DashboardSnapshot
from app.models.global_config import GlobalConfig
from app.models.in_transit import InTransitRecord
from app.models.inventory import InventorySnapshotLatest
from app.models.order import OrderHeader
from app.models.warehouse import Warehouse
from tests.integration.factories import seed_global_config

BEIJING = ZoneInfo("Asia/Shanghai")


@pytest.mark.asyncio
async def test_get_global_config_returns_restock_regions(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_global_config(
        db_session,
        safety_stock_days=18,
        restock_regions=["US", "GB"],
        eu_countries=["UK", "RO"],
    )
    await db_session.commit()

    resp = await client.get("/api/config/global")

    assert resp.status_code == 200
    body = resp.json()
    assert body["safety_stock_days"] == 18
    assert body["restock_regions"] == ["US", "GB"]
    assert body["eu_countries"] == ["GB", "RO"]


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
        json={"safety_stock_days": 30, "eu_countries": ["uk", "RO", "gb"]},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["safety_stock_days"] == 30
    assert body["eu_countries"] == ["GB", "RO"]
    db_session.expire_all()
    saved = (
        await db_session.execute(select(GlobalConfig).where(GlobalConfig.id == 1))
    ).scalar_one()
    assert saved.eu_countries == ["GB", "RO"]


async def _seed_order_header(
    db_session: AsyncSession,
    *,
    order_id: str,
    country_code: str,
    marketplace_id: str | None = None,
    original_country_code: str | None = None,
) -> OrderHeader:
    now = datetime.now(BEIJING)
    row = OrderHeader(
        shop_id="SHOP-001",
        amazon_order_id=order_id,
        marketplace_id=marketplace_id or country_code,
        country_code=country_code,
        original_country_code=original_country_code,
        order_status="Shipped",
        fulfillment_channel="AFN",
        purchase_date=now,
        last_update_date=now,
        last_sync_at=now,
    )
    db_session.add(row)
    await db_session.flush()
    return row


@pytest.mark.asyncio
async def test_patch_global_config_backfills_order_country_to_eu(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_global_config(db_session, eu_countries=[])
    order = await _seed_order_header(
        db_session,
        order_id="111-0000001-0000001",
        country_code="DE",
        marketplace_id="DE",
    )
    order_pk = order.id
    await db_session.commit()

    resp = await client.patch("/api/config/global", json={"eu_countries": ["DE", "FR"]})

    assert resp.status_code == 200
    db_session.expire_all()
    updated = (
        await db_session.execute(select(OrderHeader).where(OrderHeader.id == order_pk))
    ).scalar_one()
    assert updated.country_code == "EU"
    assert updated.marketplace_id == "EU"
    assert updated.original_country_code == "DE"


@pytest.mark.asyncio
async def test_patch_global_config_backfills_alias_country_to_eu(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_global_config(db_session, eu_countries=[])
    order = await _seed_order_header(
        db_session,
        order_id="111-0000005-0000005",
        country_code="UK",
        marketplace_id="UK",
    )
    order_pk = order.id
    await db_session.commit()

    resp = await client.patch("/api/config/global", json={"eu_countries": ["UK"]})

    assert resp.status_code == 200
    assert resp.json()["eu_countries"] == ["GB"]
    db_session.expire_all()
    updated = (
        await db_session.execute(select(OrderHeader).where(OrderHeader.id == order_pk))
    ).scalar_one()
    assert updated.country_code == "EU"
    assert updated.marketplace_id == "EU"
    assert updated.original_country_code == "GB"


@pytest.mark.asyncio
async def test_patch_global_config_restores_order_country_when_removed_from_eu(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_global_config(db_session, eu_countries=["DE", "FR"])
    order = await _seed_order_header(
        db_session,
        order_id="111-0000002-0000002",
        country_code="EU",
        marketplace_id="EU",
        original_country_code="DE",
    )
    order_pk = order.id
    await db_session.commit()

    resp = await client.patch("/api/config/global", json={"eu_countries": ["FR"]})

    assert resp.status_code == 200
    db_session.expire_all()
    updated = (
        await db_session.execute(select(OrderHeader).where(OrderHeader.id == order_pk))
    ).scalar_one()
    assert updated.country_code == "DE"
    assert updated.marketplace_id == "DE"
    assert updated.original_country_code is None


@pytest.mark.asyncio
async def test_patch_global_config_skips_order_backfill_when_eu_countries_unchanged(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_global_config(db_session, eu_countries=["DE"])
    order = await _seed_order_header(
        db_session,
        order_id="111-0000003-0000003",
        country_code="DE",
        marketplace_id="DE",
    )
    order_pk = order.id
    await _seed_dashboard_snapshot(db_session, stale=False)

    resp = await client.patch("/api/config/global", json={"eu_countries": ["DE"]})

    assert resp.status_code == 200
    db_session.expire_all()
    unchanged = (
        await db_session.execute(select(OrderHeader).where(OrderHeader.id == order_pk))
    ).scalar_one()
    snap = await db_session.get(DashboardSnapshot, 1)
    assert unchanged.country_code == "DE"
    assert unchanged.marketplace_id == "DE"
    assert unchanged.original_country_code is None
    assert snap is not None
    assert snap.stale is False


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
async def test_get_country_options_merges_builtin_and_observed_countries(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await seed_global_config(db_session)
    now = datetime.now(BEIJING)
    db_session.add(
        Warehouse(
            id="WH-RO",
            name="Romania Warehouse",
            type=3,
            country="RO",
            last_sync_at=now,
        )
    )
    db_session.add(
        Warehouse(
            id="WH-CZ",
            name="Czech Warehouse",
            type=3,
            country="CZ",
            last_sync_at=now,
        )
    )
    await db_session.flush()
    db_session.add(
        InventorySnapshotLatest(
            commodity_sku="SKU-1",
            warehouse_id="WH-RO",
            country="EU",
            original_country="RO",
            available=1,
            reserved=0,
        )
    )
    db_session.add(
        InTransitRecord(
            saihu_out_record_id="OUT-1",
            target_country="UK",
            original_target_country=None,
            is_in_transit=True,
            last_seen_at=now,
        )
    )
    await _seed_order_header(
        db_session,
        order_id="111-0000004-0000004",
        country_code="EU",
        marketplace_id="EU",
        original_country_code="RO",
    )
    await db_session.commit()

    resp = await client.get("/api/config/country-options")

    assert resp.status_code == 200
    body = resp.json()
    by_code = {item["code"]: item for item in body["items"]}
    assert "UK" not in by_code
    assert by_code["US"]["label"] == "US - 美国"
    assert by_code["GB"]["label"] == "GB - 英国"
    assert by_code["CZ"]["label"] == "CZ - 捷克"
    assert by_code["RO"]["label"] == "RO - 罗马尼亚"
    assert by_code["GB"]["observed"] is True
    assert by_code["CZ"]["observed"] is True
    assert by_code["RO"]["observed"] is True
    assert by_code["RO"]["can_be_eu_member"] is True
    assert by_code["EU"]["can_be_eu_member"] is False
    assert by_code["ZZ"]["can_be_eu_member"] is False
    assert body["unknown_country_codes"] == []


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

    await seed_global_config(db_session, shop_sync_mode="all")
    await _seed_dashboard_snapshot(db_session, stale=False)

    # shop_sync_mode 既不在敏感字段集合内、也不触发 reload_scheduler
    # （后者会通过 async_session_factory 走 prod DATABASE_URL，CI 不可达）。
    resp = await client.patch("/api/config/global", json={"shop_sync_mode": "specific"})
    assert resp.status_code == 200

    db_session.expire_all()
    snap = (
        await db_session.execute(
            DashboardSnapshot.__table__.select().where(DashboardSnapshot.id == 1)
        )
    ).one()
    assert snap.stale is False
