"""邮编匹配器单元测试:归一化 + 各种 operator + priority。"""

from app.engine.zipcode_matcher import (
    ZipcodeRule,
    match_warehouse,
    match_warehouses,
    normalize_postal,
)


def _rule(
    rid: int,
    country: str,
    prefix: int,
    op: str,
    val: str,
    wh: str,
    *,
    priority: int = 100,
    value_type: str = "number",
) -> ZipcodeRule:
    return ZipcodeRule(
        id=rid,
        country=country,
        prefix_length=prefix,
        value_type=value_type,
        operator=op,
        compare_value=val,
        warehouse_id=wh,
        priority=priority,
    )


# ==================== normalize ====================
def test_normalize_strips_dash_and_space() -> None:
    assert normalize_postal("640-8453") == "6408453"
    assert normalize_postal("SW1A 1AA") == "SW1A1AA"
    assert normalize_postal(" 100 0001 ") == "1000001"
    assert normalize_postal(None) == ""
    assert normalize_postal("") == ""


# ==================== number 比较 ====================
def test_jp_number_ge_50_to_haiyuan() -> None:
    rules = [
        _rule(1, "JP", 2, ">=", "50", "haiyuan", priority=10),
        _rule(2, "JP", 2, "<", "50", "xiapu", priority=20),
    ]
    assert match_warehouse("640-8453", "JP", rules) == "haiyuan"  # 前2位 64 >= 50
    assert match_warehouse("500-0001", "JP", rules) == "haiyuan"  # 前2位 50 >= 50
    assert match_warehouse("050-0001", "JP", rules) == "xiapu"  # 前2位 05 < 50
    assert match_warehouse("100-0001", "JP", rules) == "xiapu"  # 前2位 10 < 50


def test_jp_priority_first_match_wins() -> None:
    """priority 小的先匹配;priority 10 命中后不再尝试 priority 20。"""
    rules = [
        _rule(1, "JP", 2, ">=", "50", "haiyuan", priority=10),
        _rule(2, "JP", 2, ">=", "00", "xiapu", priority=20),  # 永不被命中
    ]
    assert match_warehouse("640-8453", "JP", rules) == "haiyuan"
    # 即使 priority=20 也匹配 "00",但 priority=10 已经命中
    assert match_warehouse("100-0001", "JP", rules) == "xiapu"


def test_unmatched_returns_none() -> None:
    rules = [_rule(1, "JP", 2, ">", "99", "x", priority=10)]
    assert match_warehouse("100-0001", "JP", rules) is None


def test_country_filter() -> None:
    rules = [_rule(1, "JP", 2, ">=", "00", "jp_wh", priority=10)]
    # US 邮编不应匹配 JP 规则
    assert match_warehouse("90210", "US", rules) is None


# ==================== string 比较 ====================
def test_uk_string_eq() -> None:
    rules = [
        _rule(1, "UK", 2, "=", "SW", "uk_a", priority=10, value_type="string"),
        _rule(2, "UK", 2, "=", "EC", "uk_b", priority=20, value_type="string"),
    ]
    assert match_warehouse("SW1A 1AA", "UK", rules) == "uk_a"
    assert match_warehouse("EC1V 0HP", "UK", rules) == "uk_b"
    assert match_warehouse("NW1 7BD", "UK", rules) is None


def test_string_neq() -> None:
    rules = [_rule(1, "UK", 2, "!=", "SW", "default", priority=10, value_type="string")]
    assert match_warehouse("EC1V 0HP", "UK", rules) == "default"
    assert match_warehouse("SW1A 1AA", "UK", rules) is None


def test_string_contains_any_token() -> None:
    rules = [_rule(1, "UK", 4, "contains", "SW,EC", "uk_mix", priority=10, value_type="string")]

    assert match_warehouse("SW1A 1AA", "UK", rules) == "uk_mix"
    assert match_warehouse("EC1V 0HP", "UK", rules) == "uk_mix"
    assert match_warehouse("NW1 7BD", "UK", rules) is None


def test_string_not_contains_all_tokens() -> None:
    rules = [
        _rule(1, "UK", 4, "not_contains", "SW,EC", "uk_other", priority=10, value_type="string")
    ]

    assert match_warehouse("NW1 7BD", "UK", rules) == "uk_other"
    assert match_warehouse("SW1A 1AA", "UK", rules) is None
    assert match_warehouse("EC1V 0HP", "UK", rules) is None


# ==================== 操作符全覆盖 ====================
def test_all_operators() -> None:
    base = [
        ("=", "50", True, "050"),
        ("!=", "50", True, "060"),
        ("!=", "50", False, "050"),
        (">", "50", True, "060"),
        (">", "50", False, "050"),
        (">=", "50", True, "050"),
        ("<", "50", True, "040"),
        ("<", "50", False, "050"),
        ("<=", "50", True, "050"),
    ]
    for op, val, expected_match, postal in base:
        rules = [_rule(1, "JP", 3, op, val, "wh", priority=10)]
        result = match_warehouse(postal, "JP", rules)
        assert (result == "wh") == expected_match, f"{op} {val} vs {postal}"


# ==================== 边界 ====================
def test_prefix_too_short_skipped() -> None:
    """邮编长度 < prefix_length 时跳过该规则。"""
    rules = [_rule(1, "JP", 5, ">=", "10000", "wh", priority=10)]
    assert match_warehouse("123", "JP", rules) is None


def test_invalid_number_value() -> None:
    """数值类型遇到无法转换的字符串应跳过。"""
    rules = [_rule(1, "UK", 2, ">", "50", "wh", priority=10)]  # number 类型
    # SW 不能转 float
    assert match_warehouse("SW1A 1AA", "UK", rules) is None


# ==================== between 运算符 ====================
def test_between_single_segment_inclusive() -> None:
    rules = [_rule(1, "JP", 3, "between", "000-270", "wh_west", priority=10)]
    # 边界都命中
    assert match_warehouse("000-1111", "JP", rules) == "wh_west"
    assert match_warehouse("270-0001", "JP", rules) == "wh_west"
    # 中间值命中
    assert match_warehouse("100-0001", "JP", rules) == "wh_west"
    # 越界未命中
    assert match_warehouse("271-0001", "JP", rules) is None
    assert match_warehouse("999-0001", "JP", rules) is None


def test_between_multi_segment_any_hit() -> None:
    rules = [
        _rule(1, "JP", 3, "between", "000-270, 500-700", "wh_mix", priority=10),
    ]
    assert match_warehouse("050-0001", "JP", rules) == "wh_mix"  # 命中第一段
    assert match_warehouse("600-0001", "JP", rules) == "wh_mix"  # 命中第二段
    assert match_warehouse("400-0001", "JP", rules) is None      # 两段都不命中
    assert match_warehouse("800-0001", "JP", rules) is None


def test_between_leading_zero_prefix() -> None:
    """前 3 位 '050' 应解析为整数 50,落在 000-270 范围内。"""
    rules = [_rule(1, "JP", 3, "between", "000-270", "wh_west", priority=10)]
    assert match_warehouse("050-0001", "JP", rules) == "wh_west"


def test_between_priority_still_first_wins() -> None:
    rules = [
        _rule(1, "JP", 3, "between", "000-270", "wh_a", priority=10),
        _rule(2, "JP", 3, "between", "000-999", "wh_b", priority=20),
    ]
    # 100 同时满足两段,但 priority=10 先命中
    assert match_warehouse("100-0001", "JP", rules) == "wh_a"
    # 500 只落在第二段
    assert match_warehouse("500-0001", "JP", rules) == "wh_b"


def test_between_invalid_format_returns_none() -> None:
    """格式错误的 compare_value 不应让 matcher 抛异常,返回 None。"""
    rules = [_rule(1, "JP", 3, "between", "abc-xyz", "wh", priority=10)]
    assert match_warehouse("100-0001", "JP", rules) is None


def test_between_non_numeric_prefix_skipped() -> None:
    """UK 邮编前缀 'SW1' 不能转 int,between 规则跳过返回 None。"""
    rules = [_rule(1, "UK", 3, "between", "000-999", "wh", priority=10)]
    assert match_warehouse("SW1A 1AA", "UK", rules) is None


# ==================== match_warehouses tied ====================
def _tied_rules() -> list[ZipcodeRule]:
    """B/C/D/E 四仓 priority=10 都含 451-599;只在其他段上互不重叠。"""
    return [
        _rule(10, "JP", 3, "between", "271-450, 451-599", "B", priority=10),
        _rule(11, "JP", 3, "between", "451-599, 851-999", "C", priority=10),
        _rule(12, "JP", 3, "between", "451-599", "D", priority=10),
        _rule(13, "JP", 3, "between", "451-599, 600-850", "E", priority=10),
    ]


def test_tied_same_priority_returns_all_winners() -> None:
    """postal 500 落在 451-599,B/C/D/E 四仓全部命中,按 rule.id 升序返回。"""
    rules = _tied_rules()
    assert match_warehouses("500-0001", "JP", rules) == ["B", "C", "D", "E"]


def test_tied_higher_priority_absorbs_lower() -> None:
    """priority=10 单命中屏蔽 priority=20 的 tied 候选。"""
    rules = [
        _rule(1, "JP", 3, "between", "451-599", "wh_p10", priority=10),
        _rule(2, "JP", 3, "between", "451-599", "wh_p20_a", priority=20),
        _rule(3, "JP", 3, "between", "451-599", "wh_p20_b", priority=20),
    ]
    # priority=10 单独命中,列表长度 1
    assert match_warehouses("500-0001", "JP", rules) == ["wh_p10"]


def test_tied_deduplicates_same_warehouse() -> None:
    """同一 warehouse_id 被两条 tied 规则写入时,只返回一次。"""
    rules = [
        _rule(1, "JP", 3, "between", "451-599", "wh_A", priority=10),
        _rule(2, "JP", 3, "between", "451-599", "wh_A", priority=10),
        _rule(3, "JP", 3, "between", "451-599", "wh_B", priority=10),
    ]
    assert match_warehouses("500-0001", "JP", rules) == ["wh_A", "wh_B"]


def test_tied_deterministic_order_by_rule_id() -> None:
    """同 priority 内输入顺序乱序时,返回顺序仍按 rule.id 升序。"""
    rules = [
        _rule(5, "JP", 3, "between", "451-599", "wh_late", priority=10),
        _rule(2, "JP", 3, "between", "451-599", "wh_early", priority=10),
    ]
    assert match_warehouses("500-0001", "JP", rules) == ["wh_early", "wh_late"]
