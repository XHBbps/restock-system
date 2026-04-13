# Remove Overstock (积压) Feature — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the entire overstock/积压 feature: the "积压提示" page, the "积压国家" field in suggestion detail, the `overstock_sku_mark` table, and all backend logic that computes/stores overstock data.

**Architecture:** Pure deletion — remove overstock code from all layers (frontend views/routes/nav, backend API/models/schemas/engine, migration, tests). Modify `step3_country_qty` to return only `country_qty` instead of a tuple. Modify initial migration inline since the project is pre-production.

**Tech Stack:** Vue 3 + TypeScript (frontend), Python + FastAPI + SQLAlchemy (backend), Alembic (migrations)

---

### Task 1: Backend — Simplify `step3_country_qty.py`

**Files:**
- Modify: `backend/app/engine/step3_country_qty.py`
- Modify: `backend/tests/unit/test_engine_step3.py`

- [ ] **Step 1: Update `compute_country_qty` to return only `country_qty`**

Change return type from `tuple[dict, dict]` to `dict[str, dict[str, int]]`. Remove the `overstock` defaultdict and the `overstock[sku].append(country)` line. The `raw < 0` branch should just `continue` without collecting anything.

```python
"""Step 3:各国建议补货量。

公式(FR-031):
    raw[国] = TARGET_DAYS x velocity[国] - (available + reserved + in_transit)
    country_qty[国] = max(raw, 0)
"""

import math
from collections import defaultdict


def compute_country_qty(
    velocity: dict[str, dict[str, float]],
    inventory: dict[str, dict[str, dict[str, int]]],
    target_days: int,
) -> dict[str, dict[str, int]]:
    """计算各 SKU 各国的补货量。

    返回:
        country_qty[sku][country] = int
    """
    country_qty: defaultdict[str, dict[str, int]] = defaultdict(dict)

    for sku, country_map in velocity.items():
        for country, v in country_map.items():
            if v <= 0:
                continue
            stock_total = inventory.get(sku, {}).get(country, {}).get("total", 0)
            raw = target_days * v - stock_total
            if raw <= 0:
                continue
            # 向上取整到件
            country_qty[sku][country] = math.ceil(raw)
    return dict(country_qty)
```

- [ ] **Step 2: Update tests to match new return type**

All tests should receive a single `dict` return instead of a tuple. Remove all overstock-related assertions.

```python
"""Step 3 country_qty 单元测试:负数 clamping。"""

from app.engine.step3_country_qty import compute_country_qty


def _make_inventory(stock_map: dict[str, dict[str, int]]) -> dict:
    """{sku: {country: total}} -> {sku: {country: {total: ...}}}"""
    return {
        sku: {country: {"total": total} for country, total in country_map.items()}
        for sku, country_map in stock_map.items()
    }


def test_basic_compute() -> None:
    velocity = {"sku-A": {"JP": 10.0, "US": 5.0}}
    inventory = _make_inventory({"sku-A": {"JP": 300, "US": 100}})
    target = 60

    qty = compute_country_qty(velocity, inventory, target)
    # JP: raw = 60*10 - 300 = 300
    assert qty["sku-A"]["JP"] == 300
    # US: raw = 60*5 - 100 = 200
    assert qty["sku-A"]["US"] == 200


def test_negative_raw_clamped_to_zero() -> None:
    velocity = {"sku-A": {"JP": 10.0, "US": 5.0}}
    inventory = _make_inventory({"sku-A": {"JP": 800, "US": 100}})
    target = 60

    qty = compute_country_qty(velocity, inventory, target)
    # JP: raw = 600-800 = -200 -> 不入 country_qty
    assert "JP" not in qty.get("sku-A", {})
    # US: 200
    assert qty["sku-A"]["US"] == 200


def test_zero_velocity_skipped() -> None:
    velocity = {"sku-A": {"JP": 0.0, "US": 5.0}}
    inventory = _make_inventory({"sku-A": {"JP": 100, "US": 100}})
    qty = compute_country_qty(velocity, inventory, 60)
    assert "JP" not in qty.get("sku-A", {})
    assert qty["sku-A"]["US"] == 200


def test_exact_target_yields_zero() -> None:
    """raw = 0 应该不入 qty。"""
    velocity = {"sku-A": {"JP": 10.0}}
    inventory = _make_inventory({"sku-A": {"JP": 600}})  # 60*10
    qty = compute_country_qty(velocity, inventory, 60)
    assert "JP" not in qty.get("sku-A", {})


def test_no_inventory_record_treated_as_zero_stock() -> None:
    velocity = {"sku-A": {"JP": 10.0}}
    inventory: dict = {}  # 没有任何库存记录
    qty = compute_country_qty(velocity, inventory, 60)
    # raw = 600 - 0 = 600
    assert qty["sku-A"]["JP"] == 600
```

- [ ] **Step 3: Run tests**

Run: `cd backend && python -m pytest tests/unit/test_engine_step3.py -v`
Expected: All 5 tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/engine/step3_country_qty.py backend/tests/unit/test_engine_step3.py
git commit -m "refactor: simplify step3 to remove overstock_countries collection"
```

---

### Task 2: Backend — Clean up `runner.py`

**Files:**
- Modify: `backend/app/engine/runner.py`

- [ ] **Step 1: Remove overstock imports and update step3 call**

In `runner.py`:

1. Remove `from app.models.overstock import OverstockSkuMark` (line 41)
2. Update the docstring at top: remove "6. Step 3: 算 country_qty + overstock" → "6. Step 3: 算 country_qty"
3. Change line 109 from `country_qty, overstock_countries = compute_country_qty(...)` to `country_qty = compute_country_qty(...)`
4. Remove `"overstock_countries": overstock_countries.get(sku, []),` from the `items_to_insert` dict (line 194)
5. Remove the entire `await _refresh_overstock_marks(...)` call (line 209) and its comment (line 208)
6. Delete the entire `_refresh_overstock_marks` function (lines 278-361)
7. Remove now-unused imports: `InventorySnapshotLatest`, `OrderHeader`, `OrderItem` — BUT only if they are not used elsewhere in the file. Check first.

- [ ] **Step 2: Verify unused imports**

Check whether `InventorySnapshotLatest`, `OrderHeader`, `OrderItem`, `Warehouse` are used anywhere else in `runner.py` besides `_refresh_overstock_marks`. If only used there, remove the imports.

- [ ] **Step 3: Run full test suite**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: All tests pass (step3 tests already updated in Task 1)

- [ ] **Step 4: Commit**

```bash
git add backend/app/engine/runner.py
git commit -m "refactor: remove overstock logic from engine runner"
```

---

### Task 3: Backend — Remove overstock model, schema fields, and API endpoints

**Files:**
- Delete: `backend/app/models/overstock.py`
- Modify: `backend/app/models/__init__.py` — remove `OverstockSkuMark` import/export
- Modify: `backend/app/models/suggestion.py` — remove `overstock_countries` column
- Modify: `backend/app/schemas/suggestion.py` — remove `overstock_countries` field
- Modify: `backend/app/api/monitor.py` — remove overstock endpoints + imports

- [ ] **Step 1: Delete `backend/app/models/overstock.py`**

Delete the entire file.

- [ ] **Step 2: Remove from `__init__.py`**

In `backend/app/models/__init__.py`, remove:
- `from app.models.overstock import OverstockSkuMark`
- `"OverstockSkuMark"` from `__all__`

- [ ] **Step 3: Remove `overstock_countries` from suggestion model**

In `backend/app/models/suggestion.py`, delete line 93:
```python
    overstock_countries: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
```

- [ ] **Step 4: Remove `overstock_countries` from suggestion schema**

In `backend/app/schemas/suggestion.py`, delete line 42:
```python
    overstock_countries: list[str]
```

- [ ] **Step 5: Remove overstock section from monitor API**

In `backend/app/api/monitor.py`:
1. Remove `from app.models.overstock import OverstockSkuMark` import
2. Delete everything from the `# ==================== Overstock SKU ====================` comment (line 196) to end of file (line 282): `OverstockOut`, `list_overstock`, `OverstockProcessedPatch`, `mark_overstock_processed`

- [ ] **Step 6: Run tests**

Run: `cd backend && python -m pytest tests/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add -u backend/app/models/ backend/app/schemas/suggestion.py backend/app/api/monitor.py
git commit -m "refactor: remove overstock model, schema fields, and API endpoints"
```

---

### Task 4: Backend — Update initial migration

**Files:**
- Modify: `backend/alembic/versions/20260408_1500_initial.py`

- [ ] **Step 1: Remove `overstock_countries` column from `suggestion_item` table**

Delete lines 399-403 (the `overstock_countries` column definition in the `suggestion_item` `create_table` call).

- [ ] **Step 2: Remove entire `overstock_sku_mark` table creation**

Delete the block from `# ==================== overstock_sku_mark ====================` through `op.create_index("ix_overstock_sku_mark_processed", ...)` (lines 437-457).

- [ ] **Step 3: Remove `overstock_sku_mark` from downgrade**

Delete lines 585-586:
```python
    op.drop_index("ix_overstock_sku_mark_processed", table_name="overstock_sku_mark")
    op.drop_table("overstock_sku_mark")
```

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/20260408_1500_initial.py
git commit -m "refactor: remove overstock from initial migration"
```

---

### Task 5: Frontend — Remove OverstockView page, navigation, and routes

**Files:**
- Delete: `frontend/src/views/OverstockView.vue`
- Modify: `frontend/src/config/navigation.ts`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/api/monitor.ts`

- [ ] **Step 1: Delete `frontend/src/views/OverstockView.vue`**

Delete the entire file.

- [ ] **Step 2: Remove overstock from navigation**

In `frontend/src/config/navigation.ts`, remove line 109:
```typescript
          { to: '/settings/overstock', label: '积压提示', icon: TrendingDown },
```

Also remove the `TrendingDown` import from `lucide-vue-next` (line 18) if it's not used elsewhere.

- [ ] **Step 3: Remove overstock routes**

In `frontend/src/router/index.ts`, remove:
1. The overstock route (lines 125-129):
```typescript
      {
        path: 'settings/overstock',
        name: 'overstock',
        component: () => import('@/views/OverstockView.vue'),
        meta: { title: '积压提示', section: 'SETTINGS' },
      },
```
2. Legacy redirects pointing to overstock (line 150 and 152):
```typescript
      { path: 'troubleshooting/overstock', redirect: '/settings/overstock' },
      { path: 'monitor/overstock', redirect: '/settings/overstock' },
```

- [ ] **Step 4: Remove overstock API functions and types**

In `frontend/src/api/monitor.ts`, delete everything from `// ========== Overstock ==========` to end of file (lines 52-76): the `Overstock` interface, `listOverstock`, and `markOverstockProcessed`.

- [ ] **Step 5: Commit**

```bash
git add -u frontend/src/views/OverstockView.vue frontend/src/config/navigation.ts frontend/src/router/index.ts frontend/src/api/monitor.ts
git commit -m "feat: remove overstock page, navigation, routes, and API client"
```

---

### Task 6: Frontend — Remove "积压国家" from SuggestionDetailView

**Files:**
- Modify: `frontend/src/views/SuggestionDetailView.vue`
- Modify: `frontend/src/api/suggestion.ts`

- [ ] **Step 1: Remove overstock_countries display from SuggestionDetailView**

In `frontend/src/views/SuggestionDetailView.vue`, delete lines 140-153 (the "积压国家" status-row block):
```html
                    <div class="status-row">
                      <span class="status-label">积压国家</span>
                      <div v-if="item.overstock_countries?.length" class="status-tag-list">
                        <el-tag
                          v-for="country in item.overstock_countries"
                          :key="country"
                          type="warning"
                          size="small"
                        >
                          {{ country }}
                        </el-tag>
                      </div>
                      <span v-else class="status-value">-</span>
                    </div>
```

- [ ] **Step 2: Remove `overstock_countries` from `SuggestionItem` type**

In `frontend/src/api/suggestion.ts`, delete line 35:
```typescript
  overstock_countries: string[]
```

- [ ] **Step 3: Verify frontend builds**

Run: `cd frontend && npx vue-tsc --noEmit && npx vite build`
Expected: No TypeScript errors, build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/SuggestionDetailView.vue frontend/src/api/suggestion.ts
git commit -m "feat: remove overstock countries from suggestion detail view"
```

---

### Task 7: Verify and Final Cleanup

- [ ] **Step 1: Grep for any remaining overstock references**

Run: `grep -ri "overstock" --include="*.py" --include="*.ts" --include="*.vue" backend/ frontend/src/`

Expected: No matches in source code (spec files are OK to leave as historical record).

- [ ] **Step 2: Run full backend tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 3: Run full frontend build**

Run: `cd frontend && npx vue-tsc --noEmit && npx vite build`
Expected: Clean build, no errors

- [ ] **Step 4: Final commit (if any cleanup was needed)**

Only if previous steps surfaced issues that needed fixing.
