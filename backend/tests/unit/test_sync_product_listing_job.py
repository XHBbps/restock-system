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
    async def commit(self) -> None:
        return None


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
async def test_sync_product_listing_job_fetches_unfiltered_rows(monkeypatch) -> None:
    import app.sync.product_listing as product_listing_module

    factory = _FakeSessionFactory(
        [_FakeDb(), _FakeSchemaDb(_nullable_schema_rows()), _FakeDb(), _FakeDb()]
    )
    started = datetime(2026, 4, 13, 23, 0, 0)
    call_args: list[tuple[bool, bool, bool]] = []
    upserted: list[dict[str, object]] = []
    created_counts: list[int] = []

    async def _fake_mark_sync_running(_db, _job_name: str) -> datetime:
        return started

    async def _fake_mark_sync_success(_db, _job_name: str, _started: datetime) -> None:
        return None

    async def _fake_list_product_listings(*, only_matched: bool, only_active: bool, on_page=None):
        call_args.append((only_matched, only_active, on_page is not None))
        if on_page is not None:
            await on_page(1, 3, 1)
        yield {"shopId": "shop-1", "marketplaceId": "US", "sku": "SELLER-1"}

    async def _fake_upsert_listing(_db, raw: dict[str, object]) -> None:
        upserted.append(raw)

    async def _fake_backfill_sku_configs(_db) -> int:
        created_counts.append(1)
        return 1

    monkeypatch.setattr(product_listing_module, "async_session_factory", factory)
    monkeypatch.setattr(product_listing_module, "mark_sync_running", _fake_mark_sync_running)
    monkeypatch.setattr(product_listing_module, "mark_sync_success", _fake_mark_sync_success)
    monkeypatch.setattr(product_listing_module, "list_product_listings", _fake_list_product_listings)
    monkeypatch.setattr(product_listing_module, "_upsert_listing", _fake_upsert_listing)
    monkeypatch.setattr(
        product_listing_module,
        "_backfill_sku_configs_from_synced_listings",
        _fake_backfill_sku_configs,
    )

    ctx = _FakeContext()
    await product_listing_module.sync_product_listing_job(ctx)  # type: ignore[arg-type]

    assert call_args == [(False, False, True)]
    assert len(upserted) == 1
    assert created_counts == [1]
    assert ctx.events[0] == ("开始同步在线产品信息", None, 1)
    assert ctx.events[1] == (None, "第 1 / 3 页，当前页 1 条，已处理 0 条", 3)


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

    async def _fake_list_product_listings(*, only_matched: bool, only_active: bool, on_page=None):
        nonlocal called
        called = True
        yield {"shopId": "shop-1", "marketplaceId": "US", "sku": "SELLER-1"}

    monkeypatch.setattr(product_listing_module, "async_session_factory", factory)
    monkeypatch.setattr(product_listing_module, "mark_sync_running", _fake_mark_sync_running)
    monkeypatch.setattr(product_listing_module, "mark_sync_failed", _fake_mark_sync_failed)
    monkeypatch.setattr(
        product_listing_module,
        "_ensure_product_listing_schema_compatible",
        _fake_schema_check,
    )
    monkeypatch.setattr(product_listing_module, "list_product_listings", _fake_list_product_listings)

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
