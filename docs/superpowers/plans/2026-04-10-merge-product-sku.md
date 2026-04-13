# Merge Product + SKU Config Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge the "商品" (DataProductsView) and "SKU 配置" (SkuConfigView) pages into a single page that shows SKU-level data with expandable listing rows, and inline edit for enabled/lead_time.

**Architecture:** Create a new backend endpoint `GET /api/data/sku-overview` that returns paginated SKU-grouped data (sku_config + aggregated listings). Frontend replaces DataProductsView with a new expandable table that also handles SKU config inline editing. Remove SkuConfigView from navigation.

**Tech Stack:** Python/FastAPI/SQLAlchemy (backend), Vue 3/TypeScript/Element Plus (frontend)

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `backend/app/schemas/data.py` | Modify | Add SkuOverview response schemas |
| `backend/app/api/data.py` | Modify | Add `GET /api/data/sku-overview` endpoint |
| `frontend/src/api/data.ts` | Modify | Add SkuOverview types and API call |
| `frontend/src/views/data/DataProductsView.vue` | Rewrite | SKU-grouped expandable table with inline config |
| `frontend/src/config/navigation.ts` | Modify | Remove SKU 配置 from SETTINGS |
| `frontend/src/router/index.ts` | Modify | Redirect /settings/sku → /data/products |

---

### Task 1: Backend — Add SkuOverview schemas

**Files:**
- Modify: `backend/app/schemas/data.py`

- [ ] **Step 1: Add SkuOverview response models**

Add to the end of `backend/app/schemas/data.py`:

```python
# ==================== SKU Overview (grouped) ====================
class SkuListingItem(BaseModel):
    """Single marketplace listing under a SKU."""
    id: int
    shop_id: str
    marketplace_id: str
    seller_sku: str | None = None
    day7_sale_num: int | None = None
    day14_sale_num: int | None = None
    day30_sale_num: int | None = None
    online_status: str
    last_sync_at: str | None = None

    model_config = {"from_attributes": True}


class SkuOverviewItem(BaseModel):
    """SKU-level row with config + aggregated listing info."""
    commodity_sku: str
    commodity_name: str | None = None
    main_image: str | None = None
    enabled: bool
    lead_time_days: int | None = None
    listing_count: int
    total_day30_sales: int
    listings: list[SkuListingItem]


class SkuOverviewListOut(BaseModel):
    items: list[SkuOverviewItem]
    total: int
    page: int
    page_size: int
```

- [ ] **Step 2: Verify — run tests**

Run: `cd backend && python -m pytest tests/unit/test_schemas.py -v 2>/dev/null; python -c "from app.schemas.data import SkuOverviewListOut; print('OK')"`
Expected: "OK"

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/data.py
git commit -m "feat(backend): add SkuOverview schemas for grouped product+config data"
```

---

### Task 2: Backend — Add `/api/data/sku-overview` endpoint

**Files:**
- Modify: `backend/app/api/data.py`

- [ ] **Step 1: Add the endpoint**

Add after the existing `list_product_listings_data` function in `backend/app/api/data.py`:

```python
from app.schemas.data import SkuOverviewItem, SkuOverviewListOut, SkuListingItem

@router.get("/sku-overview", response_model=SkuOverviewListOut)
async def list_sku_overview(
    keyword: str | None = Query(default=None, description="按 commodity_sku 模糊搜索"),
    enabled: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(db_session),
    _: dict = Depends(get_current_session),
) -> SkuOverviewListOut:
    """Return SKU-level overview: config + aggregated listings, paginated by SKU."""
    # 1. Query sku_config (paginated)
    base = select(SkuConfig).order_by(SkuConfig.commodity_sku)
    if enabled is not None:
        base = base.where(SkuConfig.enabled.is_(enabled))
    if keyword:
        base = base.where(
            SkuConfig.commodity_sku.ilike(f"%{escape_like(keyword)}%", escape="\\")
        )

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    sku_rows = (
        await db.execute(base.offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()

    if not sku_rows:
        return SkuOverviewListOut(items=[], total=int(total or 0), page=page, page_size=page_size)

    sku_codes = [r.commodity_sku for r in sku_rows]

    # 2. Batch-load all listings for these SKUs
    listing_rows = (
        await db.execute(
            select(ProductListing)
            .where(ProductListing.commodity_sku.in_(sku_codes))
            .order_by(ProductListing.commodity_sku, ProductListing.marketplace_id)
        )
    ).scalars().all()

    # Group listings by SKU
    listings_by_sku: dict[str, list[ProductListing]] = {}
    for pl in listing_rows:
        listings_by_sku.setdefault(pl.commodity_sku, []).append(pl)

    # 3. Build response
    items: list[SkuOverviewItem] = []
    for sku_cfg in sku_rows:
        sku = sku_cfg.commodity_sku
        sku_listings = listings_by_sku.get(sku, [])
        # Get name + image from first listing
        name = sku_listings[0].commodity_name if sku_listings else None
        image = sku_listings[0].main_image if sku_listings else None
        total_day30 = sum((pl.day30_sale_num or 0) for pl in sku_listings)

        items.append(
            SkuOverviewItem(
                commodity_sku=sku,
                commodity_name=name,
                main_image=image,
                enabled=sku_cfg.enabled,
                lead_time_days=sku_cfg.lead_time_days,
                listing_count=len(sku_listings),
                total_day30_sales=total_day30,
                listings=[
                    SkuListingItem(
                        id=pl.id,
                        shop_id=pl.shop_id,
                        marketplace_id=pl.marketplace_id,
                        seller_sku=pl.seller_sku,
                        day7_sale_num=pl.day7_sale_num,
                        day14_sale_num=pl.day14_sale_num,
                        day30_sale_num=pl.day30_sale_num,
                        online_status=pl.online_status or "",
                        last_sync_at=pl.last_sync_at.isoformat() if pl.last_sync_at else None,
                    )
                    for pl in sku_listings
                ],
            )
        )

    return SkuOverviewListOut(items=items, total=int(total or 0), page=page, page_size=page_size)
```

Note: Add `from app.models.sku import SkuConfig` to imports if not already present.

- [ ] **Step 2: Verify — run backend tests**

Run: `cd backend && python -m pytest -p no:cacheprovider -k "not test_sync_all" 2>&1 | tail -3`
Expected: Tests pass

- [ ] **Step 3: Verify — manual API test**

Run: `cd backend && python -c "import asyncio; from app.db.session import async_session_factory; print('db ok')"`
Start server and test: `curl http://localhost:8000/api/data/sku-overview?page=1&page_size=5` (with auth header)

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/data.py
git commit -m "feat(backend): add /api/data/sku-overview endpoint with grouped SKU data"
```

---

### Task 3: Frontend — Add SkuOverview API types and client

**Files:**
- Modify: `frontend/src/api/data.ts`

- [ ] **Step 1: Add types and function**

Add to the end of `frontend/src/api/data.ts`:

```typescript
// ========== SKU Overview (grouped) ==========
export interface SkuListingItem {
  id: number
  shop_id: string
  marketplace_id: string
  seller_sku: string | null
  day7_sale_num: number | null
  day14_sale_num: number | null
  day30_sale_num: number | null
  online_status: string
  last_sync_at: string | null
}

export interface SkuOverviewItem {
  commodity_sku: string
  commodity_name: string | null
  main_image: string | null
  enabled: boolean
  lead_time_days: number | null
  listing_count: number
  total_day30_sales: number
  listings: SkuListingItem[]
}

export async function listSkuOverview(params: {
  keyword?: string
  enabled?: boolean
  page?: number
  page_size?: number
}): Promise<PageResult<SkuOverviewItem>> {
  const { data } = await client.get('/api/data/sku-overview', { params })
  return data
}
```

- [ ] **Step 2: Verify — type check**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/data.ts
git commit -m "feat(frontend): add SkuOverview API types and client function"
```

---

### Task 4: Frontend — Rewrite DataProductsView with expandable SKU rows

**Files:**
- Rewrite: `frontend/src/views/data/DataProductsView.vue`

- [ ] **Step 1: Rewrite the component**

Replace the entire file with a new implementation that:
- Uses `listSkuOverview` instead of `listDataProductListings`
- Shows parent rows with: SkuCard (image+name), 启用 switch, 提前期 input, 站点数, 30天总销量
- Uses `el-table` expand row to show child listings: 站点, 卖家SKU, 7/14/30天销量, 在售状态
- Search by keyword, filter by enabled status
- Inline editing calls `patchSkuConfig` for enabled/lead_time changes
- "从商品同步初始化" button calls `initSkuConfigs`
- Server-side pagination at SKU level

Parent row columns:
| SKU (SkuCard) | 启用 (switch) | 覆盖提前期 (input-number) | 站点数 | 30天总销量 |

Expand child row columns:
| 站点 | 卖家SKU | 7天销量 | 14天销量 | 30天销量 | 在售状态 | 最后同步 |

- [ ] **Step 2: Verify — type check**

Run: `cd frontend && npx vue-tsc --noEmit`
Expected: No errors

- [ ] **Step 3: Verify — vite build**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/data/DataProductsView.vue
git commit -m "feat(ui): rewrite products page with SKU-grouped expandable rows and inline config"
```

---

### Task 5: Frontend — Remove SKU 配置 from navigation and router

**Files:**
- Modify: `frontend/src/config/navigation.ts`
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: Remove SKU 配置 from navigation**

In `frontend/src/config/navigation.ts`, remove this line from SETTINGS > 基础配置:
```typescript
          { to: '/settings/sku', label: 'SKU 配置', icon: PackageSearch },
```

- [ ] **Step 2: Replace SKU config route with redirect**

In `frontend/src/router/index.ts`, replace the `settings/sku` route:
```typescript
// Replace:
      {
        path: 'settings/sku',
        name: 'sku-config',
        component: () => import('@/views/SkuConfigView.vue'),
        meta: { title: 'SKU 配置', section: 'SETTINGS' },
      },
// With:
      { path: 'settings/sku', redirect: '/data/products' },
```

- [ ] **Step 3: Verify — vite build**

Run: `cd frontend && npx vite build`
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
git add frontend/src/config/navigation.ts frontend/src/router/index.ts
git commit -m "refactor(nav): remove SKU config from SETTINGS, redirect to data/products"
```

---

## Final Navigation State After All Merges

```
SETTINGS > 基础配置
  ├─ 全局参数
  └─ 邮编规则
```

Reduced from 5 items to 2. Three pages merged into DATA:
- 店铺管理 → DATA > 店铺 (Phase A ✅)
- 仓库配置 → DATA > 仓库 (Phase B ✅)
- SKU 配置 → DATA > 商品 (Phase C — this plan)

## Summary

| Task | Scope | What Changes |
|------|-------|-------------|
| 1 | Backend schemas | SkuOverview response models |
| 2 | Backend API | New `/api/data/sku-overview` endpoint |
| 3 | Frontend API | TypeScript types + client function |
| 4 | Frontend UI | Rewrite DataProductsView with expand rows + inline config |
| 5 | Frontend nav | Remove SKU 配置 menu, add redirect |
