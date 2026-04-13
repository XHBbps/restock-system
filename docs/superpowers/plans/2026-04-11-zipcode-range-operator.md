# 邮编规则 between 区间运算符 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `zipcode_rule` 支持 `between` 运算符，单条规则即可表达一段或多段闭区间（例如 `"000-270"` 或 `"000-270, 500-700"`），减少用户为了表达范围而创建多条规则的负担。

**Architecture:** 在现有 `operator` 枚举上新增 `between`，沿用 `compare_value` 文本列携带分号/逗号分隔的 `lo-hi` 段。后端 `zipcode_matcher` 在数字比较路径上增加 `between` 分支，前端在"比较类型"下拉中新增"区间"项并扩展校验逻辑。匹配优先级和首条命中语义保持不变。

**Tech Stack:** Python 3.12 / SQLAlchemy 2 / Pydantic v2 / Alembic / Vue 3 + Element Plus + TypeScript

---

## File Structure

- Modify: `backend/app/engine/zipcode_matcher.py` — 新增 `between` 分支与段解析
- Modify: `backend/app/models/zipcode_rule.py` — 扩展 `operator`/`compare_value` 列长度与 CHECK 表达式
- Create: `backend/alembic/versions/20260411_1500_zipcode_rule_between_operator.py` — DB 迁移
- Modify: `backend/app/schemas/config.py` — Pydantic `Literal` 与 `between` 专用校验
- Modify: `backend/tests/unit/test_zipcode_matcher.py` — 匹配器单元测试
- Modify: `backend/tests/unit/test_config_schema.py` — Pydantic 校验单元测试
- Modify: `frontend/src/api/config.ts` — TS 类型扩展
- Modify: `frontend/src/views/ZipcodeRuleView.vue` — 运算符选项 / 占位符 / 校验 / 预览
- Modify: `docs/PROGRESS.md` — 第 2 节功能 & 第 3 节近期变更
- Modify: `docs/Project_Architecture_Blueprint.md` — 数据库章节 zipcode_rule 说明

---

## 设计抉择（已定，直接落地）

1. **运算符名称**: `between`（加入 enum）
2. **`compare_value` 语法**：逗号分隔的 `lo-hi` 段，示例：`000-270`、`000-270, 500-700`。内部空白忽略。
3. **值类型限制**: `between` 仅允许 `value_type = 'number'`；`value_type = 'string'` 不能选 `between`。
4. **闭区间**: `lo <= prefix <= hi`，双端包含。
5. **段内约束**: `lo <= hi`，且 `hi <= 10^prefix_length - 1`；否则创建/更新 422。
6. **段数上限**: 最多 20 段（避免恶意长字符串击穿 String(200)）。
7. **列长扩展**: `operator` `String(5) → String(10)`（`between` 7 字符）；`compare_value` `String(50) → String(200)`（容纳多段）。
8. **匹配语义**: 任一段命中即规则命中；沿用现有"按 priority 首条命中返回"的主流程，不改。

---

## Task 1: 扩展 `zipcode_matcher` 支持 `between`

**Files:**
- Modify: `backend/app/engine/zipcode_matcher.py`
- Modify: `backend/tests/unit/test_zipcode_matcher.py`

- [ ] **Step 1: 写失败测试 — 单段区间命中与未命中**

在 `backend/tests/unit/test_zipcode_matcher.py` 末尾追加：

```python
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
```

- [ ] **Step 2: 跑测试确认 fail**

Run: `cd backend && pytest tests/unit/test_zipcode_matcher.py::test_between_single_segment_inclusive -v`
Expected: FAIL（`between` 未在 `_OPERATORS` 中，或者 `_compare` 返回 False 导致全部断言失败）

- [ ] **Step 3: 在 matcher 里加 between 分支**

编辑 `backend/app/engine/zipcode_matcher.py`：

把顶部常量改为：

```python
_OPERATORS = {"=", "!=", ">", ">=", "<", "<=", "contains", "not_contains", "between"}
```

在 `_compare` 函数入口处（`if operator not in _OPERATORS` 之后、`if value_type == "number"` 之前）插入 between 分支：

```python
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
        # ...原有代码保持不变
```

- [ ] **Step 4: 跑测试确认 pass**

Run: `cd backend && pytest tests/unit/test_zipcode_matcher.py::test_between_single_segment_inclusive -v`
Expected: PASS

- [ ] **Step 5: 写多段区间测试**

在同一文件继续追加：

```python
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
```

- [ ] **Step 6: 跑全量 matcher 测试**

Run: `cd backend && pytest tests/unit/test_zipcode_matcher.py -v`
Expected: 全部 PASS（包括新增的 5 个测试和原有用例）

- [ ] **Step 7: commit**

```bash
git add backend/app/engine/zipcode_matcher.py backend/tests/unit/test_zipcode_matcher.py
git commit -m "feat(zipcode): add between operator for range matching"
```

---

## Task 2: 扩展 Pydantic schema `between` 校验

**Files:**
- Modify: `backend/app/schemas/config.py`
- Modify: `backend/tests/unit/test_config_schema.py`

- [ ] **Step 1: 查看现有 test_config_schema.py 结构**

Run: `Grep -n "ZipcodeRuleIn" backend/tests/unit/test_config_schema.py`
（确认 import 方式，以便新增测试风格一致）

- [ ] **Step 2: 写失败测试 — 合法与非法输入**

在 `backend/tests/unit/test_config_schema.py` 末尾追加（若文件尚未 import `ZipcodeRuleIn`，在顶部 import 区补一行）：

```python
from app.schemas.config import ZipcodeRuleIn  # 若已 import 可忽略
import pytest
from pydantic import ValidationError


def _valid_between_body(**overrides):
    base = {
        "country": "JP",
        "prefix_length": 3,
        "value_type": "number",
        "operator": "between",
        "compare_value": "000-270",
        "warehouse_id": "wh-jp",
        "priority": 10,
    }
    base.update(overrides)
    return base


def test_zipcode_rule_in_accepts_single_between_segment() -> None:
    rule = ZipcodeRuleIn(**_valid_between_body())
    assert rule.operator == "between"
    assert rule.compare_value == "000-270"


def test_zipcode_rule_in_accepts_multi_between_segments() -> None:
    rule = ZipcodeRuleIn(**_valid_between_body(compare_value="000-270, 500-700"))
    assert rule.compare_value == "000-270, 500-700"


def test_zipcode_rule_in_rejects_between_with_string_value_type() -> None:
    with pytest.raises(ValidationError, match="between"):
        ZipcodeRuleIn(**_valid_between_body(value_type="string", compare_value="000-270"))


def test_zipcode_rule_in_rejects_between_bad_format() -> None:
    with pytest.raises(ValidationError, match="格式"):
        ZipcodeRuleIn(**_valid_between_body(compare_value="000_270"))


def test_zipcode_rule_in_rejects_between_lo_gt_hi() -> None:
    with pytest.raises(ValidationError, match="下界"):
        ZipcodeRuleIn(**_valid_between_body(compare_value="300-270"))


def test_zipcode_rule_in_rejects_between_hi_exceeds_prefix_length() -> None:
    # prefix_length=3 → 最大值 999
    with pytest.raises(ValidationError, match="超出"):
        ZipcodeRuleIn(**_valid_between_body(compare_value="000-1000"))


def test_zipcode_rule_in_rejects_between_too_many_segments() -> None:
    segments = ",".join(f"{i}00-{i}50" for i in range(21))  # 21 段
    with pytest.raises(ValidationError, match="段数"):
        ZipcodeRuleIn(**_valid_between_body(compare_value=segments))
```

- [ ] **Step 3: 跑测试确认 fail**

Run: `cd backend && pytest tests/unit/test_config_schema.py -k "between" -v`
Expected: 多数 FAIL（因为 schema 尚不支持 `between`，第一个测试会因 `Literal` 不包含 `between` 失败）

- [ ] **Step 4: 修改 `backend/app/schemas/config.py`**

找到 `ZipcodeRuleIn` 类并改成：

```python
# ==================== Zipcode Rule ====================
_BETWEEN_MAX_SEGMENTS = 20


def _parse_between_segments(raw: str) -> list[tuple[int, int]]:
    """解析 between compare_value '000-270, 500-700' -> [(0,270),(500,700)]。

    仅做纯语法/数值校验,不做 prefix_length 越界检查(由调用方负责)。
    遇到错误抛 ValueError。
    """
    segments: list[tuple[int, int]] = []
    for chunk in raw.split(","):
        piece = chunk.strip()
        if not piece:
            continue
        parts = piece.split("-", 1)
        if len(parts) != 2:
            raise ValueError(f"between 段 '{piece}' 格式错误,需为 数字-数字")
        lo_raw, hi_raw = parts[0].strip(), parts[1].strip()
        if not lo_raw.isdigit() or not hi_raw.isdigit():
            raise ValueError(f"between 段 '{piece}' 格式错误,需为 数字-数字")
        lo, hi = int(lo_raw), int(hi_raw)
        if lo > hi:
            raise ValueError(f"between 区间下界不能大于上界: {piece}")
        segments.append((lo, hi))
    return segments


class ZipcodeRuleIn(BaseModel):
    country: str = Field(..., min_length=2, max_length=2)
    prefix_length: int = Field(..., ge=1, le=10)
    value_type: Literal["number", "string"]
    operator: Literal[
        "=", "!=", ">", ">=", "<", "<=", "contains", "not_contains", "between"
    ]
    compare_value: str = Field(..., min_length=1, max_length=200)
    warehouse_id: str
    priority: int = Field(default=100, ge=1)

    @field_validator("compare_value")
    @classmethod
    def validate_compare_value(cls, value: str, info: ValidationInfo) -> str:
        compare_value = value.strip()
        if not compare_value:
            raise ValueError("compare_value 不能为空")

        operator = info.data.get("operator")
        value_type = info.data.get("value_type")
        prefix_length = info.data.get("prefix_length")

        if operator == "between":
            if value_type != "number":
                raise ValueError("between 运算符仅支持 number 值类型")
            try:
                segments = _parse_between_segments(compare_value)
            except ValueError as exc:
                raise ValueError(str(exc)) from exc
            if not segments:
                raise ValueError("between 至少需要一个有效区间段")
            if len(segments) > _BETWEEN_MAX_SEGMENTS:
                raise ValueError(
                    f"between 段数不能超过 {_BETWEEN_MAX_SEGMENTS},当前 {len(segments)}"
                )
            if prefix_length is not None:
                max_value = 10**prefix_length - 1
                for lo, hi in segments:
                    if hi > max_value:
                        raise ValueError(
                            f"between 上界 {hi} 超出前 {prefix_length} 位最大值 {max_value}"
                        )
            return compare_value

        if value_type == "number":
            try:
                float(compare_value)
            except (TypeError, ValueError) as exc:
                raise ValueError("数字类型的 compare_value 必须是有效数字") from exc
        if value_type == "string" and operator in {"contains", "not_contains"}:
            tokens = [item.strip() for item in compare_value.split(",") if item.strip()]
            if not tokens:
                raise ValueError("包含/不包含规则至少需要一个有效比较值")
        return compare_value

    @model_validator(mode="after")
    def validate_operator_by_value_type(self) -> "ZipcodeRuleIn":
        string_operators = {"=", "!=", "contains", "not_contains"}
        number_operators = {"=", "!=", ">", ">=", "<", "<=", "between"}

        if self.value_type == "string" and self.operator not in string_operators:
            raise ValueError("字符串类型仅支持 等于/不等于/包含/不包含")
        if self.value_type == "number" and self.operator not in number_operators:
            raise ValueError("数字类型仅支持 等于/不等于/大于/大于等于/小于/小于等于/区间")
        return self
```

- [ ] **Step 5: 跑测试确认 pass**

Run: `cd backend && pytest tests/unit/test_config_schema.py -k "between" -v`
Expected: 7 个新测试全部 PASS

- [ ] **Step 6: 跑全量后端测试（避免回归）**

Run: `cd backend && pytest tests/unit -q`
Expected: 所有测试 PASS（包括 `test_zipcode_matcher.py` 和 `test_zipcode_rule_api.py`）

- [ ] **Step 7: commit**

```bash
git add backend/app/schemas/config.py backend/tests/unit/test_config_schema.py
git commit -m "feat(zipcode): validate between operator in pydantic schema"
```

---

## Task 3: DB 迁移 + ORM 模型同步

**Files:**
- Create: `backend/alembic/versions/20260411_1500_zipcode_rule_between_operator.py`
- Modify: `backend/app/models/zipcode_rule.py`

- [ ] **Step 1: 创建迁移文件**

创建 `backend/alembic/versions/20260411_1500_zipcode_rule_between_operator.py`，内容：

```python
"""zipcode_rule add between operator and widen columns

Revision ID: 20260411_1500
Revises: 20260411_1000
Create Date: 2026-04-11 15:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260411_1500"
down_revision: str | Sequence[str] | None = "20260411_1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. 扩展列长度:operator 存得下 'between',compare_value 存得下多段区间
    op.alter_column(
        "zipcode_rule",
        "operator",
        existing_type=sa.String(length=5),
        type_=sa.String(length=10),
        existing_nullable=False,
    )
    op.alter_column(
        "zipcode_rule",
        "compare_value",
        existing_type=sa.String(length=50),
        type_=sa.String(length=200),
        existing_nullable=False,
    )
    # 2. 替换 CHECK 约束,加入 'between'
    op.drop_constraint("operator_enum", "zipcode_rule", type_="check")
    op.create_check_constraint(
        "operator_enum",
        "zipcode_rule",
        "operator IN ('=','!=','>','>=','<','<=','contains','not_contains','between')",
    )


def downgrade() -> None:
    # 注意:若存在 operator='between' 的行,downgrade 前必须手动清理,否则 CHECK 约束会失败
    op.drop_constraint("operator_enum", "zipcode_rule", type_="check")
    op.create_check_constraint(
        "operator_enum",
        "zipcode_rule",
        "operator IN ('=','!=','>','>=','<','<=','contains','not_contains')",
    )
    op.alter_column(
        "zipcode_rule",
        "compare_value",
        existing_type=sa.String(length=200),
        type_=sa.String(length=50),
        existing_nullable=False,
    )
    op.alter_column(
        "zipcode_rule",
        "operator",
        existing_type=sa.String(length=10),
        type_=sa.String(length=5),
        existing_nullable=False,
    )
```

- [ ] **Step 2: 同步 ORM 模型**

编辑 `backend/app/models/zipcode_rule.py`，替换 `__table_args__` 里的 `operator_enum` 行以及 `operator` / `compare_value` 列声明：

```python
class ZipcodeRule(Base):
    """按 priority 升序匹配:首条命中即返回;全部未命中归"未知仓"。"""

    __tablename__ = "zipcode_rule"
    __table_args__ = (
        CheckConstraint("value_type IN ('number','string')", name="value_type_enum"),
        CheckConstraint(
            "operator IN ('=','!=','>','>=','<','<=','contains','not_contains','between')",
            name="operator_enum",
        ),
        CheckConstraint("prefix_length BETWEEN 1 AND 10", name="prefix_length_range"),
        Index("ix_zipcode_rule_country_priority", "country", "priority"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    prefix_length: Mapped[int] = mapped_column(Integer, nullable=False)
    value_type: Mapped[str] = mapped_column(String(10), nullable=False)
    operator: Mapped[str] = mapped_column(String(10), nullable=False)
    compare_value: Mapped[str] = mapped_column(String(200), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("warehouse.id"), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
```

（`String(10)` / `String(200)` 与迁移一致；其余字段与原文件保持完全相同，禁止顺带修改无关字段。）

- [ ] **Step 3: 验证迁移脚本可解析（离线语法检查）**

Run: `cd backend && python -m py_compile alembic/versions/20260411_1500_zipcode_rule_between_operator.py`
Expected: 无输出（语法正确）

- [ ] **Step 4: 对空 SQLite 做 upgrade/downgrade dry-run（可选但推荐）**

> 如果本地有 `alembic.ini` 指向 dev DB，执行：

```bash
cd backend
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

Expected: 三条命令均无错误退出；若本地无 DB 连接则跳过此 step，交由 CI 覆盖。

- [ ] **Step 5: 跑后端单测确认 ORM 未破**

Run: `cd backend && pytest tests/unit -q`
Expected: 全部 PASS

- [ ] **Step 6: commit**

```bash
git add backend/alembic/versions/20260411_1500_zipcode_rule_between_operator.py backend/app/models/zipcode_rule.py
git commit -m "feat(db): widen zipcode_rule columns and allow between operator"
```

---

## Task 4: API 层 rule 创建/更新的集成测试

**Files:**
- Modify: `backend/tests/unit/test_zipcode_rule_api.py`

- [ ] **Step 1: 写失败测试 — create 接口接受 between**

在 `backend/tests/unit/test_zipcode_rule_api.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_create_zipcode_rule_accepts_between_operator() -> None:
    db = _FakeDb([SimpleNamespace(id="wh-jp", country="JP")])

    body = ZipcodeRuleIn(
        country="JP",
        prefix_length=3,
        value_type="number",
        operator="between",
        compare_value="000-270, 500-700",
        warehouse_id="wh-jp",
        priority=15,
    )

    result = await create_zipcode_rule(body, db=db, _={})  # type: ignore[arg-type]

    assert db.added, "规则应被写入"
    assert db.added[0].operator == "between"
    assert db.added[0].compare_value == "000-270, 500-700"
    assert result.operator == "between"
```

- [ ] **Step 2: 跑测试**

Run: `cd backend && pytest tests/unit/test_zipcode_rule_api.py::test_create_zipcode_rule_accepts_between_operator -v`
Expected: PASS（无需修改 `app/api/config.py`，因为接口直接接收 `ZipcodeRuleIn`，Task 2 的 schema 修改已覆盖）

> 若此测试意外 FAIL，排查 `app/api/config.py` 中 `create_zipcode_rule` 是否对 `operator` 做了额外枚举校验；若是，扩展该白名单即可，不要改变其他逻辑。

- [ ] **Step 3: commit**

```bash
git add backend/tests/unit/test_zipcode_rule_api.py
git commit -m "test(zipcode): cover api creating rule with between operator"
```

---

## Task 5: 前端类型与 UI

**Files:**
- Modify: `frontend/src/api/config.ts`
- Modify: `frontend/src/views/ZipcodeRuleView.vue`

- [ ] **Step 1: 扩展 TS 类型**

编辑 `frontend/src/api/config.ts`，找到 `ZipcodeRule` 接口的 `operator` 行，替换为：

```typescript
export interface ZipcodeRule {
  id: number
  country: string
  prefix_length: number
  value_type: 'number' | 'string'
  operator:
    | '='
    | '!='
    | '>'
    | '>='
    | '<'
    | '<='
    | 'contains'
    | 'not_contains'
    | 'between'
  compare_value: string
  warehouse_id: string
  priority: number
}
```

- [ ] **Step 2: 在 `ZipcodeRuleView.vue` 的常量区加入 between**

编辑 `frontend/src/views/ZipcodeRuleView.vue`，在 `NUMBER_OPERATORS` 列表末尾追加 `between`：

```typescript
const NUMBER_OPERATORS = [
  { value: '=', label: '等于' },
  { value: '>=', label: '大于等于' },
  { value: '>', label: '大于' },
  { value: '!=', label: '不等于' },
  { value: '<', label: '小于' },
  { value: '<=', label: '小于等于' },
  { value: 'between', label: '区间' },
] as const
```

（`STRING_OPERATORS` 不变。）

- [ ] **Step 3: 新增区间相关 computed 与正则**

在 `ZipcodeRuleView.vue` 的 `<script setup>` 内，紧邻 `needsCommaSeparatedValues` 声明处新增：

```typescript
const BETWEEN_SEGMENT_RE = /^\d+-\d+$/
const MAX_BETWEEN_SEGMENTS = 20

const isBetweenOperator = computed(() => form.operator === 'between')
```

- [ ] **Step 4: 修改占位符 computed**

在现有 `compareValuePlaceholder` 上增加 `between` 分支（保留其它分支原样）：

```typescript
const compareValuePlaceholder = computed(() => {
  if (isBetweenOperator.value) return '例如 000-270，或多段 000-270, 500-700'
  if (form.value_type === 'number') return '请输入数字，例如 100'
  if (needsCommaSeparatedValues.value) return '请输入多个文本，使用英文逗号分隔，例如 SW, EC'
  return '请输入文本，例如 SW'
})
```

- [ ] **Step 5: 扩展 compareValue 校验提示**

替换现有 `compareValueValidationMessage` 为：

```typescript
const compareValueValidationMessage = computed(() => {
  if (!compareValueTouched.value && !submitAttempted.value) return ''

  const value = form.compare_value.trim()
  if (!value) return '请输入比较值'

  if (isBetweenOperator.value) {
    const segments = value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
    if (segments.length === 0) return '至少需要一段区间'
    if (segments.length > MAX_BETWEEN_SEGMENTS) {
      return `区间段数不能超过 ${MAX_BETWEEN_SEGMENTS}`
    }
    const maxValue = 10 ** form.prefix_length - 1
    for (const seg of segments) {
      if (!BETWEEN_SEGMENT_RE.test(seg)) {
        return `区间格式错误：${seg}（应为 数字-数字）`
      }
      const [loStr, hiStr] = seg.split('-')
      const lo = Number(loStr)
      const hi = Number(hiStr)
      if (lo > hi) return `区间下界不能大于上界：${seg}`
      if (hi > maxValue) {
        return `上界 ${hi} 超出前 ${form.prefix_length} 位最大值 ${maxValue}`
      }
    }
    return ''
  }

  if (form.value_type === 'number' && Number.isNaN(Number(value))) {
    return '数字类型请输入有效数字'
  }

  if (needsCommaSeparatedValues.value) {
    const tokens = value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
    if (tokens.length === 0) return '请至少输入一个有效比较值'
  }

  return ''
})
```

- [ ] **Step 6: 扩展 `normalizeCompareValue` 对 between 的段归一化**

替换现有 `normalizeCompareValue` 为：

```typescript
function normalizeCompareValue(value: string): string {
  const trimmed = value.trim()
  if (!trimmed) return ''

  if (isBetweenOperator.value) {
    return trimmed
      .replace(/[，、]/g, ',')
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean)
      .join(', ')
  }

  if (!needsCommaSeparatedValues.value) return trimmed

  return trimmed
    .replace(/[，、]/g, ',')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .join(', ')
}
```

- [ ] **Step 7: 扩展 `ruleConditionText` 对 between 的展示**

替换现有 `ruleConditionText` 为：

```typescript
function ruleConditionText(
  rule: Pick<ZipcodeRule, 'value_type' | 'operator' | 'compare_value'>,
): string {
  const valueText = rule.compare_value
  if (rule.operator === 'between') {
    return `按数字区间 ${valueText}`
  }
  if (rule.operator === 'contains') {
    return `按${valueTypeLabel(rule.value_type)}包含任一 ${valueText}`
  }
  if (rule.operator === 'not_contains') {
    return `按${valueTypeLabel(rule.value_type)}不包含任一 ${valueText}`
  }
  return `按${valueTypeLabel(rule.value_type)}${operatorLabel(rule.operator)} ${valueText}`
}
```

- [ ] **Step 8: 扩展 `normalizeFormForCurrentType` — between 数字类型下跳过单数字校验**

替换现有 `normalizeFormForCurrentType` 为：

```typescript
function normalizeFormForCurrentType(options?: { notify?: boolean }): void {
  syncOperatorByValueType(form.value_type)

  if (form.value_type === 'number') {
    // between 由自己的校验流程处理,不在此处要求单个数字
    if (form.operator !== 'between') {
      const trimmed = form.compare_value.trim()
      if (trimmed && Number.isNaN(Number(trimmed))) {
        form.compare_value = ''
        if (options?.notify) {
          ElMessage.warning('已切换为数字类型，原比较值不符合数字格式，已自动清空。')
        }
        return
      }
    }
  }

  form.compare_value = normalizeCompareValue(form.compare_value)
}
```

- [ ] **Step 9: 前端类型编译与打包检查**

Run:
```bash
cd frontend && npm run build
```

Expected: `vue-tsc --noEmit` + `vite build` 均成功，无新类型错误。如果 `type-check` 是独立脚本，改为 `npm run type-check && npm run build`（按项目实际脚本名）。

- [ ] **Step 10: commit**

```bash
git add frontend/src/api/config.ts frontend/src/views/ZipcodeRuleView.vue
git commit -m "feat(web): add between operator to zipcode rule form"
```

---

## Task 6: 文档同步

**Files:**
- Modify: `docs/PROGRESS.md`
- Modify: `docs/Project_Architecture_Blueprint.md`

- [ ] **Step 1: 查找 PROGRESS.md 的最近更新日期位置**

Run: `Grep -n "最近更新\|邮编" docs/PROGRESS.md`
（记下"最近更新"与"邮编规则"相关行号）

- [ ] **Step 2: 更新 `docs/PROGRESS.md` 第 3 节近期变更**

在第 3 节（近期变更）顶部追加一条，日期 2026-04-11：

```markdown
- 2026-04-11 — 邮编规则新增 `between` 区间运算符：`compare_value` 支持 `"000-270"` 或多段 `"000-270, 500-700"`，一条规则即可表达范围；仅 `value_type=number` 允许。对应迁移 `20260411_1500`，列宽 `operator → String(10)`、`compare_value → String(200)`。
```

同时把第 2 节"已交付能力"中邮编规则条目（若存在）补充 `between` 说明；若该章节没有单列条目则跳过。

最后，把文件顶部的"最近更新"日期字段同步为 `2026-04-11`。

- [ ] **Step 3: 更新 `docs/Project_Architecture_Blueprint.md` 数据库章节**

Run: `Grep -n "zipcode_rule" docs/Project_Architecture_Blueprint.md`

在 `zipcode_rule` 表字段说明处：
1. 把 `operator` 枚举值列表追加 `between`
2. 把 `operator` 长度注明为 `String(10)`
3. 把 `compare_value` 长度注明为 `String(200)` 并补一行说明：`between` 使用 `"lo-hi"` 段，多段用逗号分隔。

- [ ] **Step 4: 关闭清单自检**

逐项确认（AGENTS.md 第 9.2 节）：
- [x] 触发 9.1：数据库 migration（新增字段 CHECK 与列宽变更）→ PROGRESS.md 第 3 节 + Architecture blueprint 数据库章节 ✅
- [x] 触发 9.1：无新增 API 端点（schema 微调不算）、无新增前端 view、无新增 env var、无新 job
- [x] PROGRESS.md "最近更新"日期已改为 2026-04-11

- [ ] **Step 5: commit**

```bash
git add docs/PROGRESS.md docs/Project_Architecture_Blueprint.md
git commit -m "docs(zipcode): note between operator and column widening"
```

---

## Task 7: 端到端烟测（手动 / 半自动）

**Files:** — 无改动，纯验证

- [ ] **Step 1: 跑后端全量单测**

Run: `cd backend && pytest tests/unit -q`
Expected: 全绿。

- [ ] **Step 2: 跑前端构建**

Run: `cd frontend && npm run build`
Expected: 构建成功。

- [ ] **Step 3: （可选）启动本地栈做一次人工用例验证**

操作步骤：
1. `docker compose up -d backend db frontend`（或项目既有的启动命令）
2. `alembic upgrade head`（应用 20260411_1500）
3. 打开 `/config/zipcode-rules`
4. 新增规则：国家 JP、截取前 3 位、数字、比较类型选"区间"、比较值 `000-270, 500-700`、选仓库、保存
5. 确认列表展示"按数字区间 000-270, 500-700"
6. 编辑规则、改成 `300-269` 期望前端阻止保存并提示"下界不能大于上界"
7. 改成 `000-1500` 期望提示"上界超出前 3 位最大值 999"

Expected: 全部符合预期；任何一条不符合记录并回到对应 Task 修复。

- [ ] **Step 4: 若一切正常，建议直接基于已有 commits 发起 PR**

```bash
git log --oneline -8
```

确认本次工作含 6 条 commit（Task 1~6，Task 7 无代码）。PR title 建议：`feat(zipcode): support between range operator`。

---

## 验收标准

1. `cd backend && pytest tests/unit -q` 全绿
2. `cd frontend && npm run build` 全绿
3. 可通过 UI 创建 / 编辑 / 删除 `operator=between` 的规则
4. matcher 对 `between` 规则在单段与多段情况下命中正确
5. 非法 `compare_value`（格式、lo>hi、越界、段数）在 create/update 时返回 422 并被前端提前拦截
6. DB migration `20260411_1500` 可 `upgrade` 与 `downgrade`（downgrade 前提需手工清理 `between` 行）
7. `docs/PROGRESS.md` 与 `Project_Architecture_Blueprint.md` 已同步

---

## 风险与回滚

- **风险 1：downgrade 遇到遗留 `between` 行**
  - 缓解：downgrade 前用 `DELETE FROM zipcode_rule WHERE operator='between'` 清理，或先批量改成具体 `>=` / `<=` 规则
- **风险 2：前端校验与后端校验漂移**
  - 缓解：前端校验（Step 5）与后端 `_parse_between_segments` 的规则完全对齐（同样的 `\d+-\d+` + lo≤hi + hi≤10^prefix-1 + 段数≤20）
- **风险 3：现有规则数据损坏**
  - 缓解：迁移只放宽列宽、放宽 CHECK 约束，不触碰数据；existing 行保持不变
- **回滚路径：** `git revert` 本次 6 个 commit → `alembic downgrade 20260411_1000`（前提：生产无 `between` 规则）
