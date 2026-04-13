"""Unit tests for Step 2 sale_days."""

import pytest

from app.engine.step2_sale_days import compute_sale_days, load_in_transit, merge_inventory


class _RowsResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _FakeDb:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    async def execute(self, stmt):
        self.statements.append(stmt)
        return _RowsResult(self.rows)


def test_merge_inventory_keeps_zero_transit_by_default() -> None:
    merged = merge_inventory(
        oversea={("sku-A", "US"): {"available": 10, "reserved": 2}},
        in_transit={},
    )

    assert merged["sku-A"]["US"] == {
        "available": 10,
        "reserved": 2,
        "in_transit": 0,
        "total": 12,
    }


def test_compute_sale_days_uses_total_stock() -> None:
    sale_days = compute_sale_days(
        velocity={"sku-A": {"US": 5.0}},
        inventory={"sku-A": {"US": {"available": 10, "reserved": 5, "in_transit": 0, "total": 15}}},
    )

    assert sale_days["sku-A"]["US"] == 3.0


def test_compute_sale_days_skips_zero_or_negative_velocity() -> None:
    sale_days = compute_sale_days(
        velocity={"sku-A": {"US": 0.0, "CA": -1.0, "UK": 2.0}},
        inventory={
            "sku-A": {
                "US": {"total": 20},
                "CA": {"total": 20},
                "UK": {"total": 6},
            }
        },
    )

    assert "US" not in sale_days.get("sku-A", {})
    assert "CA" not in sale_days.get("sku-A", {})
    assert sale_days["sku-A"]["UK"] == 3.0


def test_compute_sale_days_does_not_create_inventory_only_country() -> None:
    sale_days = compute_sale_days(
        velocity={"sku-A": {"US": 4.0}},
        inventory={
            "sku-A": {
                "US": {"total": 8},
                "CA": {"total": 100},
            }
        },
    )

    assert sale_days == {"sku-A": {"US": 2.0}}


@pytest.mark.asyncio
async def test_load_in_transit_reads_synced_tables_and_aggregates_goods() -> None:
    db = _FakeDb(
        [
            ("sku-A", "US", 12),
            ("sku-A", "JP", 5),
            ("sku-B", "US", 8),
        ]
    )

    result = await load_in_transit(db, ["sku-A", "sku-B"])

    assert result == {
        ("sku-A", "US"): 12,
        ("sku-A", "JP"): 5,
        ("sku-B", "US"): 8,
    }
    compiled_sql = str(db.statements[0])
    assert "in_transit_item" in compiled_sql
    assert "in_transit_record" in compiled_sql
    assert "suggestion_item" not in compiled_sql
