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
async def test_upsert_listing_applies_eu_mapping() -> None:
    from app.sync.product_listing import _upsert_listing

    db = _FakeDb()
    await _upsert_listing(
        db,  # type: ignore[arg-type]
        {
            "shopId": "SHOP-1",
            "marketplaceId": "A1PA6795UKMFR9",
            "sku": "SELLER-1",
        },
        {"DE", "FR"},
    )

    values = _statement_values(db.statements[0])
    assert values["marketplace_id"] == "EU"
    assert values["original_marketplace_id"] == "DE"
