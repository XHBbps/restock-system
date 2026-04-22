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
