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
async def test_upsert_inventory_applies_eu_mapping_and_preserves_original_country() -> None:
    from app.sync.inventory import _upsert_inventory

    db = _FakeDb()
    await _upsert_inventory(
        db,  # type: ignore[arg-type]
        {
            "commoditySku": "SKU-1",
            "warehouseId": "WH-1",
            "stockAvailable": "10",
            "stockOccupy": "2",
        },
        {"WH-1": "DE"},
        {"DE", "FR"},
    )

    values = _statement_values(db.statements[0])
    assert values["country"] == "EU"
    assert values["original_country"] == "DE"
