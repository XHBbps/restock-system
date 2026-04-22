from __future__ import annotations

from typing import Any

import pytest


class _FakeDb:
    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def execute(self, stmt: Any) -> None:
        self.statements.append(stmt)
        return None


def _statement_values(stmt: Any) -> dict[str, Any]:
    return dict(stmt.compile().params)


@pytest.mark.asyncio
async def test_upsert_inventory_maps_eu_country() -> None:
    from app.sync.inventory import _upsert_inventory

    db = _FakeDb()
    await _upsert_inventory(
        db,  # type: ignore[arg-type]
        {
            "commoditySku": "SKU-EU",
            "warehouseId": "WH-DE",
            "stockAvailable": 100,
            "stockOccupy": 20,
        },
        warehouse_country_map={"WH-DE": "DE"},
        eu_countries={"DE", "FR", "IT"},
    )

    values = _statement_values(db.statements[0])
    assert values["country"] == "EU"
    assert values["original_country"] == "DE"
    assert values["available"] == 100
    assert values["reserved"] == 20


@pytest.mark.asyncio
async def test_upsert_inventory_keeps_non_eu_country_as_is() -> None:
    from app.sync.inventory import _upsert_inventory

    db = _FakeDb()
    await _upsert_inventory(
        db,  # type: ignore[arg-type]
        {
            "commoditySku": "SKU-US",
            "warehouseId": "WH-US",
            "stockAvailable": 50,
            "stockOccupy": 5,
        },
        warehouse_country_map={"WH-US": "US"},
        eu_countries={"DE", "FR"},
    )

    values = _statement_values(db.statements[0])
    assert values["country"] == "US"
    # 非 EU 国家 original_country 写 None（避免冗余审计字段）
    assert values["original_country"] is None


@pytest.mark.asyncio
async def test_upsert_inventory_skips_unknown_warehouse() -> None:
    from app.sync.inventory import _upsert_inventory

    db = _FakeDb()
    await _upsert_inventory(
        db,  # type: ignore[arg-type]
        {
            "commoditySku": "SKU-X",
            "warehouseId": "WH-GHOST",
            "stockAvailable": 1,
        },
        warehouse_country_map={"WH-US": "US"},  # 不含 WH-GHOST
        eu_countries=set(),
    )

    # 未知仓库应被跳过，不产生 SQL
    assert db.statements == []


@pytest.mark.asyncio
async def test_upsert_inventory_skips_missing_sku_or_warehouse() -> None:
    from app.sync.inventory import _upsert_inventory

    db = _FakeDb()
    await _upsert_inventory(
        db,  # type: ignore[arg-type]
        {"warehouseId": "WH-US"},  # 缺 commoditySku
        {"WH-US": "US"},
        set(),
    )
    await _upsert_inventory(
        db,  # type: ignore[arg-type]
        {"commoditySku": "SKU-Y"},  # 缺 warehouseId
        {"WH-US": "US"},
        set(),
    )
    assert db.statements == []


@pytest.mark.asyncio
async def test_upsert_inventory_empty_eu_countries_defaults_to_no_mapping() -> None:
    from app.sync.inventory import _upsert_inventory

    db = _FakeDb()
    await _upsert_inventory(
        db,  # type: ignore[arg-type]
        {
            "commoditySku": "SKU-DE",
            "warehouseId": "WH-DE",
            "stockAvailable": 10,
        },
        warehouse_country_map={"WH-DE": "DE"},
        eu_countries=None,  # None = 从未配置，等同空集
    )

    values = _statement_values(db.statements[0])
    # eu_countries 为 None / 空集时 apply_eu_mapping 不改写
    assert values["country"] == "DE"
    assert values["original_country"] is None
