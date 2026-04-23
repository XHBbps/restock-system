"""Unit tests for sync/shop._upsert_shop."""

from __future__ import annotations

from typing import Any

import pytest


class _FakeDb:
    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def execute(self, stmt: Any) -> None:
        self.statements.append(stmt)
        return None


def _values(stmt: Any) -> dict[str, Any]:
    return dict(stmt.compile().params)


@pytest.mark.asyncio
async def test_upsert_shop_happy_path() -> None:
    from app.sync.shop import _upsert_shop

    db = _FakeDb()
    await _upsert_shop(
        db,  # type: ignore[arg-type]
        {
            "id": "SHOP-1",
            "name": "Test Shop",
            "sellerId": "SELLER-X",
            "region": "NA",
            "marketplaceId": "ATVPDKIKX0DER",
            "status": "0",
        },
    )

    values = _values(db.statements[0])
    assert values["id"] == "SHOP-1"
    assert values["name"] == "Test Shop"
    assert values["marketplace_id"] == "ATVPDKIKX0DER"


@pytest.mark.asyncio
async def test_upsert_shop_skips_missing_id() -> None:
    from app.sync.shop import _upsert_shop

    db = _FakeDb()
    await _upsert_shop(db, {"name": "No Id"})  # type: ignore[arg-type]

    assert db.statements == []


@pytest.mark.asyncio
async def test_upsert_shop_falls_back_name_to_id_when_empty() -> None:
    from app.sync.shop import _upsert_shop

    db = _FakeDb()
    await _upsert_shop(db, {"id": "SHOP-2", "name": None})  # type: ignore[arg-type]

    values = _values(db.statements[0])
    assert values["name"] == "SHOP-2"  # fallback to id


@pytest.mark.asyncio
async def test_upsert_shop_coerces_numeric_id_to_string() -> None:
    from app.sync.shop import _upsert_shop

    db = _FakeDb()
    await _upsert_shop(db, {"id": 12345, "name": "Numeric Shop"})  # type: ignore[arg-type]

    values = _values(db.statements[0])
    assert values["id"] == "12345"


@pytest.mark.asyncio
async def test_upsert_shop_null_optional_fields() -> None:
    from app.sync.shop import _upsert_shop

    db = _FakeDb()
    await _upsert_shop(
        db,  # type: ignore[arg-type]
        {"id": "SHOP-3", "name": "Minimal"},
    )

    values = _values(db.statements[0])
    assert values["id"] == "SHOP-3"
    # sellerId / region / marketplaceId absent → must not KeyError
