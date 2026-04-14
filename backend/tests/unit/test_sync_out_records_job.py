from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from types import SimpleNamespace

import pytest

from app.models.in_transit import InTransitRecord


class _FakeDb:
    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def execute(self, stmt: Any) -> None:
        self.statements.append(stmt)
        return None


def _statement_values(stmt: Any) -> dict[str, Any]:
    compiled = stmt.compile()
    return dict(compiled.params)


def _normalize_multi_values(rows: list[dict[Any, Any]]) -> list[dict[str, Any]]:
    return [
        {getattr(key, "key", key): value for key, value in row.items()}
        for row in rows
    ]


@pytest.mark.asyncio
async def test_upsert_out_record_persists_record_and_item_metadata() -> None:
    from app.sync.out_records import _upsert_out_record

    db = _FakeDb()
    sync_start = datetime(2026, 4, 14, 12, 0, 0)

    raw = {
        "id": "OUT-1",
        "warehouseId": "WH-SRC-1",
        "targetFbaWarehouseId": "WH-TGT-1",
        "outWarehouseNo": "OW-1",
        "updateTime": "2026-04-14 10:15:30",
        "status": "1",
        "type": "3",
        "typeName": "调拨出库",
        "remark": "在途中",
        "items": [
            {
                "commodityId": "CID-1",
                "commoditySku": "SKU-1",
                "goods": "5",
                "perPurchase": "12.50",
            }
        ],
    }

    inserted = await _upsert_out_record(
        db,  # type: ignore[arg-type]
        raw,
        {"WH-TGT-1"},
        sync_start,
    )

    assert inserted == 1
    assert len(db.statements) == 3

    record_values = _statement_values(db.statements[0])
    assert record_values["saihu_out_record_id"] == "OUT-1"
    assert record_values["warehouse_id"] == "WH-SRC-1"
    assert record_values["target_warehouse_id"] == "WH-TGT-1"
    assert record_values["target_country"] is None
    assert record_values["status"] == "1"
    assert record_values["type"] == 3
    assert record_values["type_name"] == "调拨出库"
    assert record_values["remark"] == "在途中"
    assert record_values["update_time"].isoformat() == "2026-04-14T10:15:30+08:00"

    item_values = _normalize_multi_values(db.statements[2]._multi_values[0])
    assert item_values == [
        {
            "saihu_out_record_id": "OUT-1",
            "commodity_id": "CID-1",
            "commodity_sku": "SKU-1",
            "goods": 5,
            "per_purchase": Decimal("12.50"),
        }
    ]


@pytest.mark.asyncio
async def test_upsert_out_record_skips_non_positive_items() -> None:
    from app.sync.out_records import _upsert_out_record

    db = _FakeDb()
    sync_start = datetime(2026, 4, 14, 12, 0, 0)

    raw = {
        "id": "OUT-2",
        "warehouseId": "WH-SRC-2",
        "items": [
            {"commodityId": "CID-0", "commoditySku": "SKU-0", "goods": "0", "perPurchase": "8.00"},
            {"commodityId": "CID-1", "commoditySku": "", "goods": "3", "perPurchase": "9.00"},
        ],
    }

    inserted = await _upsert_out_record(
        db,  # type: ignore[arg-type]
        raw,
        set(),
        sync_start,
    )

    assert inserted == 0
    assert len(db.statements) == 2


def test_extract_country_from_remark_returns_country_code() -> None:
    from app.sync.out_records import _extract_country_from_remark

    assert _extract_country_from_remark("20260410美国-赢捷-纽约-散货-在途中") == "US"


def test_extract_country_from_remark_returns_none_when_missing() -> None:
    from app.sync.out_records import _extract_country_from_remark

    assert _extract_country_from_remark("赢捷-纽约-散货-在途中") is None


class _FakeScalarResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class _FakeBackfillResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> _FakeScalarResult:
        return _FakeScalarResult(self._rows)


class _FakeBackfillDb:
    def __init__(self, rows: list[InTransitRecord]) -> None:
        self.rows = rows
        self.committed = False

    async def execute(self, _stmt: Any) -> _FakeBackfillResult:
        return _FakeBackfillResult(self.rows)

    async def commit(self) -> None:
        self.committed = True


@pytest.mark.asyncio
async def test_backfill_target_country_from_remark_updates_only_empty_values() -> None:
    from app.sync.out_records import _backfill_target_country_from_remark

    rows = [
        InTransitRecord(
            saihu_out_record_id="OUT-1",
            remark="20260410美国-赢捷-纽约-散货-在途中",
            target_country=None,
            is_in_transit=True,
            last_seen_at=datetime(2026, 4, 14, 12, 0, 0),
        ),
        InTransitRecord(
            saihu_out_record_id="OUT-2",
            remark="赢捷-纽约-散货-在途中",
            target_country=None,
            is_in_transit=True,
            last_seen_at=datetime(2026, 4, 14, 12, 0, 0),
        ),
    ]
    db = _FakeBackfillDb(rows)

    scanned, updated, skipped = await _backfill_target_country_from_remark(db)  # type: ignore[arg-type]

    assert scanned == 2
    assert updated == 1
    assert skipped == 1
    assert rows[0].target_country == "US"
    assert rows[1].target_country is None
    assert db.committed is True


@pytest.mark.asyncio
async def test_sync_out_records_job_runs_backfill_inside_main_flow(monkeypatch) -> None:
    import app.sync.out_records as out_records_module

    calls: list[str] = []
    progress: list[dict[str, Any]] = []

    class _FakeSession:
        async def execute(self, _stmt: Any) -> SimpleNamespace:
            raise AssertionError("unexpected execute call")

        async def commit(self) -> None:
            return None

    class _FakeSessionContext:
        async def __aenter__(self) -> _FakeSession:
            return _FakeSession()

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

    async def fake_mark_sync_running(_db: Any, job_name: str) -> datetime:
        calls.append(f"running:{job_name}")
        return datetime(2026, 4, 14, 12, 0, 0)

    async def fake_mark_sync_success(_db: Any, job_name: str, _started: datetime) -> None:
        calls.append(f"success:{job_name}")

    async def fake_load_warehouse_ids(_db: Any) -> set[str]:
        return set()

    async def fake_upsert_out_record(_db: Any, _raw: dict[str, Any], _warehouse_ids: set[str], _sync_start: datetime) -> int:
        calls.append("upsert")
        return 2

    async def fake_backfill(_db: Any) -> tuple[int, int, int]:
        calls.append("backfill")
        return 5, 3, 2

    async def fake_age_out_records(_sync_start: datetime) -> int:
        calls.append("age")
        return 4

    async def fake_list_in_transit_records(*, on_page):
        await on_page(1, 1, 1)
        yield {"id": "OUT-1", "items": [{"commoditySku": "SKU-1", "goods": "2"}]}

    async def fake_progress(**kwargs: Any) -> None:
        progress.append(kwargs)

    monkeypatch.setattr(out_records_module, "async_session_factory", lambda: _FakeSessionContext())
    monkeypatch.setattr(out_records_module, "mark_sync_running", fake_mark_sync_running)
    monkeypatch.setattr(out_records_module, "mark_sync_success", fake_mark_sync_success)
    monkeypatch.setattr(out_records_module, "_load_warehouse_ids", fake_load_warehouse_ids)
    monkeypatch.setattr(out_records_module, "_upsert_out_record", fake_upsert_out_record)
    monkeypatch.setattr(out_records_module, "_backfill_target_country_from_remark", fake_backfill)
    monkeypatch.setattr(out_records_module, "_age_out_records", fake_age_out_records)
    monkeypatch.setattr(out_records_module, "list_in_transit_records", fake_list_in_transit_records)

    ctx = out_records_module.JobContext(
        task_id=1,
        job_name="sync_out_records",
        payload={},
        progress_setter=fake_progress,
    )

    await out_records_module.sync_out_records_job(ctx)

    assert calls == [
        "running:sync_out_records",
        "upsert",
        "backfill",
        "age",
        "success:sync_out_records",
    ]
    assert [item.get("current_step") for item in progress if item.get("current_step")] == [
        "同步在途出库单",
        "回填目标国家",
        "老化未见记录",
        "完成",
    ]
    assert "回填国家 3" in progress[-1]["step_detail"]
