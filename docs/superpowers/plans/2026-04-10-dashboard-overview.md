# Dashboard Overview (信息总览) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite the workspace page as a business-focused "信息总览" dashboard with KPI cards, country stock vs target chart, TOP urgent SKUs table, and current suggestion summary.

**Architecture:** New backend endpoint `GET /api/metrics/dashboard` aggregates data from current suggestion items (sale_days_snapshot, country_breakdown, push_status, urgent) and sku_config. Frontend rewrites WorkspaceView to consume this single API endpoint.

**Tech Stack:** Python/FastAPI/SQLAlchemy (backend), Vue 3/TypeScript/ECharts/Element Plus (frontend)

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/api/metrics.py` | Modify | Add `GET /api/metrics/dashboard` endpoint |
| `frontend/src/api/dashboard.ts` | Create | Dashboard API types + client |
| `frontend/src/views/WorkspaceView.vue` | Rewrite | New dashboard layout |
| `frontend/src/config/navigation.ts` | Modify | Rename 总览 → 信息总览 |
| `frontend/src/router/index.ts` | Modify | Update route meta title |

---

### Task 1: Backend — Add dashboard overview endpoint

**Files:**
- Modify: `backend/app/api/metrics.py`

**What the endpoint returns:**

```python
{
  "enabled_sku_count": 42,          # sku_config where enabled=True
  "suggestion_item_count": 38,      # items in current suggestion
  "pushed_count": 12,               # items with push_status='pushed'
  "urgent_count": 5,                # items with urgent=True
  "suggestion_id": 7,               # current suggestion id (null if none)
  "suggestion_status": "draft",     # current suggestion status
  "target_days": 60,                # from global config
  "country_stock_days": [           # aggregated from sale_days_snapshot
    {"country": "US", "avg_sale_days": 45.2, "sku_count": 15},
    {"country": "DE", "avg_sale_days": 72.1, "sku_count": 8},
    ...
  ],
  "top_urgent_skus": [              # top 10 urgent items
    {"commodity_sku": "SKU-001", "total_qty": 500, "country_breakdown": {"US": 300, "DE": 200}},
    ...
  ]
}
```

- [ ] **Step 1: Add Pydantic schemas**

Add to `backend/app/api/metrics.py` (at the top, after imports):

```python
from pydantic import BaseModel

class CountryStockDays(BaseModel):
    country: str
    avg_sale_days: float
    sku_count: int

class UrgentSkuItem(BaseModel):
    commodity_sku: str
    total_qty: int
    country_breakdown: dict[str, int]

class DashboardOverview(BaseModel):
    enabled_sku_count: int
    suggestion_item_count: int
    pushed_count: int
    urgent_count: int
    suggestion_id: int | None
    suggestion_status: str | None
    target_days: int
    country_stock_days: list[CountryStockDays]
    top_urgent_skus: list[UrgentSkuItem]
```

- [ ] **Step 2: Add the endpoint**

```python
@router.get("/dashboard", response_model=DashboardOverview)
async def get_dashboard_overview(
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> DashboardOverview:
    from app.models.global_config import GlobalConfig
    from app.models.sku import SkuConfig
    from app.models.suggestion import Suggestion, SuggestionItem

    # 1. Enabled SKU count
    enabled_sku_count = (
        await db.execute(select(func.count()).where(SkuConfig.enabled.is_(True)))
    ).scalar_one()

    # 2. Global config target_days
    config = (await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1))).scalar_one_or_none()
    target_days = config.target_days if config else 60

    # 3. Current suggestion
    suggestion = (
        await db.execute(
            select(Suggestion)
            .where(Suggestion.status.in_(["draft", "partial"]))
            .order_by(Suggestion.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if not suggestion:
        return DashboardOverview(
            enabled_sku_count=int(enabled_sku_count or 0),
            suggestion_item_count=0,
            pushed_count=0,
            urgent_count=0,
            suggestion_id=None,
            suggestion_status=None,
            target_days=target_days,
            country_stock_days=[],
            top_urgent_skus=[],
        )

    # 4. Load suggestion items
    items = (
        await db.execute(
            select(SuggestionItem).where(SuggestionItem.suggestion_id == suggestion.id)
        )
    ).scalars().all()

    pushed_count = sum(1 for it in items if it.push_status == "pushed")
    urgent_count = sum(1 for it in items if it.urgent)

    # 5. Aggregate sale_days by country
    country_days: dict[str, list[float]] = {}
    for it in items:
        if not it.sale_days_snapshot:
            continue
        for country, days_val in it.sale_days_snapshot.items():
            if isinstance(days_val, (int, float)) and days_val >= 0:
                country_days.setdefault(country, []).append(float(days_val))

    country_stock_days = sorted(
        [
            CountryStockDays(
                country=c,
                avg_sale_days=round(sum(vals) / len(vals), 1),
                sku_count=len(vals),
            )
            for c, vals in country_days.items()
        ],
        key=lambda x: x.avg_sale_days,
    )

    # 6. Top 10 urgent SKUs
    urgent_items = sorted(
        [it for it in items if it.urgent],
        key=lambda it: it.total_qty,
        reverse=True,
    )[:10]

    top_urgent_skus = [
        UrgentSkuItem(
            commodity_sku=it.commodity_sku,
            total_qty=it.total_qty,
            country_breakdown=it.country_breakdown or {},
        )
        for it in urgent_items
    ]

    return DashboardOverview(
        enabled_sku_count=int(enabled_sku_count or 0),
        suggestion_item_count=len(items),
        pushed_count=pushed_count,
        urgent_count=urgent_count,
        suggestion_id=suggestion.id,
        suggestion_status=suggestion.status,
        target_days=target_days,
        country_stock_days=country_stock_days,
        top_urgent_skus=top_urgent_skus,
    )
```

Add necessary imports at top of file: `from fastapi import Depends`, `from sqlalchemy import func, select`, `from sqlalchemy.ext.asyncio import AsyncSession`, `from app.api.deps import db_session, get_current_session`.

- [ ] **Step 3: Verify — run tests**

Run: `cd backend && python -m pytest -p no:cacheprovider -k "not test_sync_all" 2>&1 | tail -3`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/metrics.py
git commit -m "feat(backend): add /api/metrics/dashboard endpoint for overview page"
```

---

### Task 2: Frontend — Add dashboard API types and client

**Files:**
- Create: `frontend/src/api/dashboard.ts`

- [ ] **Step 1: Create the API module**

```typescript
import client from './client'

export interface CountryStockDays {
  country: string
  avg_sale_days: number
  sku_count: number
}

export interface UrgentSkuItem {
  commodity_sku: string
  total_qty: number
  country_breakdown: Record<string, number>
}

export interface DashboardOverview {
  enabled_sku_count: number
  suggestion_item_count: number
  pushed_count: number
  urgent_count: number
  suggestion_id: number | null
  suggestion_status: string | null
  target_days: number
  country_stock_days: CountryStockDays[]
  top_urgent_skus: UrgentSkuItem[]
}

export async function getDashboardOverview(): Promise<DashboardOverview> {
  const { data } = await client.get<DashboardOverview>('/api/metrics/dashboard')
  return data
}
```

- [ ] **Step 2: Verify — type check**

Run: `cd frontend && npx vue-tsc --noEmit`

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/dashboard.ts
git commit -m "feat(frontend): add dashboard overview API types and client"
```

---

### Task 3: Frontend — Rewrite WorkspaceView as 信息总览

**Files:**
- Rewrite: `frontend/src/views/WorkspaceView.vue`

**Layout:**

```
┌─ 统计卡片（4个）──────────────────────────────────┐
│  启用 SKU 数  │  当前建议条目  │  已推送/总条目  │  待补货(紧急) │
└───────────────────────────────────────────────────┘

┌─ 核心图表（全宽）─────────────────────────────────┐
│  各国库存天数 vs 目标天数（分组柱状图）               │
│  X轴=国家, 两根柱子：平均库存天数(蓝) / 目标天数(红线) │
└───────────────────────────────────────────────────┘

┌─ 底部区（2列）───────────────────────────────────┐
│  TOP 10 急需补货 SKU        │  当前建议摘要           │
│  (表格: SKU/数量/国家分布)    │  (建议单状态+进度)      │
└───────────────────────────────────────────────────┘
```

**Key details:**
- Use `getDashboardOverview()` as single data source
- Stats card "已推送/总条目" shows as `pushed_count / suggestion_item_count`
- Chart: ECharts bar chart with countries on X axis. Each country has one blue bar (avg_sale_days). Add a red markLine at target_days.
- If no current suggestion (suggestion_id is null), show empty states gracefully
- TOP urgent table: simple el-table with commodity_sku, total_qty, country breakdown tags
- Current suggestion card: id, status tag, progress (pushed/total), link to detail

- [ ] **Step 1: Rewrite the complete component**

(Implementer should write the full Vue SFC based on the layout above, using existing dashboard components: DashboardStatCard, DashboardChartCard, DataTableCard, PageSectionCard)

- [ ] **Step 2: Verify — type check**

Run: `cd frontend && npx vue-tsc --noEmit`

- [ ] **Step 3: Verify — vite build**

Run: `cd frontend && npx vite build`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/WorkspaceView.vue
git commit -m "feat(ui): rewrite workspace as business-focused dashboard (信息总览)"
```

---

### Task 4: Frontend — Rename 总览 → 信息总览 in navigation and router

**Files:**
- Modify: `frontend/src/config/navigation.ts`
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: Update navigation label**

In `navigation.ts`, change:
```typescript
{ to: '/workspace', label: '总览', icon: LayoutDashboard },
// →
{ to: '/workspace', label: '信息总览', icon: LayoutDashboard },
```

- [ ] **Step 2: Update router meta title**

In `router/index.ts`, change the workspace route:
```typescript
meta: { title: '总览', section: 'HOME' },
// →
meta: { title: '信息总览', section: 'HOME' },
```

- [ ] **Step 3: Verify — vite build**

Run: `cd frontend && npx vite build`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/config/navigation.ts frontend/src/router/index.ts
git commit -m "refactor(nav): rename 总览 to 信息总览"
```

---

## Impact Assessment

| Area | Impact |
|------|--------|
| Backend | New endpoint only, no existing API changes |
| Frontend WorkspaceView | Full rewrite, self-contained (no other pages import from it) |
| Navigation | Label change only |
| Router | Title change only |
| Other pages | Zero impact — no shared state or dependencies |

## Summary

| Task | Scope | Files | Risk |
|------|-------|-------|------|
| 1 | Backend API | metrics.py | Low — additive endpoint |
| 2 | Frontend API | dashboard.ts | Low — new file |
| 3 | Frontend UI | WorkspaceView.vue | Medium — full rewrite |
| 4 | Navigation | navigation.ts + router | Low — rename only |
