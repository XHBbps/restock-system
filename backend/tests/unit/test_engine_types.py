"""Engine 类型系统单测：frozen dataclass 不变性 + 构造 + total 计算。"""

from __future__ import annotations

import dataclasses

import pytest


def test_inventory_stock_roundtrip() -> None:
    from app.engine.context import InventoryStock

    stock = InventoryStock(available=10, reserved=3, in_transit=7)
    assert stock.available == 10
    assert stock.reserved == 3
    assert stock.in_transit == 7
    assert stock.total == 20  # 10 + 3 + 7


def test_inventory_stock_is_frozen() -> None:
    from app.engine.context import InventoryStock

    stock = InventoryStock(available=1, reserved=0, in_transit=0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        stock.available = 99  # type: ignore[misc]


def test_inventory_stock_equality() -> None:
    from app.engine.context import InventoryStock

    a = InventoryStock(available=5, reserved=2, in_transit=0)
    b = InventoryStock(available=5, reserved=2, in_transit=0)
    c = InventoryStock(available=5, reserved=2, in_transit=1)
    assert a == b
    assert a != c


def test_local_stock_roundtrip() -> None:
    from app.engine.context import LocalStock

    stock = LocalStock(available=100, reserved=20)
    assert stock.available == 100
    assert stock.reserved == 20
    assert stock.total == 120


def test_local_stock_is_frozen() -> None:
    from app.engine.context import LocalStock

    stock = LocalStock(available=1, reserved=0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        stock.reserved = 9  # type: ignore[misc]


def test_local_stock_equality() -> None:
    from app.engine.context import LocalStock

    assert LocalStock(available=5, reserved=2) == LocalStock(available=5, reserved=2)
    assert LocalStock(available=5, reserved=2) != LocalStock(available=5, reserved=3)


def test_merge_inventory_returns_inventory_stock() -> None:
    from app.engine.context import InventoryStock
    from app.engine.step2_sale_days import merge_inventory

    oversea = {
        ("SKU-A", "US"): {"available": 10, "reserved": 3},
        ("SKU-B", "GB"): {"available": 5, "reserved": 0},
    }
    in_transit = {
        ("SKU-A", "US"): 7,
        ("SKU-C", "DE"): 20,
    }

    result = merge_inventory(oversea, in_transit)

    assert result["SKU-A"]["US"] == InventoryStock(available=10, reserved=3, in_transit=7)
    assert result["SKU-B"]["GB"] == InventoryStock(available=5, reserved=0, in_transit=0)
    assert result["SKU-C"]["DE"] == InventoryStock(available=0, reserved=0, in_transit=20)


def test_compute_sale_days_reads_inventory_stock_total() -> None:
    from app.engine.context import InventoryStock
    from app.engine.step2_sale_days import compute_sale_days

    velocity = {"SKU-A": {"US": 2.0}}  # 2 件/天
    inventory = {"SKU-A": {"US": InventoryStock(available=10, reserved=5, in_transit=5)}}  # total=20

    result = compute_sale_days(velocity, inventory)

    assert result["SKU-A"]["US"] == pytest.approx(10.0)  # 20 / 2


def test_compute_country_qty_reads_inventory_stock_total() -> None:
    from app.engine.context import InventoryStock
    from app.engine.step3_country_qty import compute_country_qty

    velocity = {"SKU-A": {"US": 3.0}}  # 3 件/天
    inventory = {"SKU-A": {"US": InventoryStock(available=10, reserved=5, in_transit=15)}}  # total=30
    # target_days=30, raw = 30*3 - 30 = 60
    result = compute_country_qty(velocity, inventory, target_days=30)

    assert result["SKU-A"]["US"] == 60


def test_compute_total_accepts_local_stock() -> None:
    from app.engine.context import LocalStock
    from app.engine.step4_total import compute_total

    # sum_qty=100, local=40+10=50, safety=0
    # buffer_days is accepted for compatibility but does not affect purchase_qty.
    result = compute_total(
        sku="SKU-A",
        country_qty_for_sku={"US": 60, "GB": 40},
        velocity_for_sku={"US": 6.0, "GB": 4.0},
        local_stock_for_sku=LocalStock(available=40, reserved=10),
        buffer_days=30,
        safety_stock_days=0,
    )
    result_no_buffer = compute_total(
        sku="SKU-A",
        country_qty_for_sku={"US": 60, "GB": 40},
        velocity_for_sku={"US": 6.0, "GB": 4.0},
        local_stock_for_sku=LocalStock(available=40, reserved=10),
        buffer_days=0,
        safety_stock_days=0,
    )
    assert result == 50
    assert result_no_buffer == result


def test_compute_total_accepts_none_local_stock() -> None:
    from app.engine.step4_total import compute_total

    result = compute_total(
        sku="SKU-B",
        country_qty_for_sku={"US": 10},
        velocity_for_sku={"US": 0.0},
        local_stock_for_sku=None,
        buffer_days=30,
        safety_stock_days=0,
    )
    assert result == 10  # 10 + 0 - 0 + 0


def test_step4_total_returns_flat_sku_to_int_dict() -> None:
    from app.engine.context import EngineContext, LocalStock
    from app.engine.step4_total import step4_total

    ctx = EngineContext(
        country_qty={"SKU-A": {"US": 100}, "SKU-B": {"GB": 40}},
        velocity={"SKU-A": {"US": 10.0}, "SKU-B": {"GB": 4.0}},
        local_stock={
            "SKU-A": LocalStock(available=20, reserved=10),  # 30
            "SKU-B": LocalStock(available=5, reserved=0),  # 5
        },
        buffer_days=30,
        safety_stock_days=0,
    )
    result = step4_total(ctx)

    # 新签名：dict[sku, int]，不再有 {"purchase_qty": int} 包裹
    assert isinstance(result, dict)
    assert all(isinstance(v, int) for v in result.values())
    # SKU-A: sum_qty=100, local=30, safety=0 → 100 - 30 = 70
    assert result["SKU-A"] == 70
    # SKU-B: sum_qty=40, local=5, safety=0 → 40 - 5 = 35
    assert result["SKU-B"] == 35
