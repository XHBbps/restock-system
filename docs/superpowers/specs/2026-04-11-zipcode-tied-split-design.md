# 邮编规则同优先级 tied 均分 — 设计 Spec

**日期**: 2026-04-11
**分支**: `001-saihu-replenishment`
**作者**: Claude (brainstorming skill)
**状态**: 待用户 review

---

## 1. 背景与动机

### 业务诉求

业务侧希望配置一批邮编规则时，**多个仓库可以共享同一段邮编范围**。例如：

| 仓库 | `compare_value` |
|---|---|
| A | `000-270` |
| B | `271-450, 451-599` |
| C | `451-599, 851-999` |
| D | `451-599` |
| E | `451-599, 600-850` |

其中 `451-599` 被 B/C/D/E 四个仓库共享。当一批订单进来，落在 `451-599` 的那部分 qty 应在这 4 个仓库间**动态均分**，最终 step5 的需求分配也应按等份摊到它们。

### 当前缺口

`backend/app/engine/zipcode_matcher.py:110` 的 `match_warehouse` 是**单返回**语义：按 priority 升序遍历，**首条命中即 return**。相同 priority 的多条 tied 规则中，只有第一条（受 Python `sorted` 的稳定排序影响，通常是 `id` 最小的那条）会拿到全部流量，其余 tied 规则是**死规则**。

`backend/app/engine/step5_warehouse_split.py:169`（`explain_country_qty_split` 函数内）通过 `match_warehouse` 逐订单归集 `known_counts[wid] += qty`，再按真实比例分配 `country_qty`。因此 tied 需求实际上 100% 被注入到某一个"赢家"，而不是均分。

### 设计目标

- 一条订单在多个 tied 仓命中时，qty 按 1/N 摊到每个 tied 仓的 `known_counts`
- 保留 priority 的"首批命中"语义：更高 priority 的命中仍然屏蔽更低 priority 的命中，只是"首批"从单条扩成"同 priority 的一整批"
- 不改 schema / 不加字段 / 不改前端表单 / 不改 API 契约
- 对任何 operator（不只 `between`）自动生效

---

## 2. Scope

### 变更面

| 层 | 文件 | 类型 |
|---|---|---|
| 引擎匹配器 | `backend/app/engine/zipcode_matcher.py` | 函数改名 + 签名变化 |
| 引擎 step5 消费端 | `backend/app/engine/step5_warehouse_split.py` | 更新调用 + `known_counts` 类型 |
| 匹配器单测 | `backend/tests/unit/test_zipcode_matcher.py` | 机械更新 18 处断言 + 新增 4 条 tied 测试 |
| step5 单测 | `backend/tests/unit/test_engine_step5.py` | 新增 3 条 tied 测试 |
| 文档同步 | `docs/PROGRESS.md` + `docs/Project_Architecture_Blueprint.md` | AGENTS.md §9.1 要求 |

### 非变更

- ❌ 不改 `zipcode_rule` 表 / 无 migration
- ❌ 不改 Pydantic schema / API 端点
- ❌ 不改前端表单 / `ZipcodeRuleView.vue`
- ❌ 不引入新的 operator 或配置字段
- ❌ 不处理"坏段容错"（上一轮已决定不做）

---

## 3. 组件设计

### 3.1 Matcher：`match_warehouses`（复数）

**签名**：

```python
def match_warehouses(
    postal_code: str | None,
    country: str,
    rules: list[ZipcodeRule],
) -> list[str]:
    """返回所有并列命中（同最低优先级）的仓库 id 列表。

    空列表 = 未匹配；长度 1 = 单仓命中；长度 ≥ 2 = tied。
    同 priority 内按 rule.id 升序枚举，去重后返回，保证确定性。
    """
```

**逻辑**：

```python
def match_warehouses(postal_code, country, rules):
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

**要点**：
- 排序键改为 `(priority, id)`，比现状 `priority` 单键多一层确定性——用于稳定 tied 内顺序
- 一旦首次命中，记录 `winning_priority`；后续扫描到 `priority > winning_priority` 的规则立刻 `break`
- 同一 `warehouse_id` 被多条 tied 规则写入时，`seen` 集合去重只算一份（防止同仓双倍计权）
- 旧函数 `match_warehouse` **完全删除**（不保留兼容 wrapper，系统里只有一个调用方）

### 3.2 Step5 消费端：`explain_country_qty_split`

替换 `backend/app/engine/step5_warehouse_split.py` 在 `explain_country_qty_split` 函数内原先的单命中循环（当前在 162-174 行附近）：

```python
# BEFORE
known_counts: defaultdict[str, int] = defaultdict(int)
matched_order_qty = 0
unknown_order_qty = 0
for postal_code, qty in orders:
    if qty <= 0:
        continue
    wid = match_warehouse(postal_code, country, rules)
    if wid is None or wid not in eligible_set:
        unknown_order_qty += qty
        continue
    known_counts[wid] += qty
    matched_order_qty += qty
```

改为：

```python
# AFTER
known_counts: defaultdict[str, float] = defaultdict(float)  # int → float
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

**要点**：
- `known_counts` 从 `defaultdict[str, int]` 变成 `defaultdict[str, float]`
- **先按 eligibility 过滤再按 N 均分**：tied 4 个仓中若 1 个不在 `eligible_set`（被删除 / 国家不匹配），则按剩 3 个均分，不浪费 1/4 份额到 unknown
- `matched_order_qty` 语义不变：只要还有至少 1 个 eligible winner，整条订单 qty 就计入 matched；全部不 eligible 才算 unknown
- 下游 `total_known = sum(known_counts.values())` 和 `round(country_qty * cnt / total_known)` 无需修改——`round(int * float / float)` 仍产出 int；"最后一仓补余数"的兜底逻辑继续成立

### 3.3 导入更新

- `backend/app/engine/step5_warehouse_split.py` 顶部 `from app.engine.zipcode_matcher import ZipcodeRule, match_warehouse` → `from app.engine.zipcode_matcher import ZipcodeRule, match_warehouses`
- `backend/tests/unit/test_zipcode_matcher.py` 顶部 `from app.engine.zipcode_matcher import ZipcodeRule, match_warehouse, normalize_postal` → `... match_warehouses ...`

---

## 4. 数据流示例

假设规则 B/C/D/E 全部 priority=10、都有 `between "451-599"` 段，country=JP。

**输入**：一批订单
```
[("500-0001", 8), ("300-0001", 4), ("700-0001", 3)]
```

**逐订单处理**：

| 订单 | `match_warehouses` 返回 | `eligible_winners`（假设全 eligible） | 每仓 `share` | 累加到 known_counts |
|---|---|---|---|---|
| ("500-0001", 8) | `["B","C","D","E"]` | 4 个 | 2.0 | B+=2, C+=2, D+=2, E+=2 |
| ("300-0001", 4) | `["B"]`（只有 B 的 271-450 段命中） | 1 个 | 4.0 | B+=4 |
| ("700-0001", 3) | `["E"]`（只有 E 的 600-850 段命中） | 1 个 | 3.0 | E+=3 |

**累计 known_counts**：`{B: 6.0, C: 2.0, D: 2.0, E: 5.0}`, `total_known = 15.0`

**假设 country_qty=150**：按比例分配得到 `{B: 60, C: 20, D: 20, E: 50}`（最后一仓 E 走 `country_qty - accumulated` 兜底，`60+20+20+50=150` 精确）

---

## 5. Edge cases

| 情形 | 行为 |
|---|---|
| 1 条 tied 规则命中（N=1） | `share = qty`，与老行为等价 ✅ |
| 完全未命中 | `winners = []` → `unknown_order_qty += qty` ✅ |
| 4 个 tied 仓中 1 个不在 `eligible_set` | 按剩 3 个均分 |
| 4 个 tied 仓全部不在 `eligible_set` | `eligible_winners = []` → 加到 `unknown_order_qty` |
| 同一 `warehouse_id` 被写成 2 条 tied 规则 | matcher 按 `warehouse_id` 去重，只算 1 份权重 |
| 低优先级 tie + 更低优先级单命中 | 只返回更低 priority 的那一批（可能 N=1 也可能 N≥2） |
| `qty=1`, N=4 | `share=0.25`，累积到 `known_counts`；最终整数输出由下游 `round` 处理 |
| 空邮编 / `None` / 归一化后为空 | `normalize_postal == ""` → `match_warehouses` 返回 `[]` ✅ 等价旧行为 |
| 前缀长度不足（订单邮编太短） | 对应规则 `continue` 跳过；其它同 priority 的规则仍可能命中 |
| 非数字前缀遇到 `between` 规则 | 单条规则 `_compare` 返回 False，不影响同 priority 其他规则 |

---

## 6. 测试计划

### 6.1 Matcher 测试（`backend/tests/unit/test_zipcode_matcher.py`）

**机械更新**：既有 18 处 `match_warehouse(...) == "wh"` → `match_warehouses(...) == ["wh"]`，以及相关 `is None` → `== []`。

**新增 4 条 tied 测试**：

1. `test_tied_same_priority_returns_all_winners` — 4 条 priority=10 的 between 规则（B/C/D/E），都含 `451-599`，查询 `500-0001` 返回 `["B","C","D","E"]`（按 rule.id 升序）
2. `test_tied_higher_priority_absorbs_lower` — priority=10 的单命中规则 + priority=20 的两条 tied 规则；查询命中前者的邮编，返回单元素列表，后者不参与
3. `test_tied_deduplicates_same_warehouse` — 两条 priority=10 规则都写 `warehouse_id='wh-A'`，返回 `["wh-A"]`（长度 1）
4. `test_tied_deterministic_order_by_rule_id` — rule.id=3 和 rule.id=1 都 tied 命中，返回顺序为 `[id1, id3]`

### 6.2 Step5 测试（`backend/tests/unit/test_engine_step5.py`）

**既有 3 个测试保持不动**（`test_real_distribution` / `test_unknown_warehouse_excluded_from_denominator` / `test_zero_data_fallback_even_split`）——它们的规则场景都是单命中，新行为等价旧行为。

**新增 3 条 tied 测试**：

1. `test_step5_tied_even_split_across_four_warehouses` — 1 条订单 `qty=8` + 4 条 tied 规则 → `known_counts` 每仓权重 2.0 → `country_qty=100` 时每仓得 25
2. `test_step5_tied_filters_ineligible_warehouse` — tied 4 个仓其中 1 个不在 `country_warehouses` → 按剩 3 个均分
3. `test_step5_tied_all_ineligible_counts_as_unknown` — tied 4 个仓全部不在 `country_warehouses` → 订单 qty 全部归 `unknown_order_qty`

### 6.3 回归验证

```bash
cd backend && pytest tests/unit -q
```

目标：所有测试 PASS，包括匹配器现有 18 + 新增 4、step5 现有 3 + 新增 3、其它无关测试（配置/API 层）154 + 4 + 3 = 161 条左右。

---

## 7. 文档同步

### 7.1 `docs/PROGRESS.md` §3 近期变更

追加 2026-04-11 一条：

> - 2026-04-11 — 邮编规则支持"同优先级 tied 均分"：同 `(country, priority)` 下多条规则同时命中一条订单时，该订单 qty 按 1/N 摊到每个 tied 仓的 `known_counts`，最终 step5 均等分配需求。matcher 接口由 `match_warehouse(...) -> str | None` 改为 `match_warehouses(...) -> list[str]`。业务配置方式：在 UI 上把多条规则的 priority 填相同值即可生效，对任何 operator（`=`/`contains`/`between`…）自动适用。

### 7.2 `docs/Project_Architecture_Blueprint.md`

更新 step5 流水线描述（6 步表的 step5 行 + 详细章节）：

> step5 仓内分配：基于近 30 天的 `order_detail` + `zipcode_rule` 把历史订单归集到仓，已知仓按真实比例分配 `country_qty`，零数据兜底均分到所有已维护海外仓。**2026-04-11 起**：若同优先级多条规则并列命中同一订单，该订单 qty 按 1/N 均分到 tied 仓；eligibility 过滤在均分之前生效。

以及 `zipcode_rule` 表说明下追加一行使用提示：

> **tied 配置**：把多条规则的 `priority` 填相同值即可触发均分；tie 定义基于命中该具体订单的最低 priority 批次，跨 operator 通用。

---

## 8. 风险与回滚

### 风险

1. **既有使用 `match_warehouse` 的外部代码被断**：已核对，全库仅 1 个调用方 (step5)，风险 = 0
2. **`known_counts` 浮点精度**：下游已 `round` 并做最后仓余数兜底，`country_qty` 输出仍精确
3. **测试需要机械更新 18 处**：可能遗漏；缓解——在 Plan 里按文件整体 diff review
4. **tied 配置被误解为"首条优先"导致业务疑惑**：在 PROGRESS 和 Blueprint 中明确书写"填相同 priority 即启用均分"

### 回滚路径

`git revert` 本次全部 commit → 系统回到 first-match-wins 语义。无 DB 变更，回滚零代价。

---

## 9. 不做的事（明确排除）

- ❌ 不引入 round-robin / 哈希分配等"记忆性"策略（每笔订单独立决策，不跨订单 state）
- ❌ 不加"按仓库容量加权"逻辑（业务没提，YAGNI）
- ❌ 不改 UI 表单来"显式配置 tie 组"（当前语义用 priority 相等即足够，加 UI 是过度工程）
- ❌ 不在 matcher 里对格式错误 / 反向段做容错（上一轮已决策）
- ❌ 不处理"优先级完全一样但 warehouse 也完全一样"的配置冗余问题（matcher 去重已兜住，业务自行清理）

---

## 10. 验收标准

1. `pytest tests/unit -q` 全绿
2. Matcher 单测覆盖 4 种 tied 场景
3. Step5 单测覆盖 3 种 tied 场景
4. `git grep match_warehouse` 仅命中文档/spec，无代码残留
5. PROGRESS.md / Blueprint.md 已按 §7 同步
6. commit 链最小且每条 commit 语义独立
