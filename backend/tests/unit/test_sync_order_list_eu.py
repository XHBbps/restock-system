from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.dialects import postgresql


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
            return _FakeResult(len(self.statements) * 100)
        return None


def _compiled_params(stmt: Any) -> dict[str, Any]:
    return dict(stmt.compile().params)


def _compiled_postgres_sql(stmt: Any) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


def _package_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "shopId": "SHOP-1",
        "shopName": "Main Shop",
        "packageSn": "PKG-1",
        "status": "has_shipped",
        "platformName": "Amazon",
        "marketplace": "US",
        "marketplaceId": "ATVPDKIKX0DER",
        "address": {
            "countryCode": "US",
            "postalCode": "90210",
        },
        "orders": [
            {
                "amazonOrderId": "AMZ-1",
                "purchaseDate": "2026-04-21 08:00:00",
            }
        ],
        "items": [
            {
                "amazonOrderId": "AMZ-1",
                "orderItemId": "ITEM-1",
                "commoditySku": "SKU-1",
                "sellerSku": "SELLER-1",
                "quantityOrdered": "2",
            }
        ],
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_upsert_package_order_maps_fields_and_items() -> None:
    from app.sync.order_list import _upsert_package_ship_order

    db = _FakeDb()
    orders, items = await _upsert_package_ship_order(
        db,  # type: ignore[arg-type]
        _package_payload(),
        set(),
    )

    assert (orders, items) == (1, 1)
    header_values = _compiled_params(db.statements[0])
    assert header_values["amazon_order_id"] == "AMZ-1"
    assert header_values["source"] == "????"
    assert header_values["order_platform"] == "Amazon"
    assert header_values["package_sn"] == "PKG-1"
    assert header_values["package_status"] == "has_shipped"
    assert header_values["shop_name"] == "Main Shop"
    assert header_values["postal_code"] == "90210"
    assert header_values["country_code"] == "US"
    assert header_values["order_status"] == "has_shipped"

    item_values = _compiled_params(db.statements[1])
    assert item_values["order_item_id_m0"] == "ITEM-1"
    assert item_values["commodity_sku_m0"] == "SKU-1"
    assert item_values["seller_sku_m0"] == "SELLER-1"
    assert item_values["quantity_ordered_m0"] == 2
    assert item_values["quantity_shipped_m0"] == 2
    assert item_values["refund_num_m0"] == 0


@pytest.mark.asyncio
async def test_upsert_package_order_falls_back_to_seller_sku_when_commodity_sku_missing() -> None:
    from app.sync.order_list import _upsert_package_ship_order

    db = _FakeDb()
    orders, items = await _upsert_package_ship_order(
        db,  # type: ignore[arg-type]
        _package_payload(
            platformName="Wayfair",
            items=[
                {
                    "amazonOrderId": "AMZ-1",
                    "orderItemId": "ITEM-1",
                    "commoditySku": None,
                    "sellerSku": "LGJ",
                    "quantityOrdered": "3",
                }
            ],
        ),
        set(),
    )

    assert (orders, items) == (1, 1)
    item_values = _compiled_params(db.statements[1])
    assert item_values["commodity_sku_m0"] == "LGJ"
    assert item_values["seller_sku_m0"] == "LGJ"
    assert item_values["quantity_ordered_m0"] == 3


@pytest.mark.asyncio
async def test_upsert_package_order_updates_postal_code_when_present() -> None:
    from app.sync.order_list import _upsert_package_ship_order

    db = _FakeDb()
    await _upsert_package_ship_order(
        db,  # type: ignore[arg-type]
        _package_payload(address={"postalCode": "10115"}),
        set(),
    )

    header_values = _compiled_params(db.statements[0])
    header_sql = _compiled_postgres_sql(db.statements[0])
    assert header_values["postal_code"] == "10115"
    assert "postal_code =" in header_sql


@pytest.mark.asyncio
@pytest.mark.parametrize("address", [{}, {"postalCode": ""}, None])
async def test_upsert_package_order_does_not_clear_postal_code_when_missing(
    address: dict[str, Any] | None,
) -> None:
    from app.sync.order_list import _upsert_package_ship_order

    db = _FakeDb()
    await _upsert_package_ship_order(
        db,  # type: ignore[arg-type]
        _package_payload(address=address),
        set(),
    )

    header_values = _compiled_params(db.statements[0])
    header_sql = _compiled_postgres_sql(db.statements[0])
    assert header_values["postal_code"] is None
    assert "postal_code =" not in header_sql


@pytest.mark.asyncio
async def test_upsert_package_order_applies_eu_mapping_and_preserves_original_country() -> None:
    from app.sync.order_list import _upsert_package_ship_order

    db = _FakeDb()
    await _upsert_package_ship_order(
        db,  # type: ignore[arg-type]
        _package_payload(marketplace="DE", address={"countryCode": "US", "postalCode": "10115"}),
        {"DE", "FR"},
    )

    header_values = _compiled_params(db.statements[0])
    assert header_values["country_code"] == "EU"
    assert header_values["original_country_code"] == "DE"


@pytest.mark.asyncio
async def test_upsert_package_order_falls_back_to_zz_for_unknown_country() -> None:
    from app.sync.order_list import _upsert_package_ship_order

    db = _FakeDb()
    await _upsert_package_ship_order(
        db,  # type: ignore[arg-type]
        _package_payload(marketplace="", address={"countryCode": "US", "country": "DE"}),
        set(),
    )

    header_values = _compiled_params(db.statements[0])
    assert header_values["country_code"] == "ZZ"
    assert header_values["original_country_code"] is None


@pytest.mark.asyncio
async def test_upsert_package_order_preserves_existing_items_when_no_valid_items() -> None:
    from app.sync.order_list import _upsert_package_ship_order

    db = _FakeDb()
    orders, items = await _upsert_package_ship_order(
        db,  # type: ignore[arg-type]
        _package_payload(items=[{"amazonOrderId": "AMZ-1", "orderItemId": "ITEM-1"}]),
        set(),
    )

    assert (orders, items) == (1, 0)
    assert len(db.statements) == 1


@pytest.mark.asyncio
async def test_upsert_package_order_keeps_split_packages_separate() -> None:
    from app.sync.order_list import _upsert_package_ship_order

    db = _FakeDb()
    await _upsert_package_ship_order(
        db,  # type: ignore[arg-type]
        _package_payload(packageSn="PKG-1"),
        set(),
    )
    await _upsert_package_ship_order(
        db,  # type: ignore[arg-type]
        _package_payload(packageSn="PKG-2"),
        set(),
    )

    first_header = _compiled_params(db.statements[0])
    second_header = _compiled_params(db.statements[3])
    assert first_header["amazon_order_id"] == second_header["amazon_order_id"] == "AMZ-1"
    assert first_header["package_sn"] == "PKG-1"
    assert second_header["package_sn"] == "PKG-2"
