"""Step 5 仓内分配单元测试:真实分布 + 零数据兜底。"""

from datetime import date
from types import SimpleNamespace

import pytest

from app.engine.step5_warehouse_split import (
    explain_country_qty_split,
    load_all_sku_country_orders,
    load_country_warehouses,
    split_country_qty,
)
from app.engine.zipcode_matcher import ZipcodeRule


def _jp_rules() -> list[ZipcodeRule]:
    return [
        ZipcodeRule(
            id=1,
            country="JP",
            prefix_length=2,
            value_type="number",
            operator=">=",
            compare_value="50",
            warehouse_id="haiyuan",
            priority=10,
        ),
        ZipcodeRule(
            id=2,
            country="JP",
            prefix_length=2,
            value_type="number",
            operator="<",
            compare_value="50",
            warehouse_id="xiapu",
            priority=20,
        ),
    ]


def test_real_distribution() -> None:
    """3 单 海源 + 2 单 夏普 -> 60/40 分配 100 件。"""
    orders = [
        ("640-8453", 1),  # haiyuan
        ("550-0000", 1),  # haiyuan
        ("510-0000", 1),  # haiyuan
        ("100-0001", 1),  # xiapu
        ("200-0001", 1),  # xiapu
    ]
    result = split_country_qty(
        sku="sku-A",
        country="JP",
        country_qty=100,
        orders=orders,
        rules=_jp_rules(),
        country_warehouses=["haiyuan", "xiapu"],
    )
    assert sum(result.values()) == 100
    # haiyuan 应得 60, xiapu 40 (允许 ±1 容差)
    assert 59 <= result.get("haiyuan", 0) <= 61
    assert 39 <= result.get("xiapu", 0) <= 41


def test_unknown_warehouse_excluded_from_denominator() -> None:
    """匹配不到规则的订单应从分母中剔除。"""
    rules = _jp_rules()
    orders = [
        ("640-8453", 5),  # haiyuan
        # 无邮编订单视为未知仓
        (None, 100),
        ("", 100),
    ]
    result = split_country_qty(
        sku="sku-A",
        country="JP",
        country_qty=50,
        orders=orders,
        rules=rules,
        country_warehouses=["haiyuan", "xiapu"],
    )
    # 已知仓只有 haiyuan,应得全部 50
    assert result == {"haiyuan": 50}


def test_zero_data_fallback_even_split() -> None:
    """零样本兜底:均分到所有已维护海外仓。"""
    result = split_country_qty(
        sku="sku-A",
        country="JP",
        country_qty=100,
        orders=[],  # 零订单
        rules=_jp_rules(),
        country_warehouses=["haiyuan", "xiapu", "third"],
    )
    # 100 / 3 = 33 余 1 -> 34/33/33
    assert sum(result.values()) == 100
    assert len(result) == 3
    assert max(result.values()) - min(result.values()) <= 1


def test_matched_warehouse_outside_eligible_list_becomes_unknown() -> None:
    """命中到非该国维护仓时,该样本不得进入有效已知仓分母。"""
    rules = _jp_rules()
    result = explain_country_qty_split(
        sku="sku-A",
        country="JP",
        country_qty=50,
        orders=[
            ("640-8453", 5),  # haiyuan
            ("100-0001", 5),  # xiapu but not eligible below
        ],
        rules=rules,
        country_warehouses=["haiyuan"],
    )

    assert result.warehouse_breakdown == {"haiyuan": 50}
    assert result.allocation_mode == "matched"
    assert result.matched_order_qty == 5
    assert result.unknown_order_qty == 5
    assert result.eligible_warehouses == ["haiyuan"]


def test_all_unknown_samples_fallback_even() -> None:
    """全是未知样本时,进入均分兜底并保留 unknown 统计。"""
    result = explain_country_qty_split(
        sku="sku-A",
        country="JP",
        country_qty=9,
        orders=[
            (None, 4),
            ("", 5),
        ],
        rules=_jp_rules(),
        country_warehouses=["haiyuan", "xiapu"],
    )

    assert result.allocation_mode == "fallback_even"
    assert result.matched_order_qty == 0
    assert result.unknown_order_qty == 9
    assert result.warehouse_breakdown == {"haiyuan": 5, "xiapu": 4}


def test_no_warehouse_returns_empty_with_reason() -> None:
    result = explain_country_qty_split(
        sku="sku-A",
        country="JP",
        country_qty=20,
        orders=[(None, 20)],
        rules=_jp_rules(),
        country_warehouses=[],
    )

    assert result.warehouse_breakdown == {}
    assert result.allocation_mode == "no_warehouse"
    assert result.matched_order_qty == 0
    assert result.unknown_order_qty == 20


def test_zero_data_no_warehouse_returns_empty() -> None:
    result = split_country_qty(
        sku="sku-A",
        country="JP",
        country_qty=100,
        orders=[],
        rules=_jp_rules(),
        country_warehouses=[],
    )
    assert result == {}


def test_zero_data_ignores_non_rule_warehouse() -> None:
    """兜底均分时，只允许已配置邮编规则的仓参与。"""
    result = split_country_qty(
        sku="sku-A",
        country="JP",
        country_qty=9,
        orders=[],
        rules=_jp_rules(),
        country_warehouses=["haiyuan"],
    )

    assert result == {"haiyuan": 9}


def test_zero_country_qty() -> None:
    result = split_country_qty(
        sku="sku-A",
        country="JP",
        country_qty=0,
        orders=[("640-8453", 5)],
        rules=_jp_rules(),
        country_warehouses=["haiyuan", "xiapu"],
    )
    assert result == {}


def test_single_known_warehouse_gets_all() -> None:
    """所有匹配订单都落在同一仓 -> 100% 分配。"""
    orders = [("640-8453", 10), ("550-0000", 10)]
    result = split_country_qty(
        sku="sku-A",
        country="JP",
        country_qty=200,
        orders=orders,
        rules=_jp_rules(),
        country_warehouses=["haiyuan", "xiapu"],
    )
    assert result == {"haiyuan": 200}


def test_total_preserved_no_loss_to_rounding() -> None:
    """分配后的总和必须等于 country_qty,不能因四舍五入丢失件数。"""
    orders = [
        ("640-8453", 7),
        ("550-0000", 11),
        ("100-0001", 13),
    ]
    result = split_country_qty(
        sku="sku-A",
        country="JP",
        country_qty=997,  # 故意用质数
        orders=orders,
        rules=_jp_rules(),
        country_warehouses=["haiyuan", "xiapu"],
    )
    assert sum(result.values()) == 997


def _tied_rules_p10() -> list[ZipcodeRule]:
    """B/C/D/E 四仓 priority=10 都含 451-599。"""
    return [
        ZipcodeRule(
            id=10,
            country="JP",
            prefix_length=3,
            value_type="number",
            operator="between",
            compare_value="271-450, 451-599",
            warehouse_id="B",
            priority=10,
        ),
        ZipcodeRule(
            id=11,
            country="JP",
            prefix_length=3,
            value_type="number",
            operator="between",
            compare_value="451-599, 851-999",
            warehouse_id="C",
            priority=10,
        ),
        ZipcodeRule(
            id=12,
            country="JP",
            prefix_length=3,
            value_type="number",
            operator="between",
            compare_value="451-599",
            warehouse_id="D",
            priority=10,
        ),
        ZipcodeRule(
            id=13,
            country="JP",
            prefix_length=3,
            value_type="number",
            operator="between",
            compare_value="451-599, 600-850",
            warehouse_id="E",
            priority=10,
        ),
    ]


def test_step5_tied_even_split_across_four_warehouses() -> None:
    """1 条 qty=8 订单落在 451-599,tied 4 仓各得 2 权重,country_qty=100 时各得 25。"""
    result = explain_country_qty_split(
        sku="sku-A",
        country="JP",
        country_qty=100,
        orders=[("500-0001", 8)],
        rules=_tied_rules_p10(),
        country_warehouses=["B", "C", "D", "E"],
    )
    assert result.allocation_mode == "matched"
    assert result.matched_order_qty == 8
    assert result.unknown_order_qty == 0
    assert result.warehouse_breakdown == {"B": 25, "C": 25, "D": 25, "E": 25}


def test_step5_tied_filters_ineligible_warehouse() -> None:
    """4 tied 仓其中 D 不在 country_warehouses -> 按剩 B/C/E 三仓均分。"""
    result = explain_country_qty_split(
        sku="sku-A",
        country="JP",
        country_qty=90,
        orders=[("500-0001", 3)],
        rules=_tied_rules_p10(),
        country_warehouses=["B", "C", "E"],  # 故意不含 D
    )
    assert result.allocation_mode == "matched"
    assert result.matched_order_qty == 3
    assert result.unknown_order_qty == 0
    assert result.warehouse_breakdown == {"B": 30, "C": 30, "E": 30}


def test_step5_tied_all_ineligible_counts_as_unknown() -> None:
    """tied 4 仓全部不在 country_warehouses -> 该订单 qty 记为 unknown。"""
    result = explain_country_qty_split(
        sku="sku-A",
        country="JP",
        country_qty=20,
        orders=[("500-0001", 4), ("600-0001", 6)],
        rules=_tied_rules_p10(),
        country_warehouses=["otherWh"],
    )
    assert result.matched_order_qty == 0
    assert result.unknown_order_qty == 10
    assert result.allocation_mode == "fallback_even"
    assert result.warehouse_breakdown == {"otherWh": 20}


def test_four_warehouse_ceil_regression_sum_equals_country_qty() -> None:
    """Regression: math.ceil on warehouse split caused sum > country_qty.

    4 warehouses with equal order counts, country_qty=5.
    With ceil: ceil(5*0.25)=2 × 3 non-last = 6 > 5, last=max(5-6,0)=0 → sum=6≠5.
    Current largest-remainder allocation keeps the total exact without relying on
    a last-warehouse correction.
    """
    rules = [
        ZipcodeRule(
            id=1,
            country="JP",
            prefix_length=1,
            value_type="number",
            operator="=",
            compare_value="1",
            warehouse_id="WH-A",
            priority=10,
        ),
        ZipcodeRule(
            id=2,
            country="JP",
            prefix_length=1,
            value_type="number",
            operator="=",
            compare_value="2",
            warehouse_id="WH-B",
            priority=10,
        ),
        ZipcodeRule(
            id=3,
            country="JP",
            prefix_length=1,
            value_type="number",
            operator="=",
            compare_value="3",
            warehouse_id="WH-C",
            priority=10,
        ),
        ZipcodeRule(
            id=4,
            country="JP",
            prefix_length=1,
            value_type="number",
            operator="=",
            compare_value="4",
            warehouse_id="WH-D",
            priority=10,
        ),
    ]
    orders = [
        ("100-0000", 1),  # WH-A
        ("200-0000", 1),  # WH-B
        ("300-0000", 1),  # WH-C
        ("400-0000", 1),  # WH-D
    ]
    result = split_country_qty(
        sku="sku-A",
        country="JP",
        country_qty=5,
        orders=orders,
        rules=rules,
        country_warehouses=["WH-A", "WH-B", "WH-C", "WH-D"],
    )
    assert sum(result.values()) == 5


def test_matched_split_uses_largest_remainder_without_over_allocation() -> None:
    """3/3/3/1 权重分配 5 件时，总和必须保持 5，且不能靠最后一仓吸收负数。"""
    rules = [
        ZipcodeRule(
            id=1,
            country="JP",
            prefix_length=1,
            value_type="number",
            operator="=",
            compare_value="1",
            warehouse_id="WH-A",
            priority=10,
        ),
        ZipcodeRule(
            id=2,
            country="JP",
            prefix_length=1,
            value_type="number",
            operator="=",
            compare_value="2",
            warehouse_id="WH-B",
            priority=10,
        ),
        ZipcodeRule(
            id=3,
            country="JP",
            prefix_length=1,
            value_type="number",
            operator="=",
            compare_value="3",
            warehouse_id="WH-C",
            priority=10,
        ),
        ZipcodeRule(
            id=4,
            country="JP",
            prefix_length=1,
            value_type="number",
            operator="=",
            compare_value="4",
            warehouse_id="WH-D",
            priority=10,
        ),
    ]
    result = split_country_qty(
        sku="sku-A",
        country="JP",
        country_qty=5,
        orders=[
            ("100-0000", 3),
            ("200-0000", 3),
            ("300-0000", 3),
            ("400-0000", 1),
        ],
        rules=rules,
        country_warehouses=["WH-A", "WH-B", "WH-C", "WH-D"],
    )

    assert sum(result.values()) == 5
    assert result == {"WH-A": 2, "WH-B": 2, "WH-C": 1}


class _FakeDb:
    def __init__(self, rows: list[tuple[str, str]] | None = None) -> None:
        self.executed = []
        self.rows = rows or []

    async def execute(self, stmt):
        self.executed.append(stmt)
        return SimpleNamespace(all=lambda: self.rows)


@pytest.mark.asyncio
async def test_load_all_sku_country_orders_applies_allowed_country_filter() -> None:
    db = _FakeDb()

    await load_all_sku_country_orders(
        db,
        commodity_skus=["sku-A"],
        today=date(2026, 4, 8),
        allowed_countries={"US", "GB"},
    )

    compiled_sql = str(db.executed[0])
    assert "order_header.country_code IN" in compiled_sql


@pytest.mark.asyncio
async def test_load_country_warehouses_only_keeps_rule_warehouses_and_deduplicates() -> None:
    db = _FakeDb(
        rows=[
            ("JP", "WH-A"),
            ("JP", "WH-A"),
            ("JP", "WH-B"),
            ("US", "WH-Z"),
        ]
    )

    result = await load_country_warehouses(db)

    assert result == {
        "JP": ["WH-A", "WH-B"],
        "US": ["WH-Z"],
    }
