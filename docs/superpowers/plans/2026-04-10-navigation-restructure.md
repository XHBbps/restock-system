# Navigation Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure sidebar navigation from 6 Chinese sections to 4 English uppercase groups (HOME/RESTOCK/DATA/SETTINGS) with sub-category headers and a new SyncLogView page.

**Architecture:** Update navigation config types to support sub-categories, rewrite router paths, update AppLayout sidebar rendering, and extract log/state content from SyncConsoleView into a new SyncLogView.

**Tech Stack:** Vue 3, TypeScript, Vue Router, Element Plus, lucide-vue-next icons

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `src/config/navigation.ts` | Rewrite | Navigation data + types with sub-category support |
| `src/components/AppLayout.vue` | Modify | Sidebar rendering for sub-categories + breadcrumb updates |
| `src/router/index.ts` | Rewrite | New route paths + legacy redirects |
| `src/views/SyncLogView.vue` | Create | Sync state table + failed API calls + status chart |
| `src/views/SyncConsoleView.vue` | Modify | Remove log/state sections, keep scheduler + task cards |

---

### Task 1: Rewrite navigation config with sub-category support

**Files:**
- Modify: `frontend/src/config/navigation.ts`

- [ ] **Step 1: Replace the full content of `navigation.ts`**

```typescript
import type { Component } from 'vue'
import {
  Activity,
  Boxes,
  ClipboardList,
  FileText,
  Gauge,
  History,
  LayoutDashboard,
  PackageSearch,
  PlayCircle,
  RefreshCw,
  Settings,
  ShieldAlert,
  Store,
  Truck,
  Warehouse,
} from 'lucide-vue-next'

export interface NavItem {
  to: string
  label: string
  icon: Component
}

export interface NavSubCategory {
  label: string
  items: NavItem[]
}

export interface NavGroup {
  title: string
  children: (NavItem | NavSubCategory)[]
}

export function isSubCategory(child: NavItem | NavSubCategory): child is NavSubCategory {
  return 'items' in child
}

export const navigationGroups: NavGroup[] = [
  {
    title: 'HOME',
    children: [
      { to: '/workspace', label: '总览', icon: LayoutDashboard },
    ],
  },
  {
    title: 'RESTOCK',
    children: [
      { to: '/restock/current', label: '当前建议', icon: ClipboardList },
      { to: '/restock/run', label: '发起补货', icon: PlayCircle },
      { to: '/restock/history', label: '历史记录', icon: History },
    ],
  },
  {
    title: 'DATA',
    children: [
      {
        label: '基础数据',
        items: [
          { to: '/data/shops', label: '店铺', icon: Store },
          { to: '/data/warehouses', label: '仓库', icon: Warehouse },
          { to: '/data/products', label: '商品', icon: PackageSearch },
        ],
      },
      {
        label: '业务数据',
        items: [
          { to: '/data/orders', label: '订单', icon: ClipboardList },
          { to: '/data/inventory', label: '库存', icon: Boxes },
          { to: '/data/out-records', label: '出库记录', icon: Truck },
        ],
      },
    ],
  },
  {
    title: 'SETTINGS',
    children: [
      {
        label: '同步管理',
        items: [
          { to: '/settings/sync', label: '数据同步', icon: RefreshCw },
          { to: '/settings/sync-log', label: '同步日志', icon: FileText },
        ],
      },
      {
        label: '基础配置',
        items: [
          { to: '/settings/global', label: '全局参数', icon: Settings },
          { to: '/settings/sku', label: 'SKU 配置', icon: PackageSearch },
          { to: '/settings/warehouse', label: '仓库配置', icon: Warehouse },
          { to: '/settings/zipcode', label: '邮编规则', icon: Truck },
          { to: '/settings/shop', label: '店铺管理', icon: Store },
        ],
      },
      {
        label: '系统监控',
        items: [
          { to: '/settings/api-monitor', label: '接口监控', icon: ShieldAlert },
          { to: '/settings/performance', label: '性能监控', icon: Gauge },
          { to: '/settings/overstock', label: '积压提示', icon: Activity },
        ],
      },
    ],
  },
]
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/config/navigation.ts
git commit -m "refactor(nav): rewrite navigation config with sub-category support

New types: NavGroup with NavItem | NavSubCategory children.
4 top-level groups: HOME, RESTOCK, DATA, SETTINGS."
```

---

### Task 2: Update AppLayout sidebar rendering and breadcrumb

**Files:**
- Modify: `frontend/src/components/AppLayout.vue`

- [ ] **Step 1: Update the template sidebar nav section**

Replace lines 12-26 (the `<nav>` block) with:

```vue
      <nav class="nav">
        <div v-for="group in navigationGroups" :key="group.title" class="nav-group">
          <div class="nav-group-title">{{ group.title }}</div>
          <template v-for="child in group.children" :key="'label' in child && 'items' in child ? child.label : child.to">
            <template v-if="isSubCategory(child)">
              <div class="nav-subcategory-title">{{ child.label }}</div>
              <RouterLink
                v-for="item in child.items"
                :key="item.to"
                :to="item.to"
                class="nav-item"
                active-class="nav-item-active"
              >
                <component :is="item.icon" class="nav-item-icon" :size="16" />
                <span class="nav-item-label">{{ item.label }}</span>
              </RouterLink>
            </template>
            <RouterLink
              v-else
              :to="child.to"
              class="nav-item"
              active-class="nav-item-active"
            >
              <component :is="child.icon" class="nav-item-icon" :size="16" />
              <span class="nav-item-label">{{ child.label }}</span>
            </RouterLink>
          </template>
        </div>
      </nav>
```

- [ ] **Step 2: Update the script import**

Change line 65:

```typescript
// Old:
import { navigationGroups } from '@/config/navigation'
// New:
import { isSubCategory, navigationGroups } from '@/config/navigation'
```

- [ ] **Step 3: Update breadcrumb root text**

In the template, line 42, change:

```vue
<!-- Old: -->
        <RouterLink to="/workspace" class="breadcrumb-root">工作台</RouterLink>
<!-- New: -->
        <RouterLink to="/workspace" class="breadcrumb-root">Restock</RouterLink>
```

- [ ] **Step 4: Add CSS for sub-category title**

Add after the `.nav-group-title` block (after line 183):

```scss
.nav-subcategory-title {
  padding: $space-2 $space-3 $space-1;
  margin-top: $space-2;
  color: $color-text-disabled;
  font-size: 11px;
  font-weight: $font-weight-medium;
}

.nav-group .nav-subcategory-title:first-child {
  margin-top: 0;
}
```

- [ ] **Step 5: Verify dev server renders correctly**

Run: `cd frontend && npm run dev`
Check the sidebar renders 4 groups with sub-category headers in DATA and SETTINGS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/AppLayout.vue
git commit -m "refactor(nav): update sidebar rendering for sub-categories and breadcrumb"
```

---

### Task 3: Rewrite router with new paths and legacy redirects

**Files:**
- Modify: `frontend/src/router/index.ts`

- [ ] **Step 1: Replace the full routes array**

Replace the entire `routes` array (lines 5-153) with:

```typescript
const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/',
    component: () => import('@/components/AppLayout.vue'),
    redirect: '/workspace',
    children: [
      // === HOME ===
      {
        path: 'workspace',
        name: 'workspace',
        component: () => import('@/views/WorkspaceView.vue'),
        meta: { title: '总览', section: 'HOME' },
      },

      // === RESTOCK ===
      {
        path: 'restock/current',
        name: 'suggestion-list',
        component: () => import('@/views/SuggestionListView.vue'),
        meta: { title: '当前建议', section: 'RESTOCK' },
      },
      {
        path: 'restock/run',
        name: 'restock-run',
        component: () => import('@/views/ReplenishmentRunView.vue'),
        meta: { title: '发起补货', section: 'RESTOCK' },
      },
      {
        path: 'restock/history',
        name: 'history',
        component: () => import('@/views/HistoryView.vue'),
        meta: { title: '历史记录', section: 'RESTOCK' },
      },
      {
        path: 'restock/suggestions/:id',
        name: 'suggestion-detail',
        component: () => import('@/views/SuggestionDetailView.vue'),
        meta: { title: '建议详情', section: 'RESTOCK' },
      },

      // === DATA ===
      {
        path: 'data/shops',
        name: 'data-shops',
        component: () => import('@/views/data/DataShopsView.vue'),
        meta: { title: '店铺', section: 'DATA' },
      },
      {
        path: 'data/warehouses',
        name: 'data-warehouses',
        component: () => import('@/views/data/DataWarehousesView.vue'),
        meta: { title: '仓库', section: 'DATA' },
      },
      {
        path: 'data/products',
        name: 'data-products',
        component: () => import('@/views/data/DataProductsView.vue'),
        meta: { title: '商品', section: 'DATA' },
      },
      {
        path: 'data/orders',
        name: 'data-orders',
        component: () => import('@/views/data/DataOrdersView.vue'),
        meta: { title: '订单', section: 'DATA' },
      },
      {
        path: 'data/inventory',
        name: 'data-inventory',
        component: () => import('@/views/data/DataInventoryView.vue'),
        meta: { title: '库存', section: 'DATA' },
      },
      {
        path: 'data/out-records',
        name: 'data-out-records',
        component: () => import('@/views/data/DataOutRecordsView.vue'),
        meta: { title: '出库记录', section: 'DATA' },
      },

      // === SETTINGS ===
      {
        path: 'settings/sync',
        name: 'sync-console',
        component: () => import('@/views/SyncConsoleView.vue'),
        meta: { title: '数据同步', section: 'SETTINGS' },
      },
      {
        path: 'settings/sync-log',
        name: 'sync-log',
        component: () => import('@/views/SyncLogView.vue'),
        meta: { title: '同步日志', section: 'SETTINGS' },
      },
      {
        path: 'settings/global',
        name: 'global-config',
        component: () => import('@/views/GlobalConfigView.vue'),
        meta: { title: '全局参数', section: 'SETTINGS' },
      },
      {
        path: 'settings/sku',
        name: 'sku-config',
        component: () => import('@/views/SkuConfigView.vue'),
        meta: { title: 'SKU 配置', section: 'SETTINGS' },
      },
      {
        path: 'settings/warehouse',
        name: 'warehouse',
        component: () => import('@/views/WarehouseView.vue'),
        meta: { title: '仓库配置', section: 'SETTINGS' },
      },
      {
        path: 'settings/zipcode',
        name: 'zipcode-rule',
        component: () => import('@/views/ZipcodeRuleView.vue'),
        meta: { title: '邮编规则', section: 'SETTINGS' },
      },
      {
        path: 'settings/shop',
        name: 'shop',
        component: () => import('@/views/ShopView.vue'),
        meta: { title: '店铺管理', section: 'SETTINGS' },
      },
      {
        path: 'settings/api-monitor',
        name: 'api-monitor',
        component: () => import('@/views/ApiMonitorView.vue'),
        meta: { title: '接口监控', section: 'SETTINGS' },
      },
      {
        path: 'settings/performance',
        name: 'performance-monitor',
        component: () => import('@/views/PerformanceMonitorView.vue'),
        meta: { title: '性能监控', section: 'SETTINGS' },
      },
      {
        path: 'settings/overstock',
        name: 'overstock',
        component: () => import('@/views/OverstockView.vue'),
        meta: { title: '积压提示', section: 'SETTINGS' },
      },

      // === Legacy redirects ===
      { path: 'replenishment/current', redirect: '/restock/current' },
      { path: 'replenishment/run', redirect: '/restock/run' },
      { path: 'replenishment/history', redirect: '/restock/history' },
      { path: 'replenishment/suggestions/:id', redirect: (to) => `/restock/suggestions/${to.params.id}` },
      { path: 'config/global', redirect: '/settings/global' },
      { path: 'config/sku', redirect: '/settings/sku' },
      { path: 'config/warehouse', redirect: '/settings/warehouse' },
      { path: 'config/zipcode', redirect: '/settings/zipcode' },
      { path: 'config/shop', redirect: '/settings/shop' },
      { path: 'sync', redirect: '/settings/sync' },
      { path: 'troubleshooting/api-monitor', redirect: '/settings/api-monitor' },
      { path: 'troubleshooting/performance', redirect: '/settings/performance' },
      { path: 'troubleshooting/overstock', redirect: '/settings/overstock' },
      { path: 'suggestions', redirect: '/restock/current' },
      { path: 'suggestions/:id', redirect: (to) => `/restock/suggestions/${to.params.id}` },
      { path: 'history', redirect: '/restock/history' },
      { path: 'ops/sync', redirect: '/settings/sync' },
      { path: 'monitor/overstock', redirect: '/settings/overstock' },
      {
        path: ':pathMatch(.*)*',
        name: 'not-found',
        component: () => import('@/views/NotFoundView.vue'),
        meta: { title: '未找到' },
      },
    ],
  },
]
```

- [ ] **Step 2: Update SuggestionDetailView internal link**

Read `frontend/src/views/SuggestionDetailView.vue` and search for any `router.push` or `RouterLink` that references `/replenishment/`. Update to `/restock/`. Similarly check `HistoryView.vue` for links to suggestion detail.

Read `frontend/src/views/HistoryView.vue` and update any `/replenishment/suggestions/` links to `/restock/suggestions/`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/router/index.ts frontend/src/views/SuggestionDetailView.vue frontend/src/views/HistoryView.vue
git commit -m "refactor(nav): rewrite router with new paths and legacy redirects

Routes: /replenishment/* → /restock/*, /config/* → /settings/*,
/sync → /settings/sync, /troubleshooting/* → /settings/*.
All old paths redirect for bookmark compatibility."
```

---

### Task 4: Create SyncLogView (extract from SyncConsoleView)

**Files:**
- Create: `frontend/src/views/SyncLogView.vue`

- [ ] **Step 1: Create the SyncLogView component**

Create `frontend/src/views/SyncLogView.vue` containing:
- Sync state table (with pagination)
- Failed API calls table (with toggle + pagination)
- Sync status pie chart
- Stats: 失败同步任务, 失败接口调用

```vue
<template>
  <div class="sync-log-view">
    <section class="top-grid">
      <DashboardStatCard
        title="失败同步任务"
        :value="failedSyncCount"
        :trend="failedSyncCount > 0 ? '建议优先排查' : '状态正常'"
        :trend-type="failedSyncCount > 0 ? 'negative' : 'positive'"
        hint="按最近一次执行状态统计"
      />
      <DashboardStatCard
        title="失败接口调用"
        :value="failedCallCount"
        hint="最近 24 小时累计失败调用"
      />
    </section>

    <DashboardChartCard
      title="同步任务状态分布"
      description="查看当前同步面板最近一次执行结果的整体分布。"
      :option="syncStatusChartOption"
      :empty="syncState.length === 0"
      empty-text="暂无同步状态数据"
    />

    <DataTableCard title="同步任务状态" description="统一查看各同步任务最近一次执行结果。">
      <template #toolbar>
        <el-button @click="loadSyncState">刷新</el-button>
      </template>
      <SyncStateTable :rows="pagedSyncState" :job-label-map="syncJobLabelMap" />
      <template #pagination>
        <TablePaginationBar
          v-model:current-page="syncStatePage"
          v-model:page-size="syncStatePageSize"
          :total="syncState.length"
        />
      </template>
    </DataTableCard>

    <DataTableCard title="最近失败调用" description="用于排查外部接口失败并直接重试。">
      <template #toolbar>
        <el-switch v-model="onlyFailed" active-text="仅失败" @change="loadRecentCalls" />
      </template>
      <FailedApiCallTable :rows="pagedRecentCalls" @retry="retry" />
      <template #pagination>
        <TablePaginationBar
          v-model:current-page="recentPage"
          v-model:page-size="recentPageSize"
          :total="recentCalls.length"
        />
      </template>
    </DataTableCard>

    <TaskProgress v-if="currentTaskId" :task-id="currentTaskId" @terminal="onTaskDone" />
  </div>
</template>

<script setup lang="ts">
import { listSyncState, type SyncStateRow } from '@/api/data'
import {
  getApiCallsOverview,
  getRecentCalls,
  retryCall,
  type ApiCallsOverview,
  type RecentCall,
} from '@/api/monitor'
import type { TaskRun } from '@/api/task'
import DataTableCard from '@/components/dashboard/DataTableCard.vue'
import DashboardChartCard from '@/components/dashboard/DashboardChartCard.vue'
import DashboardStatCard from '@/components/dashboard/DashboardStatCard.vue'
import TablePaginationBar from '@/components/TablePaginationBar.vue'
import TaskProgress from '@/components/TaskProgress.vue'
import FailedApiCallTable from '@/components/sync/FailedApiCallTable.vue'
import SyncStateTable from '@/components/sync/SyncStateTable.vue'
import { syncJobLabelMap } from '@/config/sync'
import { getActionErrorMessage } from '@/utils/apiError'
import { getSyncStatusMeta } from '@/utils/status'
import type { EChartsCoreOption } from 'echarts/core'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref } from 'vue'

const syncState = ref<SyncStateRow[]>([])
const overview = ref<ApiCallsOverview | null>(null)
const recentCalls = ref<RecentCall[]>([])
const onlyFailed = ref(true)
const currentTaskId = ref<number | null>(null)

const syncStatePage = ref(1)
const syncStatePageSize = ref(10)
const recentPage = ref(1)
const recentPageSize = ref(10)

const failedSyncCount = computed(() => syncState.value.filter((r) => r.last_status === 'failed').length)
const failedCallCount = computed(() =>
  (overview.value?.endpoints || []).reduce((sum, ep) => sum + ep.failed_count, 0),
)

const pagedSyncState = computed(() => {
  const start = (syncStatePage.value - 1) * syncStatePageSize.value
  return syncState.value.slice(start, start + syncStatePageSize.value)
})

const pagedRecentCalls = computed(() => {
  const start = (recentPage.value - 1) * recentPageSize.value
  return recentCalls.value.slice(start, start + recentPageSize.value)
})

const syncStatusChartOption = computed<EChartsCoreOption>(() => {
  const counts = syncState.value.reduce<Record<string, number>>((acc, item) => {
    const key = item.last_status || 'idle'
    acc[key] = (acc[key] || 0) + 1
    return acc
  }, {})
  return {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, icon: 'circle', textStyle: { color: '#71717a' } },
    series: [
      {
        type: 'pie',
        radius: ['52%', '78%'],
        itemStyle: { borderColor: '#ffffff', borderWidth: 4 },
        label: { formatter: '{b}\n{c}', color: '#09090b', fontSize: 12 },
        data: [
          { name: '成功', value: (counts.success || 0) + (counts.completed || 0), itemStyle: { color: '#16a34a' } },
          { name: '失败', value: counts.failed || 0, itemStyle: { color: '#dc2626' } },
          { name: '执行中', value: counts.running || 0, itemStyle: { color: '#d97706' } },
          { name: '未执行', value: counts.idle || 0, itemStyle: { color: '#a1a1aa' } },
        ].filter((item) => item.value > 0),
      },
    ],
  }
})

async function loadSyncState(): Promise<void> {
  syncState.value = await listSyncState()
}

async function loadOverview(): Promise<void> {
  overview.value = await getApiCallsOverview(24)
}

async function loadRecentCalls(): Promise<void> {
  recentPage.value = 1
  recentCalls.value = await getRecentCalls({ only_failed: onlyFailed.value, limit: 200 })
}

async function reloadAll(): Promise<void> {
  await Promise.allSettled([loadSyncState(), loadOverview(), loadRecentCalls()])
}

async function retry(id: number): Promise<void> {
  try {
    const resp = await retryCall(id)
    if (resp.task_id) {
      currentTaskId.value = resp.task_id
      ElMessage.success('重试任务已入队。')
      return
    }
    ElMessage.warning('该调用暂不支持自动重试。')
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '重试失败。'))
  }
}

async function onTaskDone(task: TaskRun): Promise<void> {
  currentTaskId.value = null
  await reloadAll()
  if (task.status === 'success') {
    ElMessage.success('任务已完成，页面状态已刷新。')
    return
  }
  ElMessage.error(task.error_msg || '任务执行失败。')
}

onMounted(reloadAll)
</script>

<style lang="scss" scoped>
.sync-log-view {
  display: flex;
  flex-direction: column;
  gap: $space-6;
}

.top-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: $space-4;
}

@media (max-width: 900px) {
  .top-grid {
    grid-template-columns: 1fr;
  }
}
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/SyncLogView.vue
git commit -m "feat(nav): create SyncLogView with sync state table and failed calls

Extracted from SyncConsoleView: sync status chart, sync state table,
failed API calls table with retry support."
```

---

### Task 5: Simplify SyncConsoleView (remove extracted content)

**Files:**
- Modify: `frontend/src/views/SyncConsoleView.vue`

- [ ] **Step 1: Remove extracted sections from template**

In `SyncConsoleView.vue`, remove from the template:

1. The `stats-grid` section — remove the "失败同步任务" and "失败接口调用" stat cards (keep "自动任务数" and "手动任务数")
2. The `chart-grid` section — remove the "同步任务状态分布" chart card (keep "自动同步下次执行")
3. The `bottom-grid` section entirely (sync state table + failed API calls table)

The template should keep:
- `DashboardPageHeader` with scheduler status
- Postal compliance warning
- Stats: 自动任务数, 手动任务数 (2 cards in a grid)
- Chart: 自动同步下次执行 (single card, not in grid)
- 调度器控制 section
- 自动同步任务 section
- 手动同步任务 section
- TaskProgress

- [ ] **Step 2: Remove unused imports and variables from script**

Remove from script:
- Imports: `FailedApiCallTable`, `SyncStateTable`, `DashboardChartCard` (for pie chart — keep if used for bar chart... actually DashboardChartCard is still used for nextRunChartOption, keep it)
- Remove imports: `FailedApiCallTable`, `SyncStateTable`
- Remove imports from `@/api/monitor`: `getRecentCalls`, `retryCall`, `type RecentCall` (keep `getApiCallsOverview` and `type ApiCallsOverview` ONLY if still used — but since we removed the failed call stats, check if overview is still needed... actually we removed the "失败接口调用" stat, so remove overview too)
- Remove imports from `@/api/data`: `listSyncState`, `type SyncStateRow` — BUT check if syncState is still used for the pie chart... we removed the pie chart, so check if syncState is used elsewhere. It IS used by `autoJobCards` and `getActionMeta`. So keep `listSyncState` and `type SyncStateRow`.
- Remove: `getRecentCalls`, `retryCall`, `type RecentCall` from monitor imports
- Remove: `getApiCallsOverview`, `type ApiCallsOverview` from monitor imports
- Remove variables: `overview`, `recentCalls`, `onlyFailed`, `recentPage`, `recentPageSize`, `syncStatePage`, `syncStatePageSize`, `failedSyncCount`, `failedCallCount`, `pagedSyncState`, `pagedRecentCalls`, `syncStatusChartOption`
- Remove functions: `loadOverview`, `loadRecentCalls`, `retry`
- Update `reloadAll` to only call: `loadScheduler()`, `loadSyncState()`
- Remove `getSyncStatusMeta` import ONLY if no longer used — it IS still used by `getActionMeta`, keep it.

- [ ] **Step 3: Verify the component still works**

Run: `cd frontend && npm run dev`
Navigate to `/settings/sync` and verify scheduler controls, auto sync cards, and manual sync cards render correctly.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/SyncConsoleView.vue
git commit -m "refactor(nav): remove log/state sections from SyncConsoleView

Sync state table, failed API calls, and status pie chart are now
in the dedicated SyncLogView at /settings/sync-log."
```

---

## Summary

| Task | Files | What Changes |
|------|-------|-------------|
| 1 | `navigation.ts` | New types + 4-group structure |
| 2 | `AppLayout.vue` | Sub-category rendering + breadcrumb |
| 3 | `router/index.ts` + views | New paths + legacy redirects |
| 4 | `SyncLogView.vue` | New page with extracted content |
| 5 | `SyncConsoleView.vue` | Remove extracted content |
