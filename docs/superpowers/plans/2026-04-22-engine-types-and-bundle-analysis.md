# Engine Types + Bundle Visualizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 关闭 2026-04-21 audit 的最后两项已跳过条目 — P2-A4（引擎内层 `{available, reserved, in_transit, total}` 等命名 dict 字符串 key 典型"拼错就静默走错"的陷阱替换为 frozen dataclass）和 P2-D3（一次性运行 bundle visualizer 定位 `element-plus` 906KB / `charts` 557KB 是否含 tree-shake 漏项，只产出调研 doc，不加 package.json 依赖）。

**Architecture:**
- **P2-A4**: 引入两个 frozen dataclass（`InventoryStock` / `LocalStock`）替换引擎内 2 种最易拼错的命名 dict；顺手把 `step4_total` 返回值从 `dict[str, dict[str, int]]` 的单键 `{"purchase_qty": int}` 折叠为 `dict[str, int]`；所有改动纯粹在 `app/engine/` 模块内，不触 DB JSONB schema（`country_breakdown` / `warehouse_breakdown` 仍是 dict，因需 JSONB round-trip）；保留外层 `dict[sku][country]` 结构（它们是纯 2-d lookup，改 dataclass 无收益）。
- **P2-D3**: 本地临时 `npx rollup-plugin-visualizer` 跑一次 `vite build --mode production --plugin-visualizer`，HTML 产物看完即删，findings 写成 `docs/superpowers/reviews/2026-04-22-bundle-visualizer-findings.md`。如发现 element-plus / echarts 有可 tree-shake 的大块，单独开 follow-up plan；如无，本 PR 就只留 findings 文档。

**Tech Stack:** Python 3.11 + SQLAlchemy 2.0（engine 模块）+ pytest（TDD/回归验证）+ mypy strict（类型验证）；Vite + rollup-plugin-visualizer（一次性 dev 工具，不入 deps）。

**Pre-flight:**
- 从 master 新开分支：`git checkout -b refactor/engine-types-and-bundle-viz`
- dev 容器 healthy：`docker compose -f deploy/docker-compose.dev.yml -f deploy/docker-compose.dev.override.yml --env-file deploy/.env.dev ps`
- pytest baseline：`docker exec` 跑 `tests/unit/test_engine_*.py` 应 passed

---

## 文件结构全景

**Phase 1（P2-A4 engine types）：**

- Modify: `backend/app/engine/context.py` — 加 `InventoryStock` / `LocalStock` frozen dataclass + type aliases
- Modify: `backend/app/engine/step2_sale_days.py` — `merge_inventory` / `compute_sale_days` / `run_step2` 签名改用新类型
- Modify: `backend/app/engine/step4_total.py` — `load_local_inventory` 返回 `dict[str, LocalStock]`；`compute_total` 接 `LocalStock | None`；`step4_total` 返回 `dict[str, int]`
- Modify: `backend/app/engine/runner.py` — step4 / step2 调用点更新
- Modify: `backend/app/api/metrics.py` — `build_dashboard_payload` 调 `compute_total` 签名更新
- Modify: `backend/tests/unit/test_engine_step2.py` — 构造 inventory dict 的地方改 `InventoryStock`
- Modify: `backend/tests/unit/test_engine_step4.py` — 构造 local_stock 的地方改 `LocalStock`
- Modify: `backend/tests/integration/test_engine_e2e.py` — 如有直接构造 engine dict fixture
- New: `backend/tests/unit/test_engine_types.py` — 新 dataclass 的 roundtrip / 等值 / 不变性单测

**Phase 2（P2-D3 bundle analysis，本地临时操作）：**

- Temp modify（不 commit）: `frontend/vite.config.ts`
- Temp devDep（不 commit）: `rollup-plugin-visualizer` via `npx --yes`
- New: `docs/superpowers/reviews/2026-04-22-bundle-visualizer-findings.md`
- Restore: `frontend/vite.config.ts` 回到原状

---

## Phase 1 — P2-A4 Engine Types Refactor

### Task 1: 引入 `InventoryStock` frozen dataclass

**Files:**
- Modify: `backend/app/engine/context.py`
- Test: `backend/tests/unit/test_engine_types.py`

- [ ] **Step 1: 写 InventoryStock 失败测试**

Create `backend/tests/unit/test_engine_types.py`:

```python
"""Engine 类型系统单测：frozen dataclass 不变性 + 构造 + total 计算。"""

from __future__ import annotations

import dataclasses

import pytest


def test_inventory_stock_roundtrip() -> None:
    from app.engine.context import InventoryStock

    stock = InventoryStock(available=10, reserved=3, in_transit=7)
    assert stock.available == 10
    assert stock.reserved == 3
    assert stock.in_transit == 7
    assert stock.total == 20  # 10 + 3 + 7


def test_inventory_stock_is_frozen() -> None:
    from app.engine.context import InventoryStock

    stock = InventoryStock(available=1, reserved=0, in_transit=0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        stock.available = 99  # type: ignore[misc]


def test_inventory_stock_equality() -> None:
    from app.engine.context import InventoryStock

    a = InventoryStock(available=5, reserved=2, in_transit=0)
    b = InventoryStock(available=5, reserved=2, in_transit=0)
    c = InventoryStock(available=5, reserved=2, in_transit=1)
    assert a == b
    assert a != c
```

- [ ] **Step 2: 运行测试确认失败（ImportError: cannot import name 'InventoryStock'）**

Run:
```
MSYS_NO_PATHCONV=1 docker cp "$(cd backend/tests && pwd -W)/unit/test_engine_types.py" restock-dev-backend:/tmp/tests/unit/test_engine_types.py
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest tests/unit/test_engine_types.py -v --no-header 2>&1"
```

Expected: `ImportError: cannot import name 'InventoryStock' from 'app.engine.context'`

- [ ] **Step 3: 实现 InventoryStock**

In `backend/app/engine/context.py`, replace full file:

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class InventoryStock:
    """单 SKU × 国家的海外仓库存快照。

    替换原引擎 step2 中的 ``dict[str, int]`` with keys
    ``{"available","reserved","in_transit","total"}`` — 字符串 key 拼错
    曾多次触发静默 bug。frozen + slots 保证不可变 + 内存紧凑。

    total 是 available + reserved + in_transit 的派生属性，不单独存储。
    """

    available: int
    reserved: int
    in_transit: int

    @property
    def total(self) -> int:
        return self.available + self.reserved + self.in_transit


@dataclass
class EngineContext:
    country_qty: dict[str, dict[str, int]] = field(default_factory=dict)
    velocity: dict[str, dict[str, float]] = field(default_factory=dict)
    local_stock: dict[str, dict[str, int]] = field(default_factory=dict)
    buffer_days: int = 30
    safety_stock_days: int = 15
```

- [ ] **Step 4: 运行测试确认通过**

```
MSYS_NO_PATHCONV=1 docker cp "$(cd backend/app && pwd -W)/engine/context.py" restock-dev-backend:/app/app/engine/context.py
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest tests/unit/test_engine_types.py -v --no-header 2>&1"
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/context.py backend/tests/unit/test_engine_types.py
git commit -m "feat(engine): 引入 InventoryStock frozen dataclass

替换 step2 的 {available, reserved, in_transit, total} 命名 dict（字符串 key
拼错的静默 bug 风险）。frozen=True + slots=True 保证不可变 + 内存紧凑；
total 改为 property 派生不单独存储，消除一致性负担。

本 commit 只引入类型，后续 commit 把 step2 / step4 / runner 迁移过去。

Progress P2-A4 from docs/superpowers/reviews/2026-04-21-full-audit.md"
```

---

### Task 2: 引入 `LocalStock` frozen dataclass

**Files:**
- Modify: `backend/app/engine/context.py`
- Test: `backend/tests/unit/test_engine_types.py`

- [ ] **Step 1: 写 LocalStock 失败测试**

Append to `backend/tests/unit/test_engine_types.py`:

```python
def test_local_stock_roundtrip() -> None:
    from app.engine.context import LocalStock

    stock = LocalStock(available=100, reserved=20)
    assert stock.available == 100
    assert stock.reserved == 20
    assert stock.total == 120


def test_local_stock_is_frozen() -> None:
    from app.engine.context import LocalStock

    stock = LocalStock(available=1, reserved=0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        stock.reserved = 9  # type: ignore[misc]


def test_local_stock_equality() -> None:
    from app.engine.context import LocalStock

    assert LocalStock(available=5, reserved=2) == LocalStock(available=5, reserved=2)
    assert LocalStock(available=5, reserved=2) != LocalStock(available=5, reserved=3)
```

- [ ] **Step 2: 运行测试确认失败**

```
MSYS_NO_PATHCONV=1 docker cp "$(cd backend/tests && pwd -W)/unit/test_engine_types.py" restock-dev-backend:/tmp/tests/unit/test_engine_types.py
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest tests/unit/test_engine_types.py::test_local_stock_roundtrip -v --no-header 2>&1"
```

Expected: `ImportError: cannot import name 'LocalStock'`

- [ ] **Step 3: 实现 LocalStock（在 InventoryStock 下方）**

Edit `backend/app/engine/context.py` — 在 `InventoryStock` 之后 `EngineContext` 之前插入：

```python
@dataclass(frozen=True, slots=True)
class LocalStock:
    """本地主仓（type=1）库存快照。

    替换原 step4 ``load_local_inventory`` 的 ``dict[str, int]`` with keys
    ``{"available","reserved"}``。本地仓不含 in_transit（in_transit 属于
    出口在途，在 step2 的 InventoryStock 里表示）。
    """

    available: int
    reserved: int

    @property
    def total(self) -> int:
        return self.available + self.reserved
```

- [ ] **Step 4: 运行测试确认通过**

```
MSYS_NO_PATHCONV=1 docker cp "$(cd backend/app && pwd -W)/engine/context.py" restock-dev-backend:/app/app/engine/context.py
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest tests/unit/test_engine_types.py -v --no-header 2>&1"
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/context.py backend/tests/unit/test_engine_types.py
git commit -m "feat(engine): 引入 LocalStock frozen dataclass

step4 本地主仓库存（type=1 仓）只有 available/reserved 两字段，无 in_transit。
与 step2 的 InventoryStock 分开命名防止混用。

Progress P2-A4 from docs/superpowers/reviews/2026-04-21-full-audit.md"
```

---

### Task 3: step2 迁移 `merge_inventory` / `compute_sale_days` / `run_step2` 用 `InventoryStock`

**Files:**
- Modify: `backend/app/engine/step2_sale_days.py`
- Test: `backend/tests/unit/test_engine_step2.py`（如存在）
- Test: `backend/tests/unit/test_engine_types.py`（加 migrations 回归测）

- [ ] **Step 1: 查找现有 step2 测试**

Run:
```
grep -rn "merge_inventory\|compute_sale_days\|run_step2" backend/tests/
```

Expected: 列出涉及 step2 的 test 文件。记下每个位置的测试 fixture 结构。

- [ ] **Step 2: 写迁移后行为不变的回归测试**

Append to `backend/tests/unit/test_engine_types.py`:

```python
def test_merge_inventory_returns_inventory_stock() -> None:
    from app.engine.context import InventoryStock
    from app.engine.step2_sale_days import merge_inventory

    oversea = {
        ("SKU-A", "US"): {"available": 10, "reserved": 3},
        ("SKU-B", "GB"): {"available": 5, "reserved": 0},
    }
    in_transit = {
        ("SKU-A", "US"): 7,
        ("SKU-C", "DE"): 20,
    }

    result = merge_inventory(oversea, in_transit)

    assert result["SKU-A"]["US"] == InventoryStock(available=10, reserved=3, in_transit=7)
    assert result["SKU-B"]["GB"] == InventoryStock(available=5, reserved=0, in_transit=0)
    assert result["SKU-C"]["DE"] == InventoryStock(available=0, reserved=0, in_transit=20)


def test_compute_sale_days_reads_inventory_stock_total() -> None:
    from app.engine.context import InventoryStock
    from app.engine.step2_sale_days import compute_sale_days

    velocity = {"SKU-A": {"US": 2.0}}  # 2 件/天
    inventory = {"SKU-A": {"US": InventoryStock(available=10, reserved=5, in_transit=5)}}  # total=20

    result = compute_sale_days(velocity, inventory)

    assert result["SKU-A"]["US"] == pytest.approx(10.0)  # 20 / 2
```

- [ ] **Step 3: 运行测试确认失败**

```
MSYS_NO_PATHCONV=1 docker cp "$(cd backend/tests && pwd -W)/unit/test_engine_types.py" restock-dev-backend:/tmp/tests/unit/test_engine_types.py
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest tests/unit/test_engine_types.py -v --no-header 2>&1"
```

Expected: 2 failed（`merge_inventory` 返回老 dict 形态；`InventoryStock.__eq__` 不匹配）

- [ ] **Step 4: 迁移 `merge_inventory`**

Edit `backend/app/engine/step2_sale_days.py` — 把 `merge_inventory` 函数替换为：

```python
def merge_inventory(
    oversea: dict[tuple[str, str], dict[str, int]],
    in_transit: dict[tuple[str, str], int],
) -> dict[str, dict[str, InventoryStock]]:
    """Merge overseas stock and in-transit stock into one structure.

    Returns: ``{sku: {country: InventoryStock}}``
    """
    merged: defaultdict[str, dict[str, InventoryStock]] = defaultdict(dict)
    keys = set(oversea.keys()) | set(in_transit.keys())
    for sku, country in keys:
        inv = oversea.get((sku, country), {"available": 0, "reserved": 0})
        transit = in_transit.get((sku, country), 0)
        merged[sku][country] = InventoryStock(
            available=int(inv["available"]),
            reserved=int(inv["reserved"]),
            in_transit=int(transit),
        )
    return dict(merged)
```

- [ ] **Step 5: 迁移 `compute_sale_days`**

Edit same file — 替换 `compute_sale_days` 函数：

```python
def compute_sale_days(
    velocity: dict[str, dict[str, float]],
    inventory: dict[str, dict[str, InventoryStock]],
) -> dict[str, dict[str, float]]:
    """Compute ``sale_days`` for each ``(sku, country)`` with positive velocity."""
    result: defaultdict[str, dict[str, float]] = defaultdict(dict)
    for sku, country_map in velocity.items():
        for country, v in country_map.items():
            if v <= 0:
                continue
            stock = inventory.get(sku, {}).get(country)
            result[sku][country] = (stock.total if stock is not None else 0) / v
    return dict(result)
```

- [ ] **Step 6: 迁移 `run_step2` 返回类型**

Edit same file — 更新 `run_step2` 签名：

```python
async def run_step2(
    db: AsyncSession,
    velocity: dict[str, dict[str, float]],
    commodity_skus: list[str] | None,
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, InventoryStock]]]:
    oversea = await load_oversea_inventory(db, commodity_skus)
    in_transit = await load_in_transit(db, commodity_skus)
    inventory = merge_inventory(oversea, in_transit)
    sale_days = compute_sale_days(velocity, inventory)
    return sale_days, inventory
```

- [ ] **Step 7: 加 import**

Edit top of `backend/app/engine/step2_sale_days.py`:

```python
from app.engine.context import InventoryStock
```

- [ ] **Step 8: 运行 step2 + 新回归测试确认通过**

```
MSYS_NO_PATHCONV=1 docker cp "$(cd backend/app && pwd -W)/engine/step2_sale_days.py" restock-dev-backend:/app/app/engine/step2_sale_days.py
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && TEST_DATABASE_URL='postgresql+asyncpg://postgres:local_check_db_password@db:5432/replenish_test' PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest tests/unit/test_engine_types.py tests/unit/test_engine_step2.py -v --no-header 2>&1"
```

Expected: 新 2 个 migration 测 passed；`test_engine_step2.py` 如存在也应 passed（因为 `InventoryStock.__getitem__` 不存在，老测试用 `inv["available"]` 的会炸 — 下一个 task 处理）

如果 `test_engine_step2.py` 失败，记下失败的测试名，Step 9 修它们。

- [ ] **Step 9: 修 `test_engine_step2.py` 老 fixture（如 Step 8 报错）**

将测试中的 `{"available": x, "reserved": y, "in_transit": z, "total": t}` 替换为 `InventoryStock(available=x, reserved=y, in_transit=z)`（total 是 property 不入参）。

重新跑 Step 8 的命令确认全部 passed。

- [ ] **Step 10: Commit**

```bash
git add backend/app/engine/step2_sale_days.py backend/tests/unit/test_engine_step2.py backend/tests/unit/test_engine_types.py
git commit -m "refactor(engine): step2 迁移到 InventoryStock dataclass

merge_inventory / compute_sale_days / run_step2 不再返回 4-key dict，而是
InventoryStock frozen dataclass，mypy 能在编译期捕获 inv['avialable'] 这类
字符串 key 拼错（原来静默 KeyError 或返回 0）。

compute_sale_days 读 stock.total（property）而非 dict['total']，消除一致性
负担（原 merge_inventory 手算 total 写入 dict，容易与 available+reserved+
in_transit 不同步）。

tests/unit/test_engine_types.py 加 2 条 migration 回归断言；
test_engine_step2.py 老 fixture 同步迁移。

Progress P2-A4 from docs/superpowers/reviews/2026-04-21-full-audit.md"
```

---

### Task 4: step4 迁移 `load_local_inventory` / `compute_total` 用 `LocalStock`

**Files:**
- Modify: `backend/app/engine/step4_total.py`
- Test: `backend/tests/unit/test_engine_step4.py`
- Test: `backend/tests/unit/test_engine_types.py`

- [ ] **Step 1: 写 compute_total 接 LocalStock 的失败测试**

Append to `backend/tests/unit/test_engine_types.py`:

```python
def test_compute_total_accepts_local_stock() -> None:
    from app.engine.context import LocalStock
    from app.engine.step4_total import compute_total

    # sum_qty=100, sum_velocity=10, buffer=30天 → buffer_qty=300
    # local=40+10=50, safety=0 → purchase_qty = 100 + 300 - 50 + 0 = 350
    result = compute_total(
        sku="SKU-A",
        country_qty_for_sku={"US": 60, "GB": 40},
        velocity_for_sku={"US": 6.0, "GB": 4.0},
        local_stock_for_sku=LocalStock(available=40, reserved=10),
        buffer_days=30,
        safety_stock_days=0,
    )
    assert result == 350


def test_compute_total_accepts_none_local_stock() -> None:
    from app.engine.step4_total import compute_total

    result = compute_total(
        sku="SKU-B",
        country_qty_for_sku={"US": 10},
        velocity_for_sku={"US": 0.0},
        local_stock_for_sku=None,
        buffer_days=30,
        safety_stock_days=0,
    )
    assert result == 10  # 10 + 0 - 0 + 0
```

- [ ] **Step 2: 运行测试确认失败**

```
MSYS_NO_PATHCONV=1 docker cp "$(cd backend/tests && pwd -W)/unit/test_engine_types.py" restock-dev-backend:/tmp/tests/unit/test_engine_types.py
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest tests/unit/test_engine_types.py::test_compute_total_accepts_local_stock -v --no-header 2>&1"
```

Expected: `TypeError: 'LocalStock' object is not subscriptable`（因为 compute_total 内部 `local_stock_for_sku.get("available", 0)` 当它是 dict）

- [ ] **Step 3: 迁移 compute_total**

Edit `backend/app/engine/step4_total.py` — 替换 `compute_total` 函数：

```python
def compute_total(
    sku: str,
    country_qty_for_sku: dict[str, int],
    velocity_for_sku: dict[str, float],
    local_stock_for_sku: LocalStock | None,
    buffer_days: int,
    safety_stock_days: int = 0,
) -> int:
    sum_qty = sum(country_qty_for_sku.values())
    sum_velocity = sum(velocity_for_sku.values())
    buffer_qty = math.ceil(sum_velocity * buffer_days)
    safety_qty = math.ceil(sum_velocity * safety_stock_days)
    local_total = local_stock_for_sku.total if local_stock_for_sku is not None else 0
    raw_purchase_qty = sum_qty + buffer_qty - local_total + safety_qty
    # 本地库存过剩时公式可能为负，夹到 0（DB 侧也有 CheckConstraint 双保险）
    purchase_qty = max(0, int(raw_purchase_qty))
    logger.info(
        "step4_purchase_qty_computed",
        sku=sku,
        sum_qty=sum_qty,
        sum_velocity=sum_velocity,
        buffer_qty=buffer_qty,
        safety_qty=safety_qty,
        local_total=local_total,
        raw_purchase_qty=raw_purchase_qty,
        purchase_qty=purchase_qty,
    )
    return purchase_qty
```

- [ ] **Step 4: 迁移 load_local_inventory**

Edit same file — 替换 `load_local_inventory` 函数：

```python
async def load_local_inventory(
    db: AsyncSession,
    commodity_skus: list[str] | None,
) -> dict[str, LocalStock]:
    stmt = (
        select(
            InventorySnapshotLatest.commodity_sku,
            func.sum(InventorySnapshotLatest.available).label("avail"),
            func.sum(InventorySnapshotLatest.reserved).label("reserv"),
        )
        .join(Warehouse, Warehouse.id == InventorySnapshotLatest.warehouse_id)
        .where(Warehouse.type == 1)
        .group_by(InventorySnapshotLatest.commodity_sku)
    )
    if commodity_skus is not None:
        stmt = stmt.where(InventorySnapshotLatest.commodity_sku.in_(commodity_skus))
    rows = (await db.execute(stmt)).all()
    return {sku: LocalStock(available=int(a or 0), reserved=int(r or 0)) for sku, a, r in rows}
```

- [ ] **Step 5: 加 import**

Edit top of `backend/app/engine/step4_total.py`，确保 `from app.engine.context import EngineContext, LocalStock`。

- [ ] **Step 6: 运行新 + 老 step4 测试**

```
MSYS_NO_PATHCONV=1 docker cp "$(cd backend/app && pwd -W)/engine/step4_total.py" restock-dev-backend:/app/app/engine/step4_total.py
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && TEST_DATABASE_URL='postgresql+asyncpg://postgres:local_check_db_password@db:5432/replenish_test' PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest tests/unit/test_engine_types.py tests/unit/test_engine_step4.py -v --no-header 2>&1"
```

Expected：migration 测 passed；原 `test_engine_step4.py` 里构造 `local_stock_for_sku={"available": ..., "reserved": ...}` 的测试会 `AttributeError: 'dict' object has no attribute 'total'`。

- [ ] **Step 7: 修 `test_engine_step4.py` 老 fixture（如 Step 6 报错）**

把测试里传给 `compute_total` 的 `local_stock_for_sku={"available": x, "reserved": y}` 替换成 `LocalStock(available=x, reserved=y)`，加 `from app.engine.context import LocalStock`。

重跑 Step 6，确认全部 passed。

- [ ] **Step 8: Commit**

```bash
git add backend/app/engine/step4_total.py backend/tests/unit/test_engine_step4.py backend/tests/unit/test_engine_types.py
git commit -m "refactor(engine): step4 迁移到 LocalStock dataclass

load_local_inventory 返回 dict[str, LocalStock]；compute_total 的
local_stock_for_sku 参数改 LocalStock | None，内部用 .total property 替代
旧 dict.get('available') + dict.get('reserved')。

tests/unit/test_engine_types.py 加 2 条 migration 回归；
test_engine_step4.py 老 fixture 同步迁移。

Progress P2-A4 from docs/superpowers/reviews/2026-04-21-full-audit.md"
```

---

### Task 5: step4 返回类型从 `dict[str, dict[str, int]]` 折叠为 `dict[str, int]`

**Files:**
- Modify: `backend/app/engine/step4_total.py`
- Modify: `backend/app/engine/context.py`（更新 EngineContext.local_stock 类型）
- Modify: `backend/app/engine/runner.py`（consumer）
- Modify: `backend/tests/unit/test_engine_step4.py`（如消费 step4_total）
- Test: `backend/tests/unit/test_engine_types.py`

- [ ] **Step 1: 写 step4_total 新签名测试**

Append to `backend/tests/unit/test_engine_types.py`:

```python
def test_step4_total_returns_flat_sku_to_int_dict() -> None:
    from app.engine.context import EngineContext, LocalStock
    from app.engine.step4_total import step4_total

    ctx = EngineContext(
        country_qty={"SKU-A": {"US": 100}, "SKU-B": {"GB": 40}},
        velocity={"SKU-A": {"US": 10.0}, "SKU-B": {"GB": 4.0}},
        local_stock={
            "SKU-A": LocalStock(available=20, reserved=10),  # 30
            "SKU-B": LocalStock(available=5, reserved=0),  # 5
        },
        buffer_days=30,
        safety_stock_days=0,
    )
    result = step4_total(ctx)

    # 新签名：dict[sku, int]，不再有 {"purchase_qty": int} 包裹
    assert isinstance(result, dict)
    assert all(isinstance(v, int) for v in result.values())
    # SKU-A: 100 + 300 - 30 = 370
    assert result["SKU-A"] == 370
    # SKU-B: 40 + 120 - 5 = 155
    assert result["SKU-B"] == 155
```

- [ ] **Step 2: 运行测试确认失败（类型不符）**

```
MSYS_NO_PATHCONV=1 docker cp "$(cd backend/tests && pwd -W)/unit/test_engine_types.py" restock-dev-backend:/tmp/tests/unit/test_engine_types.py
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest tests/unit/test_engine_types.py::test_step4_total_returns_flat_sku_to_int_dict -v --no-header 2>&1"
```

Expected: `AssertionError` on `isinstance(v, int)`（当前 v 是 dict）

- [ ] **Step 3: 更新 EngineContext.local_stock 类型**

Edit `backend/app/engine/context.py` — 替换 EngineContext 定义：

```python
@dataclass
class EngineContext:
    country_qty: dict[str, dict[str, int]] = field(default_factory=dict)
    velocity: dict[str, dict[str, float]] = field(default_factory=dict)
    local_stock: dict[str, LocalStock] = field(default_factory=dict)
    buffer_days: int = 30
    safety_stock_days: int = 15
```

- [ ] **Step 4: 折叠 step4_total 返回类型**

Edit `backend/app/engine/step4_total.py` — 替换 `step4_total` 函数：

```python
def step4_total(ctx: EngineContext) -> dict[str, int]:
    """Return ``{sku: purchase_qty}`` for all SKUs with engine signals."""
    result: dict[str, int] = {}
    all_skus = set(ctx.country_qty) | set(ctx.velocity) | set(ctx.local_stock)
    for sku in all_skus:
        result[sku] = compute_total(
            sku=sku,
            country_qty_for_sku=ctx.country_qty.get(sku, {}),
            velocity_for_sku=ctx.velocity.get(sku, {}),
            local_stock_for_sku=ctx.local_stock.get(sku),
            buffer_days=ctx.buffer_days,
            safety_stock_days=ctx.safety_stock_days,
        )
    return result
```

- [ ] **Step 5: 运行 step4 + 新回归测试**

```
MSYS_NO_PATHCONV=1 docker cp "$(cd backend/app && pwd -W)/engine/step4_total.py" restock-dev-backend:/app/app/engine/step4_total.py
MSYS_NO_PATHCONV=1 docker cp "$(cd backend/app && pwd -W)/engine/context.py" restock-dev-backend:/app/app/engine/context.py
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && TEST_DATABASE_URL='postgresql+asyncpg://postgres:local_check_db_password@db:5432/replenish_test' PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest tests/unit/test_engine_types.py tests/unit/test_engine_step4.py -v --no-header 2>&1"
```

Expected: 新 migration 测 passed；`test_engine_step4.py` 里消费 `step4_total` 返回值的测（若有 `result["SKU-A"]["purchase_qty"]` 的访问）会炸。

- [ ] **Step 6: 修 test_engine_step4.py + 查 runner.py consumer**

Grep check：
```
grep -rn 'step4_total\|\["purchase_qty"\]' backend/app/engine/runner.py backend/tests/
```

任何 `result[sku]["purchase_qty"]` 替换为 `result[sku]`。

Edit `backend/app/engine/runner.py` — 定位消费 step4 结果的地方（查找 `compute_total` 或 `step4_total`），确保消费 `dict[str, int]` 而非 `dict[str, dict[str, int]]`。

- [ ] **Step 7: 重跑 + 跑 runner 测试**

```
MSYS_NO_PATHCONV=1 docker cp "$(cd backend/app && pwd -W)/engine/runner.py" restock-dev-backend:/app/app/engine/runner.py
MSYS_NO_PATHCONV=1 docker cp "$(cd backend/tests && pwd -W)/unit/test_engine_step4.py" restock-dev-backend:/tmp/tests/unit/test_engine_step4.py
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && TEST_DATABASE_URL='postgresql+asyncpg://postgres:local_check_db_password@db:5432/replenish_test' PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest tests/unit/test_engine_types.py tests/unit/test_engine_step4.py tests/unit/test_engine_runner.py -v --no-header 2>&1"
```

Expected: 全部 passed。

- [ ] **Step 8: Commit**

```bash
git add backend/app/engine/step4_total.py backend/app/engine/context.py backend/app/engine/runner.py backend/tests/unit/test_engine_step4.py backend/tests/unit/test_engine_types.py
git commit -m "refactor(engine): step4_total 返回值从 {sku:{purchase_qty:int}} 折叠为 {sku:int}

内层 dict 只有一个 key 是历史残留。runner 拿到后无论如何都要 [sku]['purchase_qty']
一路展开再用，徒增 3 字符访问和 key 拼错的风险。EngineContext.local_stock
同步改为 dict[str, LocalStock]。

Progress P2-A4 from docs/superpowers/reviews/2026-04-21-full-audit.md"
```

---

### Task 6: 全量 pytest + mypy 回归验证（Phase 1 收口）

**Files:** 无新建；只跑命令。

- [ ] **Step 1: 全量 mypy strict**

```
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /app && MYPY_CACHE_DIR=/tmp/.mypy_cache /install/bin/mypy app 2>&1 | tail -5"
```

Expected: `Success: no issues found in 109 source files`

如有新 error，通常是 `build_dashboard_payload` 或其他调用 `compute_total` 的地方 — 修掉（把 `local_stock.get(sku)` 返回值类型从 `dict | None` 理解成 `LocalStock | None`）。

- [ ] **Step 2: 全量 pytest（~10 min 后台跑）**

```
MSYS_NO_PATHCONV=1 docker exec --user root restock-dev-backend rm -rf /tmp/tests/tests
MSYS_NO_PATHCONV=1 docker cp "$(cd backend/tests && pwd -W)" restock-dev-backend:/tmp/
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && TEST_DATABASE_URL='postgresql+asyncpg://postgres:local_check_db_password@db:5432/replenish_test' PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest -c /app/pyproject.toml -o cache_dir=/tmp/pytest_cache tests -q --no-header 2>&1 | tail -3"
```

Expected: `35X passed in 10:XX`（略多于 350 因为新增 ~9 条 engine_types 测）

- [ ] **Step 3: ruff check**

```
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "/install/bin/ruff check /app/app --cache-dir /tmp/.ruff_cache 2>&1 | tail -3"
```

Expected: `All checks passed!`

- [ ] **Step 4: 如有回归，修到绿再进 Phase 2。**

---

## Phase 2 — P2-D3 Bundle Visualizer 一次性调研

### Task 7: 加 visualizer 到 vite.config.ts（临时）

**Files:**
- Temp modify: `frontend/vite.config.ts`（本 task 结束前会还原）

- [ ] **Step 1: 临时加 visualizer 插件**

Edit `frontend/vite.config.ts` — 在 `plugins` 数组顶部加：

```typescript
import { visualizer } from 'rollup-plugin-visualizer'
```

在 `plugins: [` 数组末尾（`Components({...})` 之后）加：

```typescript
      visualizer({
        filename: 'dist/stats.html',
        open: false,
        gzipSize: true,
        brotliSize: true,
        template: 'treemap',
      }),
```

- [ ] **Step 2: 用 npx 跑一次 build（不装本地 deps）**

```bash
cd frontend
npx --yes rollup-plugin-visualizer --version   # 预取到 npx cache
npm run build
```

预期 `dist/stats.html` 生成（~200-500 KB HTML）。如 `rollup-plugin-visualizer` 不在 path，`npm run build` 会因 `import { visualizer } from 'rollup-plugin-visualizer'` 失败。那就走 Step 3 的临时本地安装：

- [ ] **Step 3（如 Step 2 失败）: 临时本地安装（不改 package.json）**

```bash
cd frontend
npm install --no-save rollup-plugin-visualizer
npm run build
```

`--no-save` 保证 package.json / lockfile 不被污染。

- [ ] **Step 4: 验证 stats.html 生成**

```
ls -lh frontend/dist/stats.html
```

Expected：文件存在，大小 200KB-1MB。

---

### Task 8: 分析 stats.html 并产出 findings 文档

**Files:**
- New: `docs/superpowers/reviews/2026-04-22-bundle-visualizer-findings.md`

- [ ] **Step 1: 用浏览器打开 stats.html**

```bash
# Windows
start frontend/dist/stats.html
# 或 macOS
open frontend/dist/stats.html
# 或 Linux
xdg-open frontend/dist/stats.html
```

页面会显示 treemap 可视化，大块矩形代表大 chunk。

- [ ] **Step 2: 关注下面 3 个问题并记下答案**

1. `element-plus-*.js`（906 KB）里最大的 3 个 module 是什么？分别占多少 KB？
2. `charts-*.js`（557 KB）的 echarts 构成里是否有用不到的模块（如 gl / map / 3d）？
3. `index-*.js`（55 KB）是否意外包含了本应被 manual-chunks 拆走的大依赖？

用浏览器放大 element-plus chunk，右键 module 可看路径和大小。

- [ ] **Step 3: 写 findings 文档**

Create `docs/superpowers/reviews/2026-04-22-bundle-visualizer-findings.md`:

```markdown
# Bundle Visualizer Findings — 2026-04-22

> 一次性 `rollup-plugin-visualizer` 调研，关闭 audit P2-D3。运行方式：临时 `npm install --no-save rollup-plugin-visualizer` + `npm run build` 生成 `dist/stats.html`。visualizer 不入 package.json，本文档是唯一持久产物。

## 执行概要

| chunk | 最小化后 | gzip | brotli |
|---|---|---|---|
| element-plus | <填实测 KB> | <填> | <填> |
| charts | <填> | <填> | <填> |
| framework | <填> | <填> | <填> |
| index | <填> | <填> | <填> |

## element-plus 分析（906 KB 原值）

- Top 3 modules（按大小）：
  1. `<module path>` — <KB>
  2. `<module path>` — <KB>
  3. `<module path>` — <KB>
- Tree-shake 漏项判断：<有 / 无>
- 如有，建议动作：<按需 import / 替换轻量组件 / 懒加载路由>

## charts (echarts) 分析（557 KB 原值）

- 检测到的 echarts 模块：<列出>
- 未使用但被包含的：<列出>
- 建议动作：<改 `echarts/core` + 按需注册 / 保持现状>

## index 分析（55 KB 原值）

- 包含内容：<列出 top 5 文件>
- 是否有意外的大依赖：<是 / 否>

## 总结与行动项

- [ ] 如发现 element-plus tree-shake 漏项，开 follow-up plan（如 `refactor/element-plus-on-demand.md`）
- [ ] 如发现 echarts 未用模块，开 follow-up plan
- [ ] 如 index 正常，归档本调研，结束

## 附：运行方法复现

```bash
cd frontend
npm install --no-save rollup-plugin-visualizer
# 临时在 vite.config.ts 加 visualizer() 插件（见 git history Task 7 所示）
npm run build
open dist/stats.html
# 看完记得 git checkout frontend/vite.config.ts 回到未改状态
```
```

填完 `<...>` 占位（用浏览器看到的实际数据）。

- [ ] **Step 4: 验证 findings 文档内容**

```bash
cat docs/superpowers/reviews/2026-04-22-bundle-visualizer-findings.md | head -40
```

Expected：所有 `<...>` 占位已填实数据。

---

### Task 9: 还原 vite.config.ts + 卸载 visualizer + commit findings

**Files:**
- Restore: `frontend/vite.config.ts`（回到 master）
- Uninstall: `rollup-plugin-visualizer`
- Commit: `docs/superpowers/reviews/2026-04-22-bundle-visualizer-findings.md`

- [ ] **Step 1: 还原 vite.config.ts**

```bash
git checkout frontend/vite.config.ts
```

确认 `frontend/vite.config.ts` 无 visualizer 相关行。

- [ ] **Step 2: 卸载临时安装的 rollup-plugin-visualizer**

```bash
cd frontend
npm uninstall rollup-plugin-visualizer
cd ..
```

然后检查 package.json / package-lock.json 是否干净：

```bash
git diff frontend/package.json frontend/package-lock.json
```

Expected: 无 diff（Task 7 用的是 `--no-save`；如果 uninstall 反倒让 lockfile 脏了，也 `git checkout`）：

```bash
git checkout frontend/package.json frontend/package-lock.json
```

- [ ] **Step 3: 清掉 dist/stats.html**

```bash
rm -f frontend/dist/stats.html
```

- [ ] **Step 4: 验证工作区干净（除了 findings.md）**

```bash
git status
```

Expected: 只有 `docs/superpowers/reviews/2026-04-22-bundle-visualizer-findings.md` untracked，其他全干净。

- [ ] **Step 5: Commit findings**

```bash
git add docs/superpowers/reviews/2026-04-22-bundle-visualizer-findings.md
git commit -m "docs(review): bundle visualizer 一次性调研结果

用 rollup-plugin-visualizer（--no-save，不入 deps）跑一次 production build，
分析 element-plus 906KB / charts 557KB / index 55KB 的 module 构成，
列出 top 消耗点和潜在 tree-shake 漏项。

工具本身不入 package.json，vite.config.ts 已还原。本 doc 是唯一产物，
后续若要重跑复现步骤已在文档末尾。

Close P2-D3 from docs/superpowers/reviews/2026-04-21-full-audit.md"
```

---

## 最终验证（两 Phase 都完成后）

### Task 10: 开 PR 前最后一轮验证

- [ ] **Step 1: 跑 frontend 全套**

```bash
cd frontend
npx vue-tsc --noEmit
npm run lint
npx vitest run
npx vite build
```

Expected：全绿，vite build 无警告。

- [ ] **Step 2: 跑 backend 全套（可前台）**

```
MSYS_NO_PATHCONV=1 docker exec --user root restock-dev-backend rm -rf /tmp/tests/tests
MSYS_NO_PATHCONV=1 docker cp "$(cd backend/tests && pwd -W)" restock-dev-backend:/tmp/
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /tmp && TEST_DATABASE_URL='postgresql+asyncpg://postgres:local_check_db_password@db:5432/replenish_test' PYTHONPATH=/app:/install/lib/python3.11/site-packages /install/bin/pytest -c /app/pyproject.toml -o cache_dir=/tmp/pytest_cache tests -q --no-header 2>&1 | tail -3"
MSYS_NO_PATHCONV=1 docker exec restock-dev-backend bash -c "cd /app && MYPY_CACHE_DIR=/tmp/.mypy_cache /install/bin/mypy app 2>&1 | tail -3"
```

Expected: pytest `35X passed`，mypy `Success: no issues found in 109 source files`。

- [ ] **Step 3: push + 开 PR**

```bash
git push -u origin refactor/engine-types-and-bundle-viz
gh pr create --base master --head refactor/engine-types-and-bundle-viz \
  --title "refactor(engine): InventoryStock/LocalStock dataclass 替代 dict + bundle visualizer 调研" \
  --body "## Summary

关闭 2026-04-21 audit 最后两项跳过项：

- **P2-A4**: 引擎 step2/step4 的 \`{available, reserved, in_transit, total}\` / \`{available, reserved}\` / \`{purchase_qty: int}\` 三种命名 dict 改成 frozen dataclass \`InventoryStock\` / \`LocalStock\` 和扁平 \`dict[sku, int]\`。outer \`dict[sku][country]\` lookup 保持不变（无收益）；DB JSONB 字段（country_breakdown / warehouse_breakdown）不动。
- **P2-D3**: 用 \`rollup-plugin-visualizer\` (npm install --no-save) 跑一次 build 看 element-plus 906KB / charts 557KB 的 module 构成，结果写进 \`docs/superpowers/reviews/2026-04-22-bundle-visualizer-findings.md\`。visualizer 不入 package.json。

## Test plan

- [x] backend pytest: 35X passed（+9 engine_types 测）
- [x] backend mypy strict: 109 files / 0 errors
- [x] backend ruff: clean
- [x] frontend vue-tsc / ESLint / vitest / vite build: all clean
- [x] bundle findings doc 已 commit，vite.config.ts 已还原，package.json 无变更

## Breaking changes

无（引擎内部类型变化，不影响 API / DB / 前端契约）。

## Follow-ups

如 findings doc 指出值得优化的 tree-shake 漏项，下一个 PR \`refactor/element-plus-on-demand\` 或 \`refactor/echarts-trim\` 处理。"
```

---

## 自检 Checklist

- [x] 每个 Task 都有明确文件路径、代码块、pytest 命令
- [x] 每个 Step 2-5 分钟粒度，无 "TBD" / "implement appropriate error handling" 等 placeholder
- [x] TDD 顺序：Step 1 写失败测试 → Step 2 确认失败 → Step 3 实现 → Step 4 确认通过 → Step 5 commit
- [x] 类型一致性：`InventoryStock(available, reserved, in_transit)` 贯穿所有 Task；`LocalStock(available, reserved)` 贯穿
- [x] 回归保护：Task 3 / 4 / 5 每一步都在改动后跑对应 step 的老测试捕捉兼容性
- [x] Phase 2 明确标注"临时操作"防止 visualizer 误入 deps
- [x] 最终 Task 10 一次性验证三轨（backend 测 + mypy + frontend 测 + build）

## Spec 覆盖

- P2-A4 ✓（Task 1-5 + 回归 Task 6）
- P2-D3 ✓（Task 7-9）

## 风险记录

- **Task 3 Step 9** / **Task 4 Step 7**: 老 `test_engine_step2.py` / `test_engine_step4.py` 的 fixture 用字符串 key dict 构造 inventory/local_stock，迁移时可能有漏网之鱼。执行时如发现某条老测试炸，统一替换即可 — 这是设计期望行为（类型更严）。
- **Task 7 Step 2**: 如果 `rollup-plugin-visualizer` 在 registry 不可达（网络问题），降级到 Step 3 的 `--no-save` 本地装。
- **Task 9 Step 1**: `git checkout frontend/vite.config.ts` 在 Git Bash / Windows 下路径无问题；如遇 CRLF 警告无害。
