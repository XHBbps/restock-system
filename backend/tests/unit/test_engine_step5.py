"""Step 5 仓内分配单元测试：真实分布 + 零数据兜底。"""

from app.engine.step5_warehouse_split import split_country_qty
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
    """3 单 海源 + 2 单 夏普 → 60/40 分配 100 件。"""
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
    # 已知仓只有 haiyuan，应得全部 50
    assert result == {"haiyuan": 50}


def test_zero_data_fallback_even_split() -> None:
    """零样本兜底：均分到所有已维护海外仓。"""
    result = split_country_qty(
        sku="sku-A",
        country="JP",
        country_qty=100,
        orders=[],  # 零订单
        rules=_jp_rules(),
        country_warehouses=["haiyuan", "xiapu", "third"],
    )
    # 100 / 3 = 33 余 1 → 34/33/33
    assert sum(result.values()) == 100
    assert len(result) == 3
    assert max(result.values()) - min(result.values()) <= 1


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
    """所有匹配订单都落在同一仓 → 100% 分配。"""
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
    """分配后的总和必须等于 country_qty，不能因四舍五入丢失件数。"""
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
