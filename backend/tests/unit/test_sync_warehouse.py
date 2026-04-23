"""Unit tests for sync/warehouse._upsert_warehouse and _normalize_replenish_site."""

from __future__ import annotations

from typing import Any

import pytest

from app.sync.warehouse import _normalize_replenish_site


def test_normalize_replenish_site_truncates_long_values() -> None:
    raw = "ATVPDKIKX0DER,A2EUQ1WTGCTBG2,A1AM78C64UM0Y8,A1F83G8C2ARO7P"
    value = _normalize_replenish_site(raw)

    assert value is not None
    assert len(value) == 50
    assert value.endswith("…")


def test_normalize_replenish_site_keeps_short_values() -> None:
    assert _normalize_replenish_site("ATVPDKIKX0DER") == "ATVPDKIKX0DER"
    assert _normalize_replenish_site("") is None


class _FakeDb:
    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def execute(self, stmt: Any) -> None:
        self.statements.append(stmt)
        return None


def _values(stmt: Any) -> dict[str, Any]:
    return dict(stmt.compile().params)


@pytest.mark.asyncio
async def test_upsert_warehouse_happy_path() -> None:
    from app.sync.warehouse import _upsert_warehouse

    db = _FakeDb()
    await _upsert_warehouse(
        db,  # type: ignore[arg-type]
        {
            "id": "WH-1",
            "name": "US Warehouse",
            "type": 1,
        },
    )

    values = _values(db.statements[0])
    assert values["id"] == "WH-1"
    assert values["name"] == "US Warehouse"
    assert values["type"] == 1


@pytest.mark.asyncio
async def test_upsert_warehouse_skips_missing_id() -> None:
    from app.sync.warehouse import _upsert_warehouse

    db = _FakeDb()
    await _upsert_warehouse(db, {"name": "No Id"})  # type: ignore[arg-type]

    assert db.statements == []


@pytest.mark.asyncio
async def test_upsert_warehouse_coerces_type_string_to_int() -> None:
    from app.sync.warehouse import _upsert_warehouse

    db = _FakeDb()
    await _upsert_warehouse(
        db,  # type: ignore[arg-type]
        {"id": "WH-2", "name": "Type String", "type": "2"},
    )

    values = _values(db.statements[0])
    assert values["type"] == 2


@pytest.mark.asyncio
async def test_upsert_warehouse_defaults_type_zero_when_invalid() -> None:
    from app.sync.warehouse import _upsert_warehouse

    db = _FakeDb()
    await _upsert_warehouse(
        db,  # type: ignore[arg-type]
        {"id": "WH-3", "name": "Bad Type", "type": "not-a-number"},
    )

    values = _values(db.statements[0])
    assert values["type"] == 0  # fallback


@pytest.mark.asyncio
async def test_upsert_warehouse_preserves_replenish_site_raw() -> None:
    from app.sync.warehouse import _upsert_warehouse

    db = _FakeDb()
    await _upsert_warehouse(
        db,  # type: ignore[arg-type]
        {
            "id": "WH-4",
            "name": "With Site",
            "type": 1,
            "replenishSite": "amazon.com",
        },
    )

    values = _values(db.statements[0])
    assert values["id"] == "WH-4"
    assert values["replenish_site_raw"] == "amazon.com"
