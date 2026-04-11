"""Step 5 仓内分配单元测试:真实分布 + 零数据兜底。"""

from app.engine.step5_warehouse_split import explain_country_qty_split, split_country_qty
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
