"""Test data factories for integration tests.

Each helper inserts one row (or a cluster of related rows) into the test DB
and returns the created ORM instance(s).  All timestamps use the Beijing
timezone so they match the application's storage convention.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.global_config import GlobalConfig
from app.models.inventory import InventorySnapshotLatest
from app.models.order import OrderDetail, OrderHeader, OrderItem
from app.models.product_listing import ProductListing
from app.models.role import Role
from app.models.sku import SkuConfig
from app.models.sys_user import SysUser
from app.models.warehouse import Warehouse

BEIJING = ZoneInfo("Asia/Shanghai")

# ---------------------------------------------------------------------------
# Individual factories
# ---------------------------------------------------------------------------


async def seed_test_user(db: AsyncSession, user_id: int = 1) -> SysUser:
    """Seed a superadmin role + sys_user matching the conftest override_user
    (id=1, username=test-owner). Idempotent: skips if row already exists."""
    role = (await db.execute(Role.__table__.select().where(Role.id == user_id))).first()
    if role is None:
        db.add(Role(id=user_id, name="superadmin-test", description="", is_superadmin=True))
        await db.flush()
    existing = (
        await db.execute(SysUser.__table__.select().where(SysUser.id == user_id))
    ).first()
    if existing is None:
        user = SysUser(
            id=user_id,
            username="test-owner",
            display_name="Test Owner",
            password_hash="placeholder",
            role_id=user_id,
            is_active=True,
            perm_version=0,
        )
        db.add(user)
        await db.flush()
        return user
    # Re-fetch the ORM instance for callers that need it
    return (
        await db.execute(SysUser.__table__.select().where(SysUser.id == user_id))
    ).one()  # type: ignore[return-value]


async def seed_global_config(db: AsyncSession, **overrides) -> GlobalConfig:
    """Seed the singleton global_config row (id=1).

    All columns have server defaults or application defaults; only
    ``login_password_hash`` is required (no default).  Pass overrides to
    customise any column.
    """
    defaults: dict = {
        "id": 1,
        "buffer_days": 30,
        "target_days": 60,
        "lead_time_days": 50,
        "safety_stock_days": 15,
        "restock_regions": [],
        "eu_countries": [],
        "sync_interval_minutes": 60,
        "scheduler_enabled": True,
        "shop_sync_mode": "all",
        "login_password_hash": "placeholder_hash",
    }
    defaults.update(overrides)
    obj = GlobalConfig(**defaults)
    db.add(obj)
    await db.flush()
    return obj


async def seed_sku(
    db: AsyncSession,
    sku: str,
    enabled: bool = True,
    lead_time_days: int | None = None,
) -> SkuConfig:
    """Seed one row in sku_config."""
    obj = SkuConfig(
        commodity_sku=sku,
        enabled=enabled,
        lead_time_days=lead_time_days,
    )
    db.add(obj)
    await db.flush()
    return obj


async def seed_warehouse(
    db: AsyncSession,
    warehouse_id: str,
    name: str,
    wtype: int,
    country: str | None = None,
) -> Warehouse:
    """Seed one row in warehouse.

    ``wtype`` mirrors the saihu convention: 1=domestic, 3=overseas, etc.
    ``last_sync_at`` is required (NOT NULL, no server default).
    """
    obj = Warehouse(
        id=warehouse_id,
        name=name,
        type=wtype,
        country=country,
        last_sync_at=datetime.now(BEIJING),
    )
    db.add(obj)
    await db.flush()
    return obj


async def seed_inventory(
    db: AsyncSession,
    sku: str,
    warehouse_id: str,
    country: str | None = None,
    available: int = 0,
    reserved: int = 0,
) -> InventorySnapshotLatest:
    """Seed one row in inventory_snapshot_latest."""
    obj = InventorySnapshotLatest(
        commodity_sku=sku,
        warehouse_id=warehouse_id,
        country=country,
        available=available,
        reserved=reserved,
    )
    db.add(obj)
    await db.flush()
    return obj


async def seed_order(
    db: AsyncSession,
    shop_id: str,
    order_id: str,
    country: str,
    sku: str,
    qty_shipped: int,
    purchase_date: datetime,
    postal_code: str | None = None,
) -> tuple[OrderHeader, OrderItem, OrderDetail]:
    """Seed an order_header + one order_item + order_detail row.

    Returns a (header, item, detail) tuple.
    """
    now = datetime.now(BEIJING)

    header = OrderHeader(
        shop_id=shop_id,
        amazon_order_id=order_id,
        marketplace_id="US" if country == "US" else "UNKNOWN",
        country_code=country,
        order_status="Shipped",
        fulfillment_channel="AFN",
        purchase_date=purchase_date,
        last_update_date=purchase_date,
        last_sync_at=now,
    )
    db.add(header)
    await db.flush()  # populate header.id

    item = OrderItem(
        order_id=header.id,
        order_item_id=f"{order_id}-item-1",
        commodity_sku=sku,
        quantity_ordered=qty_shipped,
        quantity_shipped=qty_shipped,
    )
    db.add(item)

    detail = OrderDetail(
        shop_id=shop_id,
        amazon_order_id=order_id,
        postal_code=postal_code,
        country_code=country,
        fetched_at=now,
    )
    db.add(detail)

    await db.flush()
    return header, item, detail


async def seed_product_listing(
    db: AsyncSession,
    sku: str,
    commodity_id: str,
    shop_id: str,
    marketplace_id: str = "US_MKT",
) -> ProductListing:
    """Seed one row in product_listing.

    ``last_sync_at`` is required (NOT NULL, no server default).
    """
    obj = ProductListing(
        commodity_sku=sku,
        commodity_id=commodity_id,
        shop_id=shop_id,
        marketplace_id=marketplace_id,
        seller_sku=f"{sku}-seller",
        is_matched=True,
        online_status="active",
        last_sync_at=datetime.now(BEIJING),
    )
    db.add(obj)
    await db.flush()
    return obj


# ---------------------------------------------------------------------------
# Composite seed helper
# ---------------------------------------------------------------------------

_DEFAULT_SKU = "TEST-SKU-001"
_LOCAL_WH_ID = "WH-LOCAL-CN"
_OVERSEAS_WH_ID = "WH-FBA-US"
_SHOP_ID = "SHOP-001"
_ORDER_ID = "111-0000001-0000001"
_COMMODITY_ID = "COMM-001"


async def seed_minimum_dataset(
    db: AsyncSession,
    today: date,
) -> dict:
    """Seed the smallest dataset that allows the engine to run end-to-end.

    Creates:
      - 1 global_config (id=1)
      - 1 sku_config (enabled, no custom lead_time)
      - 1 domestic warehouse (CN, type=1)
      - 1 US overseas warehouse (US, type=3)
      - US overseas inventory  (available=50)
      - Domestic inventory      (available=20)
      - 1 US order 15 days ago  (qty_shipped=5, with postal_code)
      - 1 product_listing entry

    Returns a dict of all created objects for assertions.
    """
    # 5 days before today (falls within 7-day, 14-day, and 30-day windows)
    from datetime import timedelta

    purchase_dt = datetime(
        today.year, today.month, today.day, 12, 0, 0, tzinfo=BEIJING
    ) - timedelta(days=5)

    config = await seed_global_config(db)
    sku = await seed_sku(db, _DEFAULT_SKU, enabled=True, lead_time_days=None)
    wh_local = await seed_warehouse(db, _LOCAL_WH_ID, "国内本地仓", wtype=1, country="CN")
    wh_us = await seed_warehouse(db, _OVERSEAS_WH_ID, "美国FBA仓", wtype=3, country="US")
    # Set overseas stock to 0 so country_qty is positive (velocity > 0 → replenishment needed)
    inv_us = await seed_inventory(db, _DEFAULT_SKU, _OVERSEAS_WH_ID, country="US", available=0)
    # Set local stock to 0 so total_qty is also positive
    inv_local = await seed_inventory(db, _DEFAULT_SKU, _LOCAL_WH_ID, country="CN", available=0)
    header, item, detail = await seed_order(
        db,
        shop_id=_SHOP_ID,
        order_id=_ORDER_ID,
        country="US",
        sku=_DEFAULT_SKU,
        qty_shipped=10,
        purchase_date=purchase_dt,
        postal_code="90001",
    )
    listing = await seed_product_listing(db, _DEFAULT_SKU, _COMMODITY_ID, _SHOP_ID)

    await db.commit()

    return {
        "config": config,
        "sku": sku,
        "wh_local": wh_local,
        "wh_us": wh_us,
        "inv_us": inv_us,
        "inv_local": inv_local,
        "order_header": header,
        "order_item": item,
        "order_detail": detail,
        "listing": listing,
    }
