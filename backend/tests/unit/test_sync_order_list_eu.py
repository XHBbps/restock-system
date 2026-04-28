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


@pytest.mark.asyncio
async def test_upsert_multiplatform_order_maps_fields_and_items() -> None:
    from app.sync.order_list import _upsert_multiplatform_order

    db = _FakeDb()
    inserted = await _upsert_multiplatform_order(
        db,  # type: ignore[arg-type]
        {
            "shopId": "SHOP-1",
            "orderNo": "ORDER-1",
            "platformName": "Wayfair",
            "marketplaceCode": "",
            "extraInfo": {"warehouse_country": "us"},
            "orderStatus": "已发货",
            "currency": "USD",
            "totalAmount": "12.34",
            "purchaseDate": "2026-04-21 08:00:00",
            "payTime": "2026-04-21 09:00:00",
            "orderItemList": [
                {
                    "orderItemId": "ITEM-1",
                    "localSku": "SKU-1",
                    "msku": "MSKU-1",
                    "saleNum": "2",
                    "originalPrice": "6.17",
                }
            ],
        },
        set(),
    )

    assert inserted == 1
    header_values = _compiled_params(db.statements[0])
    assert header_values["amazon_order_id"] == "ORDER-1"
    assert header_values["source"] == "多平台"
    assert header_values["order_platform"] == "Wayfair"
    assert header_values["country_code"] == "US"
    assert header_values["order_status"] == "Shipped"

    item_values = _compiled_params(db.statements[1])
    assert item_values["order_item_id_m0"] == "ITEM-1"
    assert item_values["commodity_sku_m0"] == "SKU-1"
    assert item_values["seller_sku_m0"] == "MSKU-1"
    assert item_values["quantity_ordered_m0"] == 2
    assert item_values["quantity_shipped_m0"] == 2


@pytest.mark.asyncio
async def test_upsert_multiplatform_order_keeps_new_valid_country_code() -> None:
    from app.sync.order_list import _upsert_multiplatform_order

    db = _FakeDb()
    inserted = await _upsert_multiplatform_order(
        db,  # type: ignore[arg-type]
        {
            "shopId": "SHOP-1",
            "orderNo": "ORDER-RO",
            "platformName": "eMAG",
            "marketplaceCode": "ro",
            "orderStatus": "已发货",
            "purchaseDate": "2026-04-21 08:00:00",
            "orderItemList": [
                {"orderItemId": "ITEM-1", "localSku": "SKU-1", "saleNum": "1"},
            ],
        },
        set(),
    )

    assert inserted == 1
    header_values = _compiled_params(db.statements[0])
    assert header_values["country_code"] == "RO"
    assert header_values["original_country_code"] is None


@pytest.mark.asyncio
async def test_upsert_multiplatform_order_invalid_country_falls_back_to_zz() -> None:
    from app.sync.order_list import _upsert_multiplatform_order

    db = _FakeDb()
    inserted = await _upsert_multiplatform_order(
        db,  # type: ignore[arg-type]
        {
            "shopId": "SHOP-1",
            "orderNo": "ORDER-BAD",
            "platformName": "Unknown",
            "marketplaceCode": "USA",
            "orderStatus": "已发货",
            "purchaseDate": "2026-04-21 08:00:00",
            "orderItemList": [
                {"orderItemId": "ITEM-1", "localSku": "SKU-1", "saleNum": "1"},
            ],
        },
        set(),
    )

    assert inserted == 1
    header_values = _compiled_params(db.statements[0])
    assert header_values["country_code"] == "ZZ"
    assert header_values["original_country_code"] is None


@pytest.mark.asyncio
async def test_upsert_multiplatform_order_skips_missing_local_sku_item() -> None:
    from app.sync.order_list import _upsert_multiplatform_order

    db = _FakeDb()
    inserted = await _upsert_multiplatform_order(
        db,  # type: ignore[arg-type]
        {
            "shopId": "SHOP-1",
            "orderNo": "ORDER-2",
            "platformName": "Walmart",
            "marketplaceCode": "US",
            "orderStatus": "未付款",
            "purchaseDate": "2026-04-21 08:00:00",
            "orderItemList": [{"orderItemId": "ITEM-1", "localSku": "", "saleNum": "2"}],
        },
        set(),
    )

    assert inserted == 0
    header_values = _compiled_params(db.statements[0])
    assert header_values["source"] == "多平台"
    assert header_values["order_status"] == "Pending"
    assert len(db.statements) == 2
