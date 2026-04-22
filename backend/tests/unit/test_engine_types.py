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
