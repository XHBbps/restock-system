from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

import pytest


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

    assert _extract_country_from_remark("20260410美国-赢捷-加州-散货-在途中") == "US"


def test_extract_country_from_remark_returns_none_when_missing() -> None:
    from app.sync.out_records import _extract_country_from_remark

    assert _extract_country_from_remark("赢捷-加州-散货-在途中") is None
