# Navigation Restructure Design

## Goal

Restructure the frontend sidebar navigation from 6 loosely named Chinese sections to 4 top-level English uppercase categories with uniform naming, clearer grouping, and a new "Sync Log" page split from the existing Sync Console.

## Architecture

The navigation uses a centralized config (`src/config/navigation.ts`) that drives both the sidebar rendering in `AppLayout.vue` and the route definitions in `router/index.ts`. Changes touch: navigation config, router, AppLayout sidebar rendering (support for sub-category headers), and a new SyncLogView page.

## Navigation Structure

```
HOME                              /workspace
  └─ 总览                          /workspace

RESTOCK                           /restock
  ├─ 当前建议                      /restock/current
  ├─ 发起补货                      /restock/run
  └─ 历史记录                      /restock/history
  (hidden) 建议详情                 /restock/suggestions/:id

DATA                              /data
  ├─ 基础数据 (sub-category label, not clickable)
  │   ├─ 店铺                      /data/shops
  │   ├─ 仓库                      /data/warehouses
  │   └─ 商品                      /data/products
  └─ 业务数据 (sub-category label, not clickable)
      ├─ 订单                      /data/orders
      ├─ 库存                      /data/inventory
      └─ 出库记录                   /data/out-records

SETTINGS                          /settings
  ├─ 同步管理 (sub-category label, not clickable)
  │   ├─ 数据同步                   /settings/sync
  │   └─ 同步日志                   /settings/sync-log
  ├─ 基础配置 (sub-category label, not clickable)
  │   ├─ 全局参数                   /settings/global
  │   ├─ SKU 配置                  /settings/sku
  │   ├─ 仓库配置                   /settings/warehouse
  │   ├─ 邮编规则                   /settings/zipcode
  │   └─ 店铺管理                   /settings/shop
  └─ 系统监控 (sub-category label, not clickable)
      ├─ 接口监控                   /settings/api-monitor
      ├─ 性能监控                   /settings/performance
      └─ 积压提示                   /settings/overstock
```

## Sidebar Rendering Changes

Current navigation config uses a flat `{ label, icon, to }` structure per group. New structure needs a **sub-category** level:

```typescript
interface NavItem {
  label: string
  icon: Component
  to: string
}

interface NavSubCategory {
  label: string           // e.g. "基础数据", rendered as gray non-clickable header
  items: NavItem[]
}

interface NavGroup {
  title: string           // e.g. "HOME", "RESTOCK", rendered as uppercase bold label
  children: (NavItem | NavSubCategory)[]
}
```

**Rendering rules:**
- Top-level `title` → English uppercase, bold, small-caps style
- `NavSubCategory.label` → Gray text, smaller font, non-clickable, acts as visual divider
- `NavItem` → Clickable RouterLink with icon, same as current
- Groups with only direct NavItem children (HOME, RESTOCK) render without sub-category headers
- Groups with NavSubCategory children (DATA, SETTINGS) show the sub-category labels

## Route Migration

All old routes must redirect to new paths for bookmark compatibility:

| Old Path | New Path |
|----------|----------|
| `/replenishment/current` | `/restock/current` |
| `/replenishment/run` | `/restock/run` |
| `/replenishment/history` | `/restock/history` |
| `/replenishment/suggestions/:id` | `/restock/suggestions/:id` |
| `/config/global` | `/settings/global` |
| `/config/sku` | `/settings/sku` |
| `/config/warehouse` | `/settings/warehouse` |
| `/config/zipcode` | `/settings/zipcode` |
| `/config/shop` | `/settings/shop` |
| `/sync` | `/settings/sync` |
| `/troubleshooting/api-monitor` | `/settings/api-monitor` |
| `/troubleshooting/performance` | `/settings/performance` |
| `/troubleshooting/overstock` | `/settings/overstock` |

Also preserve existing legacy redirects (`/suggestions`, `/suggestions/:id`, `/history`, `/ops/sync`, `/monitor/overstock`).

## New Page: SyncLogView

Split from current `SyncConsoleView.vue`.

**SyncConsoleView retains:**
- Scheduler toggle (auto sync on/off)
- Auto sync task cards (interval, last run status)
- Manual sync trigger buttons

**New SyncLogView contains:**
- Sync state table (job name, last run, last success, status, error)
- Sync status pie chart (success/failed/running/idle)
- Any log/history display that was in the original console

Route: `/settings/sync-log`

## Breadcrumb Updates

Current breadcrumb format: `Workspace > {section} > {title}`

New format uses the top-level group as first segment:

| Route | Breadcrumb |
|-------|-----------|
| `/workspace` | HOME > 总览 |
| `/restock/current` | RESTOCK > 当前建议 |
| `/restock/suggestions/5` | RESTOCK > 建议详情 |
| `/data/orders` | DATA > 订单 |
| `/settings/sync` | SETTINGS > 数据同步 |
| `/settings/sku` | SETTINGS > SKU 配置 |

## Files Affected

- Modify: `src/config/navigation.ts` — new structure with NavGroup/NavSubCategory types
- Modify: `src/components/AppLayout.vue` — sidebar rendering for sub-categories
- Modify: `src/router/index.ts` — all route paths + redirects
- Create: `src/views/SyncLogView.vue` — extracted from SyncConsoleView
- Modify: `src/views/SyncConsoleView.vue` — remove log/state content moved to SyncLogView
- All existing view files — update `meta.section` values to match new group titles

## Out of Scope

- No page content changes (besides SyncConsoleView split)
- No new features
- No design system / color / icon changes
- No backend API changes
