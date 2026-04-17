from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.api.data import list_inventory_warehouse_groups, list_out_record_types


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one(self):
        return self._value


class _AllResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _FakeSession:
    def __init__(self, responses):
        self._responses = list(responses)
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return self._responses.pop(0)


def _inventory_row(warehouse_id: str = "WH-1", sku: str = "SKU-1"):
    return SimpleNamespace(
        commodity_sku=sku,
        warehouse_id=warehouse_id,
        country="US",
        available=10,
        reserved=2,
        updated_at=datetime(2026, 4, 17, 10, 0, 0),
    )


@pytest.mark.asyncio
async def test_list_inventory_warehouse_groups_returns_grouped_page() -> None:
    group_row = SimpleNamespace(
        warehouse_id="WH-1",
        warehouse_name="Warehouse",
        warehouse_type=1,
        sku_count=1,
        total_available=10,
        total_occupy=2,
    )
    db = _FakeSession(
        [
            _ScalarResult(1),
            _AllResult([group_row]),
            _AllResult([(_inventory_row(), "Warehouse", 1)]),
            _AllResult([("SKU-1", "Product", "https://example.test/img.jpg")]),
        ]
    )

    result = await list_inventory_warehouse_groups(
        country="US",
        sku="SKU",
        only_nonzero=True,
        page=2,
        page_size=10,
        db=db,
        _=None,
    )

    assert result.total == 1
    assert result.page == 2
    assert result.page_size == 10
    assert result.items[0].warehouse_id == "WH-1"
    assert result.items[0].sku_count == 1
    assert result.items[0].total_available == 10
    assert result.items[0].items[0].commodity_name == "Product"


@pytest.mark.asyncio
async def test_list_inventory_warehouse_groups_skips_item_queries_when_empty() -> None:
    db = _FakeSession([_ScalarResult(0), _AllResult([])])

    result = await list_inventory_warehouse_groups(
        country=None,
        sku=None,
        only_nonzero=True,
        page=1,
        page_size=20,
        db=db,
        _=None,
    )

    assert result.items == []
    assert result.total == 0
    assert len(db.statements) == 2


@pytest.mark.asyncio
async def test_list_out_record_types_returns_non_empty_distinct_values() -> None:
    db = _FakeSession([_AllResult([("调拨出库",), ("销售出库",)])])

    result = await list_out_record_types(db=db, _=None)

    assert result == ["调拨出库", "销售出库"]
