from __future__ import annotations

from typing import Any

import pytest


class _FakeResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar_one(self) -> int:
        return self._value


class _FakeDb:
    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def execute(self, stmt: Any) -> Any:
        self.statements.append(stmt)
        if getattr(stmt, "_returning", None):
            return _FakeResult(123)
        return None


def _compiled_params(stmt: Any) -> dict[str, Any]:
    return dict(stmt.compile().params)


@pytest.mark.asyncio
async def test_upsert_order_applies_eu_mapping_and_preserves_original_country() -> None:
    from app.sync.order_list import _upsert_order

    db = _FakeDb()
    inserted = await _upsert_order(
        db,  # type: ignore[arg-type]
        {
            "shopId": "SHOP-1",
            "amazonOrderId": "AMZ-1",
            "marketplaceId": "A1PA6795UKMFR9",
            "purchaseDate": "2026-04-21 08:00:00",
            "lastUpdateDate": "2026-04-21 09:00:00",
            "orderStatus": "Unshipped",
            "orderItemVoList": [
                {
                    "orderItemId": "ITEM-1",
                    "commoditySku": "SKU-1",
                    "quantityOrdered": "2",
                }
            ],
        },
        {"DE", "FR"},
    )

    assert inserted == 1
    header_values = _compiled_params(db.statements[0])
    assert header_values["marketplace_id"] == "EU"
    assert header_values["country_code"] == "EU"
    assert header_values["original_country_code"] == "DE"
