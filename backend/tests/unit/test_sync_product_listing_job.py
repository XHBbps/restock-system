from datetime import datetime
from typing import Any

import pytest

from app.core.exceptions import ValidationFailed


class _FakeContext:
    def __init__(self) -> None:
        self.events: list[tuple[str | None, str | None, int | None]] = []

    async def progress(
        self,
        *,
        current_step: str | None = None,
        step_detail: str | None = None,
        total_steps: int | None = None,
    ) -> None:
        self.events.append((current_step, step_detail, total_steps))


class _FakeDb:
    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def execute(self, stmt: Any) -> Any:
        self.statements.append(stmt)
        return _ScalarResult([])

    async def commit(self) -> None:
        return None


class _ScalarResult:
    def __init__(self, values: list[Any]) -> None:
        self._values = values

    def scalars(self) -> "_ScalarResult":
        return self

    def all(self) -> list[Any]:
        return self._values

    def one_or_none(self) -> Any:
        return self._values[0] if self._values else None


class _FakeMappingsResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def all(self) -> list[dict[str, object]]:
        return self._rows


class _FakeExecuteResult:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def mappings(self) -> _FakeMappingsResult:
        return _FakeMappingsResult(self._rows)


class _FakeSchemaDb(_FakeDb):
    def __init__(self, rows: list[dict[str, object]]) -> None:
        super().__init__()
        self._rows = rows

    async def execute(self, _stmt) -> _FakeExecuteResult:
        return _FakeExecuteResult(self._rows)


class _FakeSessionFactory:
    def __init__(self, dbs: list[_FakeDb]) -> None:
        self._dbs = list(dbs)

    def __call__(self) -> "_FakeSessionFactory":
        return self

    async def __aenter__(self) -> _FakeDb:
        return self._dbs.pop(0)

    async def __aexit__(self, *args: Any) -> None:
        return None


@pytest.mark.asyncio
async def test_sync_product_listing_job_syncs_commodity_then_listing(monkeypatch) -> None:
    import app.sync.product_listing as product_listing_module

    factory = _FakeSessionFactory(
        [_FakeDb(), _FakeSchemaDb(_nullable_schema_rows()), _FakeDb(), _FakeDb(), _FakeDb()]
    )
    started = datetime(2026, 4, 13, 23, 0, 0)
    call_args: list[tuple[bool, bool, bool]] = []
    commodity_rows: list[dict[str, object]] = []
    listing_rows: list[dict[str, object]] = []
    created_commodity_counts: list[int] = []
    created_listing_counts: list[int] = []

    async def _fake_mark_sync_running(_db, _job_name: str) -> datetime:
        return started

    async def _fake_mark_sync_success(_db, _job_name: str, _started: datetime) -> None:
        return None

    async def _fake_list_commodities(*, on_page=None):
        if on_page is not None:
            await on_page(1, 2, 1)
        yield {"sku": "SKU-1", "name": "Product 1"}

    async def _fake_upsert_commodity(_db, raw: dict[str, object]) -> bool:
        commodity_rows.append(raw)
        return True

    async def _fake_backfill_commodity(_db) -> int:
        created_commodity_counts.append(1)
        return 1

    async def _fake_list_product_listings(*, only_matched: bool, only_active: bool, on_page=None):
        call_args.append((only_matched, only_active, on_page is not None))
        if on_page is not None:
            await on_page(1, 3, 1)
        yield {"shopId": "shop-1", "marketplaceId": "US", "sku": "SELLER-1"}

    async def _fake_upsert_listing(
        _db,
        raw: dict[str, object],
        _eu_countries: set[str],
    ) -> None:
        listing_rows.append(raw)

    async def _fake_backfill_listing(_db) -> int:
        created_listing_counts.append(0)
        return 0

    async def _fake_load_eu_countries(_db) -> set[str]:
        return set()

    monkeypatch.setattr(product_listing_module, "async_session_factory", factory)
    monkeypatch.setattr(product_listing_module, "mark_sync_running", _fake_mark_sync_running)
    monkeypatch.setattr(product_listing_module, "mark_sync_success", _fake_mark_sync_success)
    monkeypatch.setattr(product_listing_module, "list_commodities", _fake_list_commodities)
    monkeypatch.setattr(product_listing_module, "_upsert_commodity", _fake_upsert_commodity)
    monkeypatch.setattr(
        product_listing_module,
        "_backfill_sku_configs_from_commodities",
        _fake_backfill_commodity,
    )
    monkeypatch.setattr(product_listing_module, "list_product_listings", _fake_list_product_listings)
    monkeypatch.setattr(product_listing_module, "_upsert_listing", _fake_upsert_listing)
    monkeypatch.setattr(product_listing_module, "load_eu_countries", _fake_load_eu_countries)
    monkeypatch.setattr(
        product_listing_module,
        "_backfill_sku_configs_from_synced_listings",
        _fake_backfill_listing,
    )

    ctx = _FakeContext()
    await product_listing_module.sync_product_listing_job(ctx)  # type: ignore[arg-type]

    assert commodity_rows == [{"sku": "SKU-1", "name": "Product 1"}]
    assert call_args == [(False, False, True)]
    assert listing_rows == [{"shopId": "shop-1", "marketplaceId": "US", "sku": "SELLER-1"}]
    assert created_commodity_counts == [1]
    assert created_listing_counts == [0]
    assert ctx.events[0][0] == "同步商品主数据"
    assert ctx.events[-1][0] == "完成"
    assert "商品主数据 1 条" in (ctx.events[-1][1] or "")


@pytest.mark.asyncio
async def test_schema_guard_rejects_legacy_not_null_columns() -> None:
    import app.sync.product_listing as product_listing_module

    db = _FakeSchemaDb(
        [
            {"column_name": "commodity_sku", "is_nullable": "NO"},
            {"column_name": "commodity_id", "is_nullable": "NO"},
        ]
    )

    with pytest.raises(ValidationFailed, match="alembic upgrade head"):
        await product_listing_module._ensure_product_listing_schema_compatible(db)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_upsert_commodity_skips_blank_sku_and_maps_fields() -> None:
    import app.sync.product_listing as product_listing_module

    db = _FakeDb()
    assert await product_listing_module._upsert_commodity(db, {"sku": ""}) is False  # type: ignore[arg-type]

    assert await product_listing_module._upsert_commodity(  # type: ignore[arg-type]
        db,
        {
            "id": "CID-1",
            "sku": "SKU-1",
            "name": "Name",
            "state": "active",
            "isGroup": "true",
            "imgUrl": "https://example.test/a.png",
            "purchaseDays": "12",
            "childSkus": ["A", "B"],
        },
    ) is True

    params = db.statements[-1].compile().params
    assert params["sku"] == "SKU-1"
    assert params["commodity_id"] == "CID-1"
    assert params["name"] == "Name"
    assert params["state"] == "active"
    assert params["is_group"] is True
    assert params["purchase_days"] == 12
    assert params["child_skus"] == ["A", "B"]


@pytest.mark.asyncio
async def test_insert_missing_sku_configs_defaults_disabled() -> None:
    import app.sync.product_listing as product_listing_module

    class _ExistingSkuDb(_FakeDb):
        async def execute(self, stmt):
            self.statements.append(stmt)
            if getattr(stmt, "table", None) is not None and stmt.table.name == "sku_config":
                return _ScalarResult([])
            return _ScalarResult(["SKU-2"])

    db = _ExistingSkuDb()
    created = await product_listing_module._insert_missing_sku_configs(  # type: ignore[arg-type]
        db, ["SKU-1", "SKU-2"], enabled=False
    )

    params = db.statements[-1].compile().params
    assert created == 1
    assert params["commodity_sku_m0"] == "SKU-1"
    assert params["enabled_m0"] is False


@pytest.mark.asyncio
async def test_sync_product_listing_job_fails_fast_on_legacy_schema(monkeypatch) -> None:
    import app.sync.product_listing as product_listing_module

    factory = _FakeSessionFactory([_FakeDb(), _FakeDb(), _FakeDb()])
    started = datetime(2026, 4, 13, 23, 0, 0)
    errors: list[str] = []
    called = False

    async def _fake_mark_sync_running(_db, _job_name: str) -> datetime:
        return started

    async def _fake_mark_sync_failed(_db, _job_name: str, error: str) -> None:
        errors.append(error)

    async def _fake_schema_check(_db) -> None:
        raise ValidationFailed("schema drift: run `alembic upgrade head`")

    async def _fake_list_commodities(*, on_page=None):
        nonlocal called
        called = True
        yield {"sku": "SKU-1", "name": "Product 1"}

    monkeypatch.setattr(product_listing_module, "async_session_factory", factory)
    monkeypatch.setattr(product_listing_module, "mark_sync_running", _fake_mark_sync_running)
    monkeypatch.setattr(product_listing_module, "mark_sync_failed", _fake_mark_sync_failed)
    monkeypatch.setattr(
        product_listing_module,
        "_ensure_product_listing_schema_compatible",
        _fake_schema_check,
    )
    monkeypatch.setattr(product_listing_module, "list_commodities", _fake_list_commodities)

    ctx = _FakeContext()
    with pytest.raises(ValidationFailed, match="alembic upgrade head"):
        await product_listing_module.sync_product_listing_job(ctx)  # type: ignore[arg-type]

    assert called is False
    assert errors == ["schema drift: run `alembic upgrade head`"]


def _nullable_schema_rows() -> list[dict[str, object]]:
    return [
        {"column_name": "commodity_sku", "is_nullable": "YES"},
        {"column_name": "commodity_id", "is_nullable": "YES"},
    ]
