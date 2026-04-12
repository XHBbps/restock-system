from datetime import datetime

from app.api.data import _has_visible_order_detail
from app.models.order import OrderDetail


def build_detail(**overrides: object) -> OrderDetail:
    payload = {
        "shop_id": "shop-1",
        "amazon_order_id": "order-1",
        "postal_code": None,
        "country_code": "US",
        "state_or_region": None,
        "city": None,
        "detail_address": None,
        "receiver_name": None,
        "fetched_at": datetime(2026, 4, 10, 12, 0, 0),
    }
    payload.update(overrides)
    return OrderDetail(**payload)


def test_has_visible_order_detail_returns_false_for_empty_detail() -> None:
    detail = build_detail()

    assert _has_visible_order_detail(detail) is False


def test_has_visible_order_detail_returns_true_when_postal_code_present() -> None:
    detail = build_detail(postal_code="90210")

    assert _has_visible_order_detail(detail) is True
