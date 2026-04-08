"""邮编→仓库匹配器。

实现 FR-034/034a：
- 归一化：strip + 去 '-' 与空格 → 截取前 N 位
- 按 priority 升序遍历规则，第一条命中即返回
- 全部未命中 → None（"未知仓"）
- 比较运算符：= != > >= < <=
- 值类型：number / string
"""

from dataclasses import dataclass


@dataclass
class ZipcodeRule:
    """简化的规则数据结构（与 ORM 解耦便于测试）。"""

    id: int
    country: str
    prefix_length: int
    value_type: str  # 'number' or 'string'
    operator: str  # '=' '!=' '>' '>=' '<' '<='
    compare_value: str
    warehouse_id: str
    priority: int


_OPERATORS = {"=", "!=", ">", ">=", "<", "<="}


def normalize_postal(code: str | None) -> str:
    """归一化邮编：trim + 去内部 - 与空格。"""
    if code is None:
        return ""
    return code.strip().replace("-", "").replace(" ", "")


def _extract_prefix(normalized: str, prefix_length: int) -> str:
    return normalized[:prefix_length]


def _compare(left: str, operator: str, right: str, value_type: str) -> bool:
    if operator not in _OPERATORS:
        return False
    if value_type == "number":
        try:
            l_val: float = float(left)
            r_val: float = float(right)
        except (TypeError, ValueError):
            return False
    else:
        l_val = left  # type: ignore[assignment]
        r_val = right  # type: ignore[assignment]

    if operator == "=":
        return l_val == r_val
    if operator == "!=":
        return l_val != r_val
    if operator == ">":
        return l_val > r_val
    if operator == ">=":
        return l_val >= r_val
    if operator == "<":
        return l_val < r_val
    if operator == "<=":
        return l_val <= r_val
    return False


def match_warehouse(
    postal_code: str | None,
    country: str,
    rules: list[ZipcodeRule],
) -> str | None:
    """对单个订单匹配仓库。

    返回仓库 id 或 None（未知仓）。
    rules 必须按 priority 升序传入（或在内部排序）。
    """
    normalized = normalize_postal(postal_code)
    if not normalized:
        return None
    country_rules = sorted(
        (r for r in rules if r.country == country),
        key=lambda r: r.priority,
    )
    for rule in country_rules:
        prefix = _extract_prefix(normalized, rule.prefix_length)
        if not prefix or len(prefix) < rule.prefix_length:
            continue
        if _compare(prefix, rule.operator, rule.compare_value, rule.value_type):
            return rule.warehouse_id
    return None
