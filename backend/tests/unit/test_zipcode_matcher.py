"""邮编匹配器单元测试：归一化 + 各种 operator + priority。"""

from app.engine.zipcode_matcher import ZipcodeRule, match_warehouse, normalize_postal


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
    assert match_warehouse("640-8453", "JP", rules) == "haiyuan"
    assert match_warehouse("050-0001", "JP", rules) == "haiyuan"
    assert match_warehouse("100-0001", "JP", rules) == "xiapu"


def test_jp_priority_first_match_wins() -> None:
    """priority 小的先匹配；priority 10 命中后不再尝试 priority 20。"""
    rules = [
        _rule(1, "JP", 2, ">=", "50", "haiyuan", priority=10),
        _rule(2, "JP", 2, ">=", "00", "xiapu", priority=20),  # 永不被命中
    ]
    assert match_warehouse("640-8453", "JP", rules) == "haiyuan"
    # 即使 priority=20 也匹配 "00"，但 priority=10 已经命中
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
