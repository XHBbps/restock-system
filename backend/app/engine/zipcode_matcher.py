"""邮编->仓库匹配器。

实现 FR-034/034a:
- 归一化:strip + 去 '-' 与空格 -> 截取前 N 位
- 按 priority 升序遍历规则,第一条命中即返回
- 全部未命中 -> None("未知仓")
- 比较运算符:= != > >= < <= contains not_contains
- 值类型:number / string
"""

from dataclasses import dataclass


@dataclass
class ZipcodeRule:
    """简化的规则数据结构(与 ORM 解耦便于测试)。"""

    id: int
    country: str
    prefix_length: int
    value_type: str  # 'number' or 'string'
    operator: str  # '=' '!=' '>' '>=' '<' '<=' 'contains' 'not_contains'
    compare_value: str
    warehouse_id: str
    priority: int


_OPERATORS = {"=", "!=", ">", ">=", "<", "<=", "contains", "not_contains", "between"}


def normalize_postal(code: str | None) -> str:
    """归一化邮编:trim + 去内部 - 与空格。"""
    if code is None:
        return ""
    return code.strip().replace("-", "").replace(" ", "")


def _extract_prefix(normalized: str, prefix_length: int) -> str:
    return normalized[:prefix_length]


def _split_compare_values(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def _compare(left: str, operator: str, right: str, value_type: str) -> bool:
    if operator not in _OPERATORS:
        return False

    if operator == "between":
        # between 仅支持数字;prefix 以整数解析(保留前导零语义)
        try:
            l_num = int(left)
        except (TypeError, ValueError):
            return False
        for chunk in right.split(","):
            piece = chunk.strip()
            if not piece:
                continue
            parts = piece.split("-", 1)
            if len(parts) != 2:
                return False
            try:
                lo = int(parts[0].strip())
                hi = int(parts[1].strip())
            except ValueError:
                return False
            if lo > hi:
                return False
            if lo <= l_num <= hi:
                return True
        return False

    if value_type == "number":
        try:
            l_num = float(left)
            r_num = float(right)
        except (TypeError, ValueError):
            return False

        if operator == "=":
            return l_num == r_num
        if operator == "!=":
            return l_num != r_num
        if operator == ">":
            return l_num > r_num
        if operator == ">=":
            return l_num >= r_num
        if operator == "<":
            return l_num < r_num
        if operator == "<=":
            return l_num <= r_num
        return False
    else:
        l_str = left
        r_str = right
        compare_values: list[str] = _split_compare_values(r_str)

        if operator == "=":
            return l_str == r_str
        if operator == "!=":
            return l_str != r_str
        if operator == "contains":
            return bool(compare_values) and any(token in l_str for token in compare_values)
        if operator == "not_contains":
            return bool(compare_values) and all(token not in l_str for token in compare_values)
        return False


def match_warehouse(
    postal_code: str | None,
    country: str,
    rules: list[ZipcodeRule],
) -> str | None:
    """对单个订单匹配仓库。

    返回仓库 id 或 None(未知仓)。
    rules 必须按 priority 升序传入(或在内部排序)。
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
