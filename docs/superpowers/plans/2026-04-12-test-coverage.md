# Test Coverage Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Step5 ceil regression, add 2 missing backend tests, add frontend SuggestionDetailView editing logic tests.

**Architecture:** TDD for all changes. Backend uses pytest with fake DB stubs. Frontend uses Vitest + Vue Test Utils with vi.mock.

**Tech Stack:** Python 3.12 / pytest / Vitest 2.1.8 / Vue Test Utils / Element Plus

**Spec:** `docs/superpowers/specs/2026-04-12-test-coverage-design.md`

---

## File Map

| File | Task | Changes |
|------|------|---------|
| `backend/app/engine/step5_warehouse_split.py` | A | line 192: `math.ceil` → `round`; line 190: remove `max(..., 0)` |
| `backend/tests/unit/test_engine_step5.py` | A | Add 4-warehouse regression test |
| `backend/tests/unit/test_pushback_purchase.py` | B | Add zero qty test |
| `frontend/src/views/__tests__/SuggestionDetailView.test.ts` | D | New file: 3 tests |

---

## Task A: Step5 ceil regression fix + test

**Files:**
- Modify: `backend/app/engine/step5_warehouse_split.py:189-192`
- Test: `backend/tests/unit/test_engine_step5.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/unit/test_engine_step5.py`:

```python
def test_four_warehouse_ceil_regression_sum_equals_country_qty() -> None:
    """Regression: math.ceil on warehouse split caused sum > country_qty.

    4 warehouses with equal order counts, country_qty=5.
    With ceil: ceil(5*0.25)=2 × 3 non-last = 6 > 5, last=max(5-6,0)=0 → sum=6≠5.
    With round: round(5*0.25)=1 × 3 = 3, last=5-3=2 → sum=5. Correct.
    """
    rules = [
        ZipcodeRule(id=1, country="JP", prefix_length=1, value_type="number",
                    operator="=", compare_value="1", warehouse_id="WH-A", priority=10),
        ZipcodeRule(id=2, country="JP", prefix_length=1, value_type="number",
                    operator="=", compare_value="2", warehouse_id="WH-B", priority=10),
        ZipcodeRule(id=3, country="JP", prefix_length=1, value_type="number",
                    operator="=", compare_value="3", warehouse_id="WH-C", priority=10),
        ZipcodeRule(id=4, country="JP", prefix_length=1, value_type="number",
                    operator="=", compare_value="4", warehouse_id="WH-D", priority=10),
    ]
    orders = [
        ("100-0000", 1),  # WH-A
        ("200-0000", 1),  # WH-B
        ("300-0000", 1),  # WH-C
        ("400-0000", 1),  # WH-D
    ]
    result = split_country_qty(
        sku="sku-A",
        country="JP",
        country_qty=5,
        orders=orders,
        rules=rules,
        country_warehouses=["WH-A", "WH-B", "WH-C", "WH-D"],
    )
    # Critical invariant: sum must equal country_qty
    assert sum(result.values()) == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /e/Ai_project/restock_system/backend && python -m pytest tests/unit/test_engine_step5.py::test_four_warehouse_ceil_regression_sum_equals_country_qty -v`

Expected: FAIL — `assert 6 == 5` (3 non-last warehouses each get `ceil(1.25)=2`, accumulated=6, last gets `max(5-6,0)=0`)

- [ ] **Step 3: Fix step5_warehouse_split.py — revert ceil to round**

In `backend/app/engine/step5_warehouse_split.py`, two changes:

Line 189-190 — remove `max(..., 0)` guard:
```python
# BEFORE:
                result[wid] = max(country_qty - accumulated, 0)
# AFTER:
                result[wid] = country_qty - accumulated
```

Line 192 — revert `math.ceil` to `round`:
```python
# BEFORE:
                share = math.ceil(country_qty * cnt / total_known)
# AFTER:
                share = round(country_qty * cnt / total_known)
```

Remove `import math` from the top of the file if it's no longer used elsewhere. (Check first — `math` is NOT used elsewhere in this file, only in the `round`/`ceil` line.)

- [ ] **Step 4: Run all Step5 tests**

Run: `cd /e/Ai_project/restock_system/backend && python -m pytest tests/unit/test_engine_step5.py -v`

Expected: ALL passed (14 tests including the new one)

- [ ] **Step 5: Run full backend test suite**

Run: `cd /e/Ai_project/restock_system/backend && python -m pytest tests/unit/ --tb=short -q`

Expected: 170 passed

- [ ] **Step 6: Commit**

```bash
cd /e/Ai_project/restock_system/backend
git add app/engine/step5_warehouse_split.py tests/unit/test_engine_step5.py
git commit -m "fix(engine): Step5 仓分配回退 ceil→round 修复 sum≠country_qty 回归 + 4 仓回归测试"
```

---

## Task B: Push zero qty test

**Files:**
- Test: `backend/tests/unit/test_pushback_purchase.py`

- [ ] **Step 1: Write the test**

Append to `backend/tests/unit/test_pushback_purchase.py`:

```python
@pytest.mark.asyncio
async def test_push_saihu_job_rejects_all_zero_qty() -> None:
    """P2-7: 全部 total_qty=0 时应抛 ValueError,不发送赛狐请求。"""
    ctx = _FakeContext({"suggestion_id": 100, "item_ids": [1, 2]})
    items = [_make_item(1, total_qty=0), _make_item(2, total_qty=0)]

    db1 = _FakeDb(
        [
            _ScalarResult(_make_config()),
            _ScalarResult(items),
        ]
    )
    factory = _FakeSessionFactory([db1])

    mock_api = AsyncMock()
    with (
        patch("app.pushback.purchase.async_session_factory", factory),
        patch("app.pushback.purchase.create_purchase_order", mock_api),
        pytest.raises(ValueError, match="total_qty 均为 0"),
    ):
        await push_saihu_job(ctx)  # type: ignore[arg-type]

    mock_api.assert_not_called()
```

- [ ] **Step 2: Run test to verify it passes**

Run: `cd /e/Ai_project/restock_system/backend && python -m pytest tests/unit/test_pushback_purchase.py::test_push_saihu_job_rejects_all_zero_qty -v`

Expected: PASS (code already has the filter from P2-7)

- [ ] **Step 3: Run full push tests**

Run: `cd /e/Ai_project/restock_system/backend && python -m pytest tests/unit/test_pushback_purchase.py -v`

Expected: 8 passed

- [ ] **Step 4: Commit**

```bash
cd /e/Ai_project/restock_system/backend
git add tests/unit/test_pushback_purchase.py
git commit -m "test(pushback): 补充 total_qty=0 全量过滤测试 [P2-7 验证]"
```

---

## Task D: SuggestionDetailView editing logic tests

**Files:**
- Create: `frontend/src/views/__tests__/SuggestionDetailView.test.ts`

**Approach:** SuggestionDetailView defines `isEditable`, `hasChanges`, `save` inside `<script setup>` (not exported). We test them indirectly: mount the component with mock data, check DOM state (disabled tags, button behavior), and verify API calls.

- [ ] **Step 1: Create the `__tests__` directory**

Run: `mkdir -p /e/Ai_project/restock_system/frontend/src/views/__tests__`

- [ ] **Step 2: Create the test file**

Create `frontend/src/views/__tests__/SuggestionDetailView.test.ts`:

```typescript
// @vitest-environment jsdom

import { flushPromises, shallowMount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import type { SuggestionDetail, SuggestionItem } from '@/api/suggestion'

// --- Mocks ---

const mockGetSuggestion = vi.fn()
const mockPatchSuggestionItem = vi.fn()

vi.mock('@/api/suggestion', () => ({
  getSuggestion: (...args: unknown[]) => mockGetSuggestion(...args),
  patchSuggestionItem: (...args: unknown[]) => mockPatchSuggestionItem(...args),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: '1' }, query: {} }),
  useRouter: () => ({ back: vi.fn(), push: vi.fn() }),
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return { ...actual, ElMessage: { success: vi.fn(), error: vi.fn() } }
})

// --- Factories ---

function makeItem(overrides: Partial<SuggestionItem> = {}): SuggestionItem {
  return {
    id: 10,
    commodity_sku: 'SKU-A',
    commodity_id: 'C001',
    commodity_name: 'Test Product',
    main_image: null,
    total_qty: 100,
    country_breakdown: { US: 60, JP: 40 },
    warehouse_breakdown: { US: { 'WH-1': 60 }, JP: { 'WH-2': 40 } },
    allocation_snapshot: null,
    t_purchase: { US: '2026-05-01', JP: '2026-05-01' },
    t_ship: { US: '2026-05-15', JP: '2026-05-15' },
    velocity_snapshot: null,
    sale_days_snapshot: null,
    urgent: false,
    push_blocker: null,
    push_status: 'pending',
    saihu_po_number: null,
    push_error: null,
    push_attempt_count: 0,
    pushed_at: null,
    ...overrides,
  }
}

function makeSuggestion(
  overrides: Partial<SuggestionDetail> = {},
  itemOverrides: Partial<SuggestionItem> = {},
): SuggestionDetail {
  return {
    id: 1,
    status: 'draft',
    triggered_by: 'manual',
    total_items: 1,
    pushed_items: 0,
    failed_items: 0,
    global_config_snapshot: {},
    created_at: '2026-04-12T10:00:00',
    archived_at: null,
    items: [makeItem(itemOverrides)],
    ...overrides,
  }
}

// --- Stubs for Element Plus components ---
const STUBS = {
  ElCard: true, ElCollapse: true, ElCollapseItem: true,
  ElAlert: true, ElTag: true, ElButton: true,
  ElInputNumber: true, ElTable: true, ElTableColumn: true,
  ElEmpty: true, SkuCard: true,
}

describe('SuggestionDetailView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('shows archived readonly tag when suggestion is archived', async () => {
    mockGetSuggestion.mockResolvedValue(makeSuggestion({ status: 'archived' }))

    const { default: View } = await import('../SuggestionDetailView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    expect(wrapper.text()).toContain('已归档建议单不可编辑')
  })

  it('shows pushed readonly tag when item is already pushed', async () => {
    mockGetSuggestion.mockResolvedValue(makeSuggestion({}, { push_status: 'pushed' }))

    const { default: View } = await import('../SuggestionDetailView.vue')
    const wrapper = shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    expect(wrapper.text()).toContain('已推送条目不可编辑')
  })

  it('loads suggestion on mount via getSuggestion API', async () => {
    mockGetSuggestion.mockResolvedValue(makeSuggestion())

    const { default: View } = await import('../SuggestionDetailView.vue')
    shallowMount(View, { global: { stubs: STUBS } })
    await flushPromises()

    expect(mockGetSuggestion).toHaveBeenCalledWith(1)
  })
})
```

- [ ] **Step 3: Run the test**

Run: `cd /e/Ai_project/restock_system/frontend && npx vitest run src/views/__tests__/SuggestionDetailView.test.ts`

Expected: 3 passed. If import errors occur due to complex dependencies (dayjs, utils), adjust stubs. Common fix: add more `vi.mock` entries for problematic imports.

- [ ] **Step 4: Run all frontend tests**

Run: `cd /e/Ai_project/restock_system/frontend && npx vitest run`

Expected: 11 passed (8 existing + 3 new)

- [ ] **Step 5: Commit**

```bash
cd /e/Ai_project/restock_system/frontend
git add src/views/__tests__/SuggestionDetailView.test.ts
git commit -m "test(frontend): SuggestionDetailView 编辑逻辑测试 — archived/pushed 禁用 + API 调用验证"
```

---

## Task E: Final verification

- [ ] **Step 1: Run full backend tests**

Run: `cd /e/Ai_project/restock_system/backend && python -m pytest tests/unit/ -v --tb=short`
Expected: 171 passed

- [ ] **Step 2: Run ruff**

Run: `cd /e/Ai_project/restock_system/backend && python -m ruff check .`
Expected: no new errors (1 pre-existing in config.py)

- [ ] **Step 3: Run full frontend tests**

Run: `cd /e/Ai_project/restock_system/frontend && npx vitest run`
Expected: 11 passed

- [ ] **Step 4: Run frontend type check**

Run: `cd /e/Ai_project/restock_system/frontend && npx vue-tsc --noEmit`
Expected: no new errors
