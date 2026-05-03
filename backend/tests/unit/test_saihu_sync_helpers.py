from datetime import datetime
from types import SimpleNamespace

from app.api.data import _disabled_order_detail_fields
from app.sync.product_listing import _infer_is_matched, _normalize_online_status


def test_normalize_online_status_lowercases_real_response() -> None:
    assert _normalize_online_status("Active") == "active"
    assert _normalize_online_status(" inActive ") == "inactive"


def test_infer_is_matched_requires_both_commodity_fields() -> None:
    assert _infer_is_matched({"commodityId": "1001", "commoditySku": "SKU-A"}) is True
    assert _infer_is_matched({"commodityId": "1001", "commoditySku": ""}) is False
    assert _infer_is_matched({"commodityId": "", "commoditySku": "SKU-A"}) is False
    assert _infer_is_matched({}) is False


def test_disabled_order_detail_fields_hide_existing_values() -> None:
    detail = SimpleNamespace(
        postal_code="90210",
        state_or_region="CA",
        city="Los Angeles",
        detail_address="123 Test St",
        receiver_name="Alice",
        fetched_at=datetime(2026, 4, 9, 10, 0, 0),
    )

    assert _disabled_order_detail_fields(detail) == {
        "postal_code": "90210",
        "state_or_region": None,
        "city": None,
        "detail_address": None,
        "receiver_name": None,
        "detail_fetched_at": datetime(2026, 4, 9, 10, 0, 0),
    }
