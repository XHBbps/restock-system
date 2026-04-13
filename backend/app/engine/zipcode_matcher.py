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
            left_int = int(left)
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
            if lo <= left_int <= hi:
                return True
        return False

    if value_type == "number":
        try:
            left_num = float(left)
            right_num = float(right)
        except (TypeError, ValueError):
            return False

        if operator == "=":
            return int(left_num) == int(right_num)  # P2-6: 整数比较避免浮点精度
        if operator == "!=":
            return int(left_num) != int(right_num)
        if operator == ">":
            return left_num > right_num
        if operator == ">=":
            return left_num >= right_num
        if operator == "<":
            return left_num < right_num
        if operator == "<=":
            return left_num <= right_num
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


def match_warehouses(
    postal_code: str | None,
    country: str,
    rules: list[ZipcodeRule],
) -> list[str]:
    """返回所有并列命中（同最低优先级）的仓库 id 列表。

    空列表 = 未匹配;长度 1 = 单仓命中;长度 ≥ 2 = tied。
    同 priority 内按 rule.id 升序枚举,按 warehouse_id 去重后返回。
    """
    normalized = normalize_postal(postal_code)
    if not normalized:
        return []
    country_rules = sorted(
        (r for r in rules if r.country == country),
        key=lambda r: (r.priority, r.id),
    )
    winners: list[str] = []
    seen: set[str] = set()
    winning_priority: int | None = None
    for rule in country_rules:
        # 首次命中前 winning_priority 仍为 None,不参与比较;
        # 命中后若后续规则 priority 已大于首批命中的 priority,立刻收摊
        if winning_priority is not None and rule.priority > winning_priority:
            break
        prefix = _extract_prefix(normalized, rule.prefix_length)
        if not prefix or len(prefix) < rule.prefix_length:
            continue
        if _compare(prefix, rule.operator, rule.compare_value, rule.value_type):
            if winning_priority is None:
                winning_priority = rule.priority
            if rule.warehouse_id not in seen:
                seen.add(rule.warehouse_id)
                winners.append(rule.warehouse_id)
    return winners
