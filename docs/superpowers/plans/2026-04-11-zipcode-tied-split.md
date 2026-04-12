# 邮编规则同优先级 tied 均分 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `zipcode_rule` 在多个仓库同优先级命中一条订单时，按 1/N 均分该订单 qty 到 tied 仓的 `known_counts`，最终 step5 按对称比例分配需求。

**Architecture:** 把 `match_warehouse` 改名为 `match_warehouses` 并改返回 `list[str]`（所有首批同 priority 命中的仓）；step5 消费端迭代 winners 按 `qty / N` 累加到 `known_counts`（类型 `int → float`）。全程纯引擎逻辑改动，不触碰 DB / API / 前端 / schema。

**Tech Stack:** Python 3.12 / SQLAlchemy 2 / pytest

**Spec**: [docs/superpowers/specs/2026-04-11-zipcode-tied-split-design.md](../specs/2026-04-11-zipcode-tied-split-design.md)

---

## File Structure

- Modify: `backend/app/engine/zipcode_matcher.py` — 新增 `match_warehouses`；Task 3 删除旧 `match_warehouse`
- Modify: `backend/app/engine/step5_warehouse_split.py` — 切换到 `match_warehouses`，`known_counts: int → float`
- Modify: `backend/tests/unit/test_zipcode_matcher.py` — Task 1 追加 4 条 tied 测试；Task 3 机械更新既有断言
- Modify: `backend/tests/unit/test_engine_step5.py` — Task 2 追加 3 条 tied 测试
- Modify: `docs/PROGRESS.md` — Task 4 在 §3 追加 2026-04-11 条目
- Modify: `docs/Project_Architecture_Blueprint.md` — Task 4 更新 step5 描述 + zipcode_rule 使用提示

## 执行顺序与渐进安全

为了每个 Task 结束都能让 `pytest tests/unit -q` 全绿，采用**并存式重构**：

1. **Task 1** 新增 `match_warehouses`（旧 `match_warehouse` 保留）+ 4 新 matcher 测试 → 全绿
2. **Task 2** step5 切到 `match_warehouses` + 3 新 step5 测试 → 全绿（旧 `match_warehouse` 仍在，但已无生产调用方）
3. **Task 3** 机械更新既有 matcher 测试的 `match_warehouse → match_warehouses`，然后删除旧函数 → 全绿
4. **Task 4** 文档同步 → 无代码改动
5. **Task 5** 端到端验证 → pytest 全绿

---

## Task 1: 新增 `match_warehouses` 函数及 tied 测试

**Files:**
- Modify: `backend/app/engine/zipcode_matcher.py`
- Modify: `backend/tests/unit/test_zipcode_matcher.py`

- [ ] **Step 1: 写失败测试 — 4 条仓库同优先级都命中 451-599**

在 `backend/tests/unit/test_zipcode_matcher.py` 末尾追加（顶部 import 区先补 `match_warehouses`，注意不要删除 `match_warehouse` —— 旧函数仍在 Task 3 才删）：

改 import 行（第 3 行附近）：

```python
from app.engine.zipcode_matcher import (
    ZipcodeRule,
    match_warehouse,
    match_warehouses,
    normalize_postal,
)
```

在文件末尾追加：

```python
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
```

- [ ] **Step 2: 跑测试确认 fail**

Run: `cd backend && pytest tests/unit/test_zipcode_matcher.py::test_tied_same_priority_returns_all_winners -v`
Expected: FAIL（`ImportError: cannot import name 'match_warehouses'` 或 `AttributeError`）。

- [ ] **Step 3: 实现 `match_warehouses`**

在 `backend/app/engine/zipcode_matcher.py` 文件末尾（原 `match_warehouse` 函数之后）追加：

```python
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
```

不要删除 / 修改任何其它已有函数（`match_warehouse` / `_compare` / `normalize_postal` 等保持原样）。

- [ ] **Step 4: 跑测试确认 pass**

Run: `cd backend && pytest tests/unit/test_zipcode_matcher.py::test_tied_same_priority_returns_all_winners -v`
Expected: PASS。

- [ ] **Step 5: 追加剩余 3 条 tied 测试**

继续追加到 `backend/tests/unit/test_zipcode_matcher.py`：

```python
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
```

- [ ] **Step 6: 跑全部 matcher 测试**

Run: `cd backend && pytest tests/unit/test_zipcode_matcher.py -v`
Expected: 所有既有测试 PASS（因为 `match_warehouse` 未动）+ 4 条新 tied 测试 PASS。

- [ ] **Step 7: 跑全量后端测试确认无回归**

Run: `cd backend && pytest tests/unit -q`
Expected: 全绿。

- [ ] **Step 8: commit**

```bash
git add backend/app/engine/zipcode_matcher.py backend/tests/unit/test_zipcode_matcher.py
git commit -m "feat(zipcode): add match_warehouses returning tied winners list"
```

---

## Task 2: Step5 消费端切换到 `match_warehouses` + 新 tied 测试

**Files:**
- Modify: `backend/app/engine/step5_warehouse_split.py`
- Modify: `backend/tests/unit/test_engine_step5.py`

- [ ] **Step 1: 写失败测试 — tied 均分**

在 `backend/tests/unit/test_engine_step5.py` 末尾追加：

```python
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
    # 4 仓权重相等 -> 100 均分为 25 25 25 25
    assert result.warehouse_breakdown == {"B": 25, "C": 25, "D": 25, "E": 25}
```

- [ ] **Step 2: 跑测试确认 fail**

Run: `cd backend && pytest tests/unit/test_engine_step5.py::test_step5_tied_even_split_across_four_warehouses -v`
Expected: FAIL（`match_warehouse` 当前首条命中语义下，只有 `B` 拿到 8，结果会是 `{"B": 100}` 而非均分）。

- [ ] **Step 3: 修改 `step5_warehouse_split.py`**

**3a)** 顶部 import 行改为：

```python
from app.engine.zipcode_matcher import ZipcodeRule, match_warehouses
```

（把 `match_warehouse` 从 import 列表里删掉；把 `match_warehouses` 加进去。注意一定要确认旧函数 import 不再被引用 —— Task 3 才会删除旧函数定义本身，这里只是 step5 文件内部不再 import 它。）

**3b)** 找到 `explain_country_qty_split` 函数内的订单归集循环（当前位于 163-174 行附近），替换为：

```python
    # 已知仓件数统计
    known_counts: defaultdict[str, float] = defaultdict(float)
    matched_order_qty = 0
    unknown_order_qty = 0
    for postal_code, qty in orders:
        if qty <= 0:
            continue
        winners = match_warehouses(postal_code, country, rules)
        eligible_winners = [w for w in winners if w in eligible_set]
        if not eligible_winners:
            unknown_order_qty += qty
            continue
        share = qty / len(eligible_winners)
        for wid in eligible_winners:
            known_counts[wid] += share
        matched_order_qty += qty
```

关键变化：
- `known_counts: defaultdict[str, int]` → `defaultdict[str, float]`
- `wid = match_warehouse(...)` → `winners = match_warehouses(...)`
- 先按 `eligible_set` 过滤 winners，再均分（保证 tied 仓中若有不 eligible 的，share 基数按剩余数量算）
- 只要还有至少 1 个 `eligible_winners`，订单 qty 就计入 `matched_order_qty`（否则归 unknown）

函数其它部分（`total_known` / 按比例分配 / 零数据 fallback / return）**全部保持原样**，不要顺手修改。

- [ ] **Step 4: 跑新测试确认 pass**

Run: `cd backend && pytest tests/unit/test_engine_step5.py::test_step5_tied_even_split_across_four_warehouses -v`
Expected: PASS。

- [ ] **Step 5: 追加剩余 2 条 step5 tied 测试**

继续追加到 `backend/tests/unit/test_engine_step5.py`：

```python
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
    # 3 仓等权 -> 90 平分 -> 30/30/30
    assert result.warehouse_breakdown == {"B": 30, "C": 30, "E": 30}


def test_step5_tied_all_ineligible_counts_as_unknown() -> None:
    """tied 4 仓全部不在 country_warehouses -> 该订单 qty 记为 unknown。"""
    result = explain_country_qty_split(
        sku="sku-A",
        country="JP",
        country_qty=20,
        orders=[("500-0001", 4), ("600-0001", 6)],  # 600 落在 E 的 600-850 段
        rules=_tied_rules_p10(),
        country_warehouses=["otherWh"],  # B/C/D/E 全部不在
    )
    # 两条订单的 4+6=10 件全部归 unknown
    assert result.matched_order_qty == 0
    assert result.unknown_order_qty == 10
    # 零已知 -> fallback_even 均分到 otherWh
    assert result.allocation_mode == "fallback_even"
    assert result.warehouse_breakdown == {"otherWh": 20}
```

- [ ] **Step 6: 跑完整 step5 测试文件**

Run: `cd backend && pytest tests/unit/test_engine_step5.py -v`
Expected: 所有既有测试 PASS（老用例都是单命中场景，行为等价；注意 `test_unknown_warehouse_excluded_from_denominator` 用 `split_country_qty` 外层函数调用，仍走新实现）+ 3 条新测试 PASS。

- [ ] **Step 7: 跑全量后端测试**

Run: `cd backend && pytest tests/unit -q`
Expected: 全绿。

- [ ] **Step 8: commit**

```bash
git add backend/app/engine/step5_warehouse_split.py backend/tests/unit/test_engine_step5.py
git commit -m "feat(engine): step5 splits tied-priority orders evenly across winners"
```

---

## Task 3: 机械迁移既有 matcher 测试 + 删除旧函数

**Files:**
- Modify: `backend/tests/unit/test_zipcode_matcher.py`
- Modify: `backend/app/engine/zipcode_matcher.py`

**说明**：此 task 把 `test_zipcode_matcher.py` 里所有对旧 `match_warehouse` 的调用改用 `match_warehouses`，同时把单字符串返回值断言改为单元素列表、`is None` 改为 `== []`。完成后删除旧函数定义，确保 `git grep match_warehouse` 仅残留在 spec / plan 文档。

- [ ] **Step 1: 核对当前调用点**

Run: `cd /e/Ai_project/restock_system && git grep -n 'match_warehouse\b' backend/ | grep -v 'match_warehouses'`

预期命中：
- `backend/app/engine/zipcode_matcher.py:110`（旧函数定义本体 — Step 5 要删）
- `backend/tests/unit/test_zipcode_matcher.py` 里若干行（import 行 + 断言行）
- 不应有 `backend/app/engine/step5_warehouse_split.py` 的命中（Task 2 已切换）

若在 step5 文件里仍有命中，立即 STOP 并报告：说明 Task 2 的 import 修改没到位。

- [ ] **Step 2: 修改 import 行**

在 `backend/tests/unit/test_zipcode_matcher.py` 文件顶部（第 3 行附近），把原先：

```python
from app.engine.zipcode_matcher import (
    ZipcodeRule,
    match_warehouse,
    match_warehouses,
    normalize_postal,
)
```

改成：

```python
from app.engine.zipcode_matcher import ZipcodeRule, match_warehouses, normalize_postal
```

（删除 `match_warehouse,` 一行）

- [ ] **Step 3: 批量重命名调用点**

使用 Edit 工具的 `replace_all=true` 模式：把 `match_warehouse(` 全部替换为 `match_warehouses(`。

Edit 参数：
- `file_path`: `backend/tests/unit/test_zipcode_matcher.py`
- `old_string`: `match_warehouse(`
- `new_string`: `match_warehouses(`
- `replace_all`: `true`

此时测试里所有形如 `assert match_warehouse(...) == "wh_x"` 的断言都已改成 `assert match_warehouses(...) == "wh_x"`，但右值仍是字符串，会在运行时失败 —— Step 4 修复。

- [ ] **Step 4: 修复返回值断言 —— 单字符串 → 单元素列表**

Read 当前 `backend/tests/unit/test_zipcode_matcher.py` 全文，逐条修改 assert。以下是完整的 before/after 映射表（基于 Task 1 完成后的文件状态，含 between 测试和新 tied 测试）。

对文件里每一处以下模式的行应用 Edit：

| 操作 | old_string | new_string |
|---|---|---|
| `haiyuan` 单命中 | `match_warehouses("640-8453", "JP", rules) == "haiyuan"` | `match_warehouses("640-8453", "JP", rules) == ["haiyuan"]` |
| `haiyuan` 边界 | `match_warehouses("500-0001", "JP", rules) == "haiyuan"` | `match_warehouses("500-0001", "JP", rules) == ["haiyuan"]` |
| `xiapu` 单命中 | `match_warehouses("050-0001", "JP", rules) == "xiapu"` | `match_warehouses("050-0001", "JP", rules) == ["xiapu"]` |
| `xiapu` 其它 | `match_warehouses("100-0001", "JP", rules) == "xiapu"` | `match_warehouses("100-0001", "JP", rules) == ["xiapu"]` |
| uk_a | `match_warehouses("SW1A 1AA", "UK", rules) == "uk_a"` | `match_warehouses("SW1A 1AA", "UK", rules) == ["uk_a"]` |
| uk_b | `match_warehouses("EC1V 0HP", "UK", rules) == "uk_b"` | `match_warehouses("EC1V 0HP", "UK", rules) == ["uk_b"]` |
| default 字符串 `!=` | `match_warehouses("EC1V 0HP", "UK", rules) == "default"` | `match_warehouses("EC1V 0HP", "UK", rules) == ["default"]` |
| uk_mix contains | `match_warehouses("SW1A 1AA", "UK", rules) == "uk_mix"` | `match_warehouses("SW1A 1AA", "UK", rules) == ["uk_mix"]` |
| uk_mix contains 2 | `match_warehouses("EC1V 0HP", "UK", rules) == "uk_mix"` | `match_warehouses("EC1V 0HP", "UK", rules) == ["uk_mix"]` |
| uk_other not_contains | `match_warehouses("NW1 7BD", "UK", rules) == "uk_other"` | `match_warehouses("NW1 7BD", "UK", rules) == ["uk_other"]` |
| wh_west 边界 1 | `match_warehouses("000-1111", "JP", rules) == "wh_west"` | `match_warehouses("000-1111", "JP", rules) == ["wh_west"]` |
| wh_west 边界 2 | `match_warehouses("270-0001", "JP", rules) == "wh_west"` | `match_warehouses("270-0001", "JP", rules) == ["wh_west"]` |
| wh_west 中间 | `match_warehouses("100-0001", "JP", rules) == "wh_west"` | `match_warehouses("100-0001", "JP", rules) == ["wh_west"]` |
| wh_mix 第一段 | `match_warehouses("050-0001", "JP", rules) == "wh_mix"` | `match_warehouses("050-0001", "JP", rules) == ["wh_mix"]` |
| wh_mix 第二段 | `match_warehouses("600-0001", "JP", rules) == "wh_mix"` | `match_warehouses("600-0001", "JP", rules) == ["wh_mix"]` |
| wh_west leading zero | `match_warehouses("050-0001", "JP", rules) == "wh_west"` | `match_warehouses("050-0001", "JP", rules) == ["wh_west"]` |
| wh_a priority | `match_warehouses("100-0001", "JP", rules) == "wh_a"` | `match_warehouses("100-0001", "JP", rules) == ["wh_a"]` |
| wh_b priority | `match_warehouses("500-0001", "JP", rules) == "wh_b"` | `match_warehouses("500-0001", "JP", rules) == ["wh_b"]` |

**特殊情况** —— `test_all_operators` 的参数化断言（当前大约 119-123 行）：

```python
    for op, val, expected_match, postal in base:
        rules = [_rule(1, "JP", 3, op, val, "wh", priority=10)]
        result = match_warehouses(postal, "JP", rules)
        assert (result == "wh") == expected_match, f"{op} {val} vs {postal}"
```

改为：

```python
    for op, val, expected_match, postal in base:
        rules = [_rule(1, "JP", 3, op, val, "wh", priority=10)]
        result = match_warehouses(postal, "JP", rules)
        assert (result == ["wh"]) == expected_match, f"{op} {val} vs {postal}"
```

- [ ] **Step 5: 修复未命中断言 —— `is None` → `== []`**

对文件里所有形如 `assert match_warehouses(...) is None` 的断言，逐条改为 `assert match_warehouses(...) == []`。

Edit 参数示例（每处独立，old_string 要带足上下文保证唯一）：

- `assert match_warehouses("100-0001", "JP", rules) is None` → `assert match_warehouses("100-0001", "JP", rules) == []`
- `assert match_warehouses("90210", "US", rules) is None` → `assert match_warehouses("90210", "US", rules) == []`
- `assert match_warehouses("NW1 7BD", "UK", rules) is None` → `assert match_warehouses("NW1 7BD", "UK", rules) == []`
- `assert match_warehouses("SW1A 1AA", "UK", rules) is None` → `assert match_warehouses("SW1A 1AA", "UK", rules) == []`
- `assert match_warehouses("EC1V 0HP", "UK", rules) is None` → `assert match_warehouses("EC1V 0HP", "UK", rules) == []`
- `assert match_warehouses("123", "JP", rules) is None` → `assert match_warehouses("123", "JP", rules) == []`
- `assert match_warehouses("271-0001", "JP", rules) is None` → `assert match_warehouses("271-0001", "JP", rules) == []`
- `assert match_warehouses("999-0001", "JP", rules) is None` → `assert match_warehouses("999-0001", "JP", rules) == []`
- `assert match_warehouses("400-0001", "JP", rules) is None` → `assert match_warehouses("400-0001", "JP", rules) == []`
- `assert match_warehouses("800-0001", "JP", rules) is None` → `assert match_warehouses("800-0001", "JP", rules) == []`

注意：某些邮编字符串（如 `"100-0001"`）在文件里出现过多次，每次 Edit 必须用足够长的 `old_string` 带上下文（比如带前后的 `assert` 和函数名）保证 `old_string` 在文件里唯一。若 Edit 报 "multiple matches"，用更长的上下文重试；或者用 `replace_all=false` 配合不同上下文逐次定位。

若同一处模式无法单次定位（罕见），则 Read 该段代码上下 5 行，再做精确 Edit。

- [ ] **Step 6: 跑完整 matcher 测试**

Run: `cd backend && pytest tests/unit/test_zipcode_matcher.py -v`
Expected: 全部既有测试 + 4 条 tied 测试 PASS。

若有 FAIL，Read 失败处，确认 Step 4/5 是否漏改；漏改一条立刻补。

- [ ] **Step 7: 删除旧 `match_warehouse` 函数**

Read `backend/app/engine/zipcode_matcher.py`，定位旧函数定义（约在文件第 110-133 行）。用 Edit 把整个 `def match_warehouse(...) -> str | None:` 函数块（从 `def match_warehouse` 开始到 return None 结束，包括前导空行和 docstring）完全删除。

删除后文件里只保留：
- `normalize_postal`
- `_extract_prefix`
- `_split_compare_values`
- `_compare`
- `match_warehouses`（新增的函数）
- `ZipcodeRule` dataclass
- `_OPERATORS` 常量

- [ ] **Step 8: 核对 grep 干净**

Run: `cd /e/Ai_project/restock_system && git grep -n 'match_warehouse\b' backend/ | grep -v 'match_warehouses'`
Expected: 无输出（或仅剩空行）—— 代码里完全没有对旧函数的引用。

`docs/` 下允许 spec / plan 文档保留旧函数名的历史引用，不需要改。

- [ ] **Step 9: 跑全量后端测试**

Run: `cd backend && pytest tests/unit -q`
Expected: 全绿（包括 154 原有 + 4 matcher tied + 3 step5 tied = 161 条左右）。

- [ ] **Step 10: commit**

```bash
git add backend/app/engine/zipcode_matcher.py backend/tests/unit/test_zipcode_matcher.py
git commit -m "refactor(zipcode): remove legacy match_warehouse, migrate tests"
```

---

## Task 4: 文档同步

**Files:**
- Modify: `docs/PROGRESS.md`
- Modify: `docs/Project_Architecture_Blueprint.md`

- [ ] **Step 1: 追加 PROGRESS.md §3 条目**

Read `docs/PROGRESS.md` 找到 §3 的当前最新条目（最近一次更新应为 2026-04-11 的 between 运算符条目 §3.13）。在其后追加：

```markdown
### 3.14 邮编规则同优先级 tied 均分

- 2026-04-11 — matcher 由 `match_warehouse(...) -> str | None` 重构为 `match_warehouses(...) -> list[str]`：按 `(priority, rule.id)` 排序后返回"首批同 priority 命中"的仓库列表，同 `warehouse_id` 去重。step5 消费端迭代 winners 按 `qty / N` 累加到 `known_counts`（类型由 `int` 改为 `float`；最终整数输出由下游 `round` + 尾仓兜底保证精确）。业务配置方式：把多条规则的 `priority` 填相同值即可触发均分，对任何 operator（`=`/`contains`/`between`…）自动适用。tied 仓中若有不在 `country_warehouses` 列表的，先过滤再按剩余数量均分。
```

- [ ] **Step 2: 更新 Project_Architecture_Blueprint.md step5 描述**

Read `docs/Project_Architecture_Blueprint.md`，Grep 定位 step5 在 6 步流水线的描述段落（Grep pattern `Step 5\|step5\|仓内分配`）。在 step5 说明末尾追加一句：

```markdown
**2026-04-11 起** 同优先级 tied 均分：若多条规则同优先级并列命中一条订单，该订单 qty 按 `1/N` 均分到 tied 仓的 `known_counts`（先按 `country_warehouses` 过滤不可用仓再定 N）；matcher 接口为 `match_warehouses(postal, country, rules) -> list[str]`。
```

- [ ] **Step 3: 更新 Project_Architecture_Blueprint.md zipcode_rule 使用提示**

同一文件中找到之前（Task 6 of between 工作）新增的 `#### zipcode_rule（邮编→仓库规则）` 子章节。在该章节末尾追加一条 bullet：

```markdown
- **tied 配置**：把多条规则的 `priority` 填相同值即触发同优先级均分；tied 定义基于命中该具体订单的最低 priority 批次，跨 operator 通用
```

- [ ] **Step 4: AGENTS.md §9.2 关闭清单自检**

逐项确认：
- [x] 触发 9.1：引擎 step 逻辑变化 → PROGRESS.md §3 + Architecture Blueprint step5 描述 ✅
- [x] 无 API 端点变化、无前端 view 变化、无 env var、无 migration
- [x] PROGRESS.md §3 已按日期 2026-04-11 追加（最近更新若有单独字段也同步为 2026-04-11）

- [ ] **Step 5: commit**

```bash
git add docs/PROGRESS.md docs/Project_Architecture_Blueprint.md
git commit -m "docs(zipcode): note tied-priority split in step5"
```

---

## Task 5: 端到端验证

**Files:** 无改动，纯验证。

- [ ] **Step 1: 跑后端全量单测**

Run: `cd backend && pytest tests/unit -q`
Expected: 全绿。比 Task 1 前多 4（matcher tied）+ 3（step5 tied）= 7 条通过。

- [ ] **Step 2: grep 确认无旧 API 残留**

Run: `cd /e/Ai_project/restock_system && git grep -n 'match_warehouse\b' -- 'backend/*.py' | grep -v 'match_warehouses'`
Expected: 无输出。

- [ ] **Step 3: 查看本次 commit 链**

Run: `git log --oneline 583f166..HEAD`
Expected: 4 条 commit
1. `feat(zipcode): add match_warehouses returning tied winners list` (Task 1)
2. `feat(engine): step5 splits tied-priority orders evenly across winners` (Task 2)
3. `refactor(zipcode): remove legacy match_warehouse, migrate tests` (Task 3)
4. `docs(zipcode): note tied-priority split in step5` (Task 4)

- [ ] **Step 4: 人工 sanity check（可选）**

读一遍 `backend/app/engine/zipcode_matcher.py` 确认 `match_warehouse` 真被删、`match_warehouses` 在文件里只出现一次定义。Read `backend/app/engine/step5_warehouse_split.py` 顶部 import 确认只 import `match_warehouses`。

---

## 验收标准

1. `cd backend && pytest tests/unit -q` 全绿（新增 7 条测试通过）
2. `git grep match_warehouse` 仅命中 `docs/superpowers/{specs,plans}/` 下的历史引用
3. `match_warehouses` 是 matcher 的唯一对外函数
4. step5 `known_counts` 类型为 `defaultdict[str, float]`
5. 4 条 commit 形成线性链；每条 commit 单独跑测试都通过
6. `docs/PROGRESS.md` §3.14 + `docs/Project_Architecture_Blueprint.md` step5 + `zipcode_rule` 使用提示都已同步

---

## 风险与回滚

**风险**：
1. Task 3 批量 Edit 过程中某条 `is None → == []` 漏改 → 对应测试 FAIL。缓解：Step 6 跑完整 matcher 测试会立即暴露。
2. `known_counts` float 化后，`round(country_qty * cnt / total_known)` 个别场景下 `last-wh 补余` 仍可能出现 +1/−1 微差 —— 但既有测试 `test_total_preserved_no_loss_to_rounding` 专门针对这个兜底，若通过即安全。
3. Task 2 import 行把 `match_warehouse` 删掉但还没换成 `match_warehouses` → `ImportError`。缓解：Task 2 Step 3 的指令要求同时替换。

**回滚路径**：`git revert` 本次 4 条 commit → 回到 first-match-wins 语义。无 DB / schema 变更，回滚零代价。
