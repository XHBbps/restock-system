# Plan A 前端收尾：导出 + 快照历史 + 生成开关 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 前端补齐 Excel 导出 + 快照历史 + 生成开关 UI，全量清理"赛狐推送"时代残余代码，业务人员角色补齐导出与开关读取权限。

**Architecture:**
- 新增 alembic 数据迁移：`role_permission` 表幂等授予"业务人员" `restock:export` + `config:view`
- 前端先"清理 pass"（B1-B6 refactor），再"功能 pass"（B7-B10 feat），所有变更聚合为单 PR 分 12 个 commit
- 快照历史前端排序在 `api/snapshot.ts` 内 reverse（后端按 version asc 返回）
- 生成开关采用"即时保存 + `ElSwitch :loading`" 交互，OFF→ON 增加二次确认（后端会自动归档 draft）

**Tech Stack:** Vue 3 + TypeScript + Element Plus + Pinia（前端）；FastAPI + SQLAlchemy 2 + Alembic（后端）；vitest + vue-tsc（前端验证）

**Design Spec:** `docs/superpowers/specs/2026-04-19-plan-a-frontend-completion-design.md`

**Pre-flight (执行前)：**
- 确认分支：`git checkout -b feature/plan-a-frontend-completion master`
- 确认 dev 容器运行：`docker ps | grep restock-dev`
- 确认后端 alembic 当前 head = `20260418_0900`：
  `docker exec restock-dev-backend alembic current`

---

## 文件结构

**创建：**
- `backend/alembic/versions/20260419_XXXX_grant_export_and_config_view_to_business_role.py`
- `frontend/src/api/snapshot.ts`
- `frontend/src/utils/download.ts`

**修改：**
- `frontend/src/api/suggestion.ts`（类型收敛 + 删除 `pushItems`）
- `frontend/src/api/config.ts`（追加 `getGenerationToggle` / `patchGenerationToggle`）
- `frontend/src/utils/status.ts`（删除 `partial`/`pushed` map 项 + `suggestionPushStatusMap` + `getSuggestionPushStatusMeta`）
- `frontend/src/components/SkuCard.vue`（删除未使用的 `blocker` prop）
- `frontend/src/views/SuggestionDetailView.vue`（清 push 引用；加导出按钮、快照历史区）
- `frontend/src/views/SuggestionListView.vue`（删除推送 UI；加开关只读 tag）
- `frontend/src/views/GlobalConfigView.vue`（加生成开关卡片）
- `frontend/src/views/HistoryView.vue`（替换 push 列为 export_status + snapshot_count；`canDelete` 新语义）
- `frontend/src/utils/status.test.ts`
- `frontend/src/views/__tests__/SuggestionDetailView.test.ts`
- `frontend/src/views/__tests__/SuggestionListView.test.ts`
- `frontend/src/views/__tests__/HistoryView.test.ts`
- `docs/PROGRESS.md`、`docs/Project_Architecture_Blueprint.md`

---

## Task 0: 新建功能分支

**Files:**
- Modify: 本地 git 状态

- [ ] **Step 1：切换分支**

```bash
cd /e/Ai_project/restock_system
git status
git checkout master
git pull
git checkout -b feature/plan-a-frontend-completion
```

Expected: 新分支 `feature/plan-a-frontend-completion`，工作树干净。

- [ ] **Step 2：确认 dev 后端在运行**

```bash
docker ps --filter name=restock-dev --format 'table {{.Names}}\t{{.Status}}'
docker exec restock-dev-backend alembic current
```

Expected: 后端健康，alembic current = `20260418_0900 (head)`

---

## Task 1（B0）：后端 alembic 迁移 —— 业务人员角色追加权限

**Files:**
- Create: `backend/alembic/versions/20260419_0000_grant_export_and_config_view_to_business_role.py`

- [ ] **Step 1：新建迁移文件**

```python
"""grant restock:export and config:view to business role

Revision ID: 20260419_0000
Revises: 20260418_0900
Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa


revision = "20260419_0000"
down_revision = "20260418_0900"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """幂等追加：业务人员 += restock:export, config:view。

    现有"业务人员"默认角色（20260414_2400 seed）不含 config:view / restock:export。
    前端补货单导出按钮和生成开关状态读取依赖这两条权限。
    ON CONFLICT DO NOTHING 保证已手动授予过的实例重入无副作用。
    """
    op.execute(
        sa.text(
            """
            INSERT INTO role_permission (role_id, permission_id)
            SELECT r.id, p.id
            FROM role r
            CROSS JOIN permission p
            WHERE r.name = '业务人员'
              AND p.code IN ('restock:export', 'config:view')
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM role_permission
            WHERE role_id = (SELECT id FROM role WHERE name = '业务人员')
              AND permission_id IN (
                SELECT id FROM permission WHERE code IN ('restock:export', 'config:view')
              )
            """
        )
    )
```

- [ ] **Step 2：验证迁移语法 + dry run**

```bash
docker exec restock-dev-backend alembic history | head -5
docker exec restock-dev-backend alembic upgrade --sql 20260418_0900:head
```

Expected: 输出包含两条 INSERT ... SELECT ...；无 SQL 语法错误。

- [ ] **Step 3：执行迁移**

```bash
docker exec restock-dev-backend alembic upgrade head
docker exec restock-dev-backend alembic current
```

Expected: alembic current = `20260419_0000 (head)`

- [ ] **Step 4：查询验证权限已授予**

```bash
docker exec restock-dev-db psql -U postgres -d replenish -c \
  "SELECT r.name, p.code FROM role r JOIN role_permission rp ON rp.role_id=r.id JOIN permission p ON p.id=rp.permission_id WHERE r.name='业务人员' AND p.code IN ('restock:export','config:view') ORDER BY p.code;"
```

Expected: 返回 2 行（`config:view` 与 `restock:export`）。

- [ ] **Step 5：幂等性验证（再跑一次 upgrade）**

```bash
docker exec restock-dev-backend alembic downgrade -1
docker exec restock-dev-backend alembic upgrade head
docker exec restock-dev-db psql -U postgres -d replenish -c \
  "SELECT COUNT(*) FROM role_permission rp JOIN role r ON r.id=rp.role_id JOIN permission p ON p.id=rp.permission_id WHERE r.name='业务人员' AND p.code IN ('restock:export','config:view');"
```

Expected: COUNT = 2（无重复）

- [ ] **Step 6：后端 unit 回归**

```bash
docker exec restock-dev-backend pytest tests/unit -q
```

Expected: 0 failed，无 error 新增。

- [ ] **Step 7：commit**

```bash
git add backend/alembic/versions/20260419_0000_grant_export_and_config_view_to_business_role.py
git commit -m "feat(backend): 业务人员角色追加 restock:export 与 config:view"
```

---

## Task 2（B1）：前端类型收敛 + 删除 `pushItems`

**Files:**
- Modify: `frontend/src/api/suggestion.ts`

- [ ] **Step 1：备份当前行号映射（参考用，无需改文件）**

当前 `api/suggestion.ts`：
- L14-24 `Suggestion` 接口含 `pushed_items`/`failed_items` + 5 值 status 枚举
- L26-45 `SuggestionItem` 接口含 6 个 push_* 字段 + `saihu_po_number`
- L93-102 `pushItems()` 函数

- [ ] **Step 2：重写 `Suggestion` / `SuggestionItem` 接口**

改动 `frontend/src/api/suggestion.ts:14-45`，将现有两个接口完全替换为：

```ts
export interface Suggestion {
  id: number
  status: 'draft' | 'archived' | 'error'
  triggered_by: string
  total_items: number
  snapshot_count: number
  global_config_snapshot: Record<string, unknown>
  created_at: string
  archived_at: string | null
}

export interface SuggestionItem {
  id: number
  commodity_sku: string
  commodity_id: string | null
  commodity_name: string | null
  main_image: string | null
  total_qty: number
  country_breakdown: Record<string, number>
  warehouse_breakdown: Record<string, Record<string, number>>
  allocation_snapshot: Record<string, AllocationExplanation> | null
  velocity_snapshot: Record<string, number> | null
  sale_days_snapshot: Record<string, number> | null
  urgent: boolean
  export_status: 'pending' | 'exported'
  exported_snapshot_id: number | null
  exported_at: string | null
}
```

> `status` 收敛到后端 CHECK 约束实际允许的 3 值（`backend/app/models/suggestion.py:29`）
> `snapshot_count` 为后端 `SuggestionOut.snapshot_count: int = 0`（`backend/app/schemas/suggestion.py:21`）
> `export_status` 为后端 CHECK 约束实际允许的 2 值（`backend/app/models/suggestion.py:68`）
> `main_image`（非 `main_image_url`）与后端 `SuggestionItemOut.main_image` 一致（`backend/app/schemas/suggestion.py:34`）

- [ ] **Step 3：删除 `pushItems()` 函数**

从 `frontend/src/api/suggestion.ts:93-102` 完全删除：

```ts
export async function pushItems(
  suggestionId: number,
  itemIds: number[]
): Promise<{ task_id: number; existing: boolean }> {
  const { data } = await client.post<{ task_id: number; existing: boolean }>(
    `/api/suggestions/${suggestionId}/push`,
    { item_ids: itemIds }
  )
  return data
}
```

- [ ] **Step 4：vue-tsc 校验（预期大量红）**

```bash
cd frontend
pnpm vue-tsc --noEmit 2>&1 | head -80
```

Expected: 多处 `Property 'push_status'/'push_blocker'/...'pushed_items' does not exist` —— 正常，后续任务清理。

- [ ] **Step 5：commit**

```bash
git add frontend/src/api/suggestion.ts
git commit -m "refactor(frontend): 收敛 Suggestion/SuggestionItem 类型并删除 pushItems"
```

---

## Task 3（B2）：清理 `utils/status.ts`

**Files:**
- Modify: `frontend/src/utils/status.ts`

- [ ] **Step 1：修改 `suggestionStatusMap`（L13-19）删除死 entry**

改动 `frontend/src/utils/status.ts:13-19`，替换为：

```ts
const suggestionStatusMap: Record<string, StatusMeta> = {
  draft: { label: '草稿', tagType: 'warning' },
  archived: { label: '已归档', tagType: 'info' },
  error: { label: '异常', tagType: 'danger' },
}
```

- [ ] **Step 2：删除整个 `suggestionPushStatusMap` 常量（L21-26）**

```ts
const suggestionPushStatusMap: Record<string, StatusMeta> = {
  pending: { label: '待推送', tagType: 'warning' },
  pushed: { label: '已推送', tagType: 'success' },
  push_failed: { label: '推送失败', tagType: 'danger' },
  blocked: { label: '待处理', tagType: 'info' },
}
```

- [ ] **Step 3：删除 `getSuggestionPushStatusMeta` 函数（L48-50）**

```ts
export function getSuggestionPushStatusMeta(status: string): StatusMeta {
  return suggestionPushStatusMap[status] || fallbackMeta(status)
}
```

- [ ] **Step 4：vue-tsc 校验**

```bash
cd frontend
pnpm vue-tsc --noEmit 2>&1 | grep -E "(status\.ts|suggestionPushStatusMap|getSuggestionPushStatusMeta)" | head -20
```

Expected: 仍有多处 import 断链（`SuggestionDetailView.vue` / `SuggestionListView.vue` 仍在引用），后续任务清理。

- [ ] **Step 5：commit**

```bash
git add frontend/src/utils/status.ts
git commit -m "refactor(frontend): 清理 utils/status 推送相关死代码"
```

---

## Task 4（B3）：`SuggestionDetailView.vue` 清理 push 引用（暂不加新功能）

**Files:**
- Modify: `frontend/src/views/SuggestionDetailView.vue`

- [ ] **Step 1：L30-35 SkuCard 删除 `:blocker` prop**

改动 `frontend/src/views/SuggestionDetailView.vue:30-35`：

```vue
                <SkuCard
                  :sku="item.commodity_sku"
                  :name="item.commodity_name"
                  :image="item.main_image"
                  :blocker="item.push_blocker"
                />
```

替换为：

```vue
                <SkuCard
                  :sku="item.commodity_sku"
                  :name="item.commodity_name"
                  :image="item.main_image"
                />
```

- [ ] **Step 2：L122-125 描述注释改"导出状态"**

```vue
                      <div class="section-title">状态信息</div>
                      <div class="section-desc">用于快速判断当前条目的推送状态和异常信息。</div>
```

替换为：

```vue
                      <div class="section-title">状态信息</div>
                      <div class="section-desc">用于快速判断当前条目的导出状态。</div>
```

- [ ] **Step 3：L128-147 `status-grid` 整块替换为导出状态展示**

```vue
                  <div class="status-grid">
                    <div class="status-row">
                      <span class="status-label">推送状态</span>
                      <el-tag :type="getSuggestionPushStatusMeta(item.push_status).tagType" size="small">
                        {{ getSuggestionPushStatusMeta(item.push_status).label }}
                      </el-tag>
                    </div>
                    <div class="status-row">
                      <span class="status-label">推送阻塞</span>
                      <span class="status-value">{{ item.push_blocker || '-' }}</span>
                    </div>
                    <div class="status-row">
                      <span class="status-label">采购单号</span>
                      <span class="status-value">{{ item.saihu_po_number || '-' }}</span>
                    </div>
                    <div class="status-row">
                      <span class="status-label">失败原因</span>
                      <span class="status-value">{{ item.push_error || '-' }}</span>
                    </div>
                  </div>
```

替换为：

```vue
                  <div class="status-grid">
                    <div class="status-row">
                      <span class="status-label">导出状态</span>
                      <el-tag :type="item.export_status === 'exported' ? 'success' : 'warning'" size="small">
                        {{ item.export_status === 'exported' ? '已导出' : '未导出' }}
                      </el-tag>
                    </div>
                    <div class="status-row">
                      <span class="status-label">导出时间</span>
                      <span class="status-value">{{ formatDateTime(item.exported_at) }}</span>
                    </div>
                    <div class="status-row">
                      <span class="status-label">所属快照</span>
                      <span class="status-value">{{ item.exported_snapshot_id ? `v${item.exported_snapshot_id}` : '-' }}</span>
                    </div>
                  </div>
```

- [ ] **Step 4：L168 不可编辑 tag 文案改判 `export_status`**

```vue
                    <el-tag v-if="!isEditable(item)" type="info">
                      {{ item.push_status === 'pushed' ? '已推送条目不可编辑' : '已归档建议单不可编辑' }}
                    </el-tag>
```

替换为：

```vue
                    <el-tag v-if="!isEditable(item)" type="info">
                      {{ item.export_status === 'exported' ? '已导出条目不可编辑' : '已归档建议单不可编辑' }}
                    </el-tag>
```

- [ ] **Step 5：L309 `isEditable` 改判**

```ts
function isEditable(item: SuggestionItem): boolean {
  return suggestion.value?.status !== 'archived' && item.push_status !== 'pushed' && auth.hasPermission('restock:operate')
}
```

替换为：

```ts
function isEditable(item: SuggestionItem): boolean {
  return suggestion.value?.status !== 'archived' && item.export_status !== 'exported' && auth.hasPermission('restock:operate')
}
```

- [ ] **Step 6：L204 删除 `getSuggestionPushStatusMeta` 导入**

```ts
import { getSuggestionPushStatusMeta, getSuggestionStatusMeta } from '@/utils/status'
```

替换为：

```ts
import { getSuggestionStatusMeta } from '@/utils/status'
```

- [ ] **Step 7：vue-tsc 校验（该文件应干净）**

```bash
cd frontend
pnpm vue-tsc --noEmit 2>&1 | grep "SuggestionDetailView" | head -20
```

Expected: 该文件 0 报错。

- [ ] **Step 8：commit**

```bash
git add frontend/src/views/SuggestionDetailView.vue
git commit -m "refactor(frontend): SuggestionDetailView 移除 push 引用"
```

---

## Task 5（B4）：`SuggestionListView.vue` 删除全部推送 UI（~110 行）

**Files:**
- Modify: `frontend/src/views/SuggestionListView.vue`

- [ ] **Step 1：L13-16 删除 push TaskProgress 块**

```vue
      <!-- TaskProgress for push task -->
      <TaskProgress v-if="pushTaskId" :task-id="pushTaskId" @terminal="onPushDone" />
```

完全删除（仅保留 L12-13 的 `genTaskId` TaskProgress）。

- [ ] **Step 2：L24-44 工具栏整块重写（删推送筛选 + 推送按钮）**

```vue
      <template v-else>
        <div class="table-toolbar">
          <div class="toolbar-filters">
            <el-input v-model="searchSku" placeholder="搜索 SKU" clearable style="width: 220px" />
            <el-select v-model="filterPushStatus" placeholder="推送状态" clearable style="width: 140px">
              <el-option label="待推送" value="pending" />
              <el-option label="待处理" value="blocked" />
              <el-option label="已推送" value="pushed" />
              <el-option label="推送失败" value="push_failed" />
            </el-select>
          </div>
          <el-button
            v-if="auth.hasPermission('restock:operate')"
            type="primary"
            :loading="pushing"
            :disabled="selectedIds.length === 0"
            @click="handlePush"
          >
            推送（{{ selectedIds.length }}）
          </el-button>
        </div>
```

替换为：

```vue
      <template v-else>
        <div class="table-toolbar">
          <div class="toolbar-filters">
            <el-input v-model="searchSku" placeholder="搜索 SKU" clearable style="width: 220px" />
          </div>
        </div>
```

- [ ] **Step 3：L45-55 表格头部删除 selection + 多选回调**

```vue
        <el-table
          ref="tableRef"
          v-loading="loading"
          :data="pagedItems"
          row-key="id"
          :row-class-name="rowClass"
          @selection-change="handleSelection"
          @select-all="handleSelectAll"
          @sort-change="handleSortChange"
        >
          <el-table-column type="selection" width="48" :selectable="canSelect" />
```

替换为：

```vue
        <el-table
          ref="tableRef"
          v-loading="loading"
          :data="pagedItems"
          :row-class-name="rowClass"
          @sort-change="handleSortChange"
        >
```

- [ ] **Step 4：L88-94 删除"推送状态"列**

```vue
          <el-table-column label="推送状态" prop="push_status" width="120" sortable="custom">
            <template #default="{ row }">
              <el-tag :type="getSuggestionPushStatusMeta(row.push_status).tagType">
                {{ getSuggestionPushStatusMeta(row.push_status).label }}
              </el-tag>
            </template>
          </el-table-column>
```

完全删除。

- [ ] **Step 5：L115 import 语句清理 `pushItems`**

```ts
import { getCurrentSuggestion, pushItems, type SuggestionDetail, type SuggestionItem } from '@/api/suggestion'
```

替换为：

```ts
import { getCurrentSuggestion, type SuggestionDetail, type SuggestionItem } from '@/api/suggestion'
```

- [ ] **Step 6：L121 import 语句清理 `getSuggestionPushStatusMeta`**

```ts
import { getSuggestionPushStatusMeta, getSuggestionStatusMeta } from '@/utils/status'
```

替换为：

```ts
import { getSuggestionStatusMeta } from '@/utils/status'
```

- [ ] **Step 7：L122-128 import 清理 `compareNumber`（若仅被 push_status 排序用）**

先确认是否还有其他使用。用 grep：

```bash
cd frontend
grep -n "compareNumber" src/views/SuggestionListView.vue
```

Expected: L124 import + L231 在 total_qty 排序里使用 —— total_qty 保留，故 `compareNumber` 保留不删。

- [ ] **Step 8：L130 删除 TableInstance import（若未被其他保留代码引用）**

```bash
grep -n "TableInstance\|tableRef" src/views/SuggestionListView.vue
```

Expected: 仅 L130 + L137 引用。两处删除：

L130：
```ts
import type { TableInstance } from 'element-plus'
```
删除。

L137：
```ts
const tableRef = ref<TableInstance>()
```
删除。

- [ ] **Step 9：L139-157 状态变量 + PUSH_STATUS_SORT_ORDER 删除**

```ts
const selectedIds = ref<number[]>([])
const suppressSelectionSync = ref(false)
const searchSku = ref('')
const filterPushStatus = ref('')
const pushing = ref(false)
const generating = ref(false)
const pushTaskId = ref<number | null>(null)
const genTaskId = ref<number | null>(null)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const sortState = ref<SortState>({})

const PUSH_STATUS_SORT_ORDER: Record<SuggestionItem['push_status'], number> = {
  pending: 0,
  blocked: 1,
  push_failed: 2,
  pushed: 3,
}
```

替换为：

```ts
const searchSku = ref('')
const generating = ref(false)
const genTaskId = ref<number | null>(null)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const sortState = ref<SortState>({})
```

- [ ] **Step 10：`loadCurrent` 里的 `selectedIds` 清理**

L163-179 原代码：
```ts
async function loadCurrent(): Promise<void> {
  loading.value = true
  try {
    suggestion.value = await getCurrentSuggestion()
    selectedIds.value = []
  } catch (err: unknown) {
    const e = err as { response?: { status?: number } }
    if (e.response?.status === 404) {
      suggestion.value = null
      selectedIds.value = []
    } else {
      ElMessage.error(getActionErrorMessage(err, '加载当前建议失败'))
    }
  } finally {
    loading.value = false
  }
}
```

替换为：

```ts
async function loadCurrent(): Promise<void> {
  loading.value = true
  try {
    suggestion.value = await getCurrentSuggestion()
  } catch (err: unknown) {
    const e = err as { response?: { status?: number } }
    if (e.response?.status === 404) {
      suggestion.value = null
    } else {
      ElMessage.error(getActionErrorMessage(err, '加载当前建议失败'))
    }
  } finally {
    loading.value = false
  }
}
```

- [ ] **Step 11：`filteredItems` 删除 `filterPushStatus` 分支**

L208-219 原代码：
```ts
const filteredItems = computed(() => {
  if (!suggestion.value) return []
  let items = suggestion.value.items
  if (searchSku.value) {
    const q = searchSku.value.toLowerCase()
    items = items.filter((it) => it.commodity_sku.toLowerCase().includes(q))
  }
  if (filterPushStatus.value) {
    items = items.filter((it) => it.push_status === filterPushStatus.value)
  }
  return items
})
```

替换为：

```ts
const filteredItems = computed(() => {
  if (!suggestion.value) return []
  let items = suggestion.value.items
  if (searchSku.value) {
    const q = searchSku.value.toLowerCase()
    items = items.filter((it) => it.commodity_sku.toLowerCase().includes(q))
  }
  return items
})
```

- [ ] **Step 12：`sortedItems` 删除 push_status 字段排序**

L226-237 原代码：
```ts
const sortedItems = computed(() =>
  applyLocalSort(
    filteredItems.value,
    sortState.value,
    {
      total_qty: (left, right) => compareNumber(left.total_qty, right.total_qty),
      push_status: (left, right) =>
        compareNumber(PUSH_STATUS_SORT_ORDER[left.push_status], PUSH_STATUS_SORT_ORDER[right.push_status]),
    },
    defaultSuggestionComparator,
  ),
)
```

替换为：

```ts
const sortedItems = computed(() =>
  applyLocalSort(
    filteredItems.value,
    sortState.value,
    {
      total_qty: (left, right) => compareNumber(left.total_qty, right.total_qty),
    },
    defaultSuggestionComparator,
  ),
)
```

- [ ] **Step 13：watch 块简化（原两处都操作 selectedIds + 表格）**

L244-253 原代码：
```ts
watch([searchSku, filterPushStatus, pageSize], () => {
  page.value = 1
  selectedIds.value = []
  nextTick(() => tableRef.value?.clearSelection())
})

// Restore checkbox state when changing pages
watch(page, () => {
  nextTick(() => syncTableSelection())
})
```

替换为：

```ts
watch([searchSku, pageSize], () => {
  page.value = 1
})
```

- [ ] **Step 14：删除 handleSelection / handleSelectAll / syncTableSelection / canSelect**

L260-305 整块删除：

```ts
function canSelect(row: SuggestionItem): boolean {
  return !row.push_blocker && row.push_status !== 'pushed' && row.push_status !== 'blocked'
}

function handleSelection(rows: SuggestionItem[]): void {
  ...（含 suppressSelectionSync / selectedIds 逻辑）
}

function handleSelectAll(currentPageSelection: SuggestionItem[]): void {
  ...
}

function syncTableSelection(): void {
  ...
}
```

全部删除（保留 `handleSortChange`、`rowClass` 等）。

- [ ] **Step 15：`handleSortChange` 删除 selection 相关**

L307-313 原代码：
```ts
function handleSortChange({ prop, order }: SortChangeEvent): void {
  const normalizedOrder = normalizeSortOrder(order)
  sortState.value = normalizedOrder && prop ? { prop, order: normalizedOrder } : {}
  page.value = 1
  selectedIds.value = []
  nextTick(() => tableRef.value?.clearSelection())
}
```

替换为：

```ts
function handleSortChange({ prop, order }: SortChangeEvent): void {
  const normalizedOrder = normalizeSortOrder(order)
  sortState.value = normalizedOrder && prop ? { prop, order: normalizedOrder } : {}
  page.value = 1
}
```

- [ ] **Step 16：删除 `handlePush` / `onPushDone`**

L315-356 整块删除：

```ts
async function handlePush(): Promise<void> { ... }
async function onPushDone(task: TaskRun): Promise<void> { ... }
```

- [ ] **Step 17：清理 nextTick / TaskRun 未使用 import**

```bash
grep -n "nextTick\|TaskRun\|TaskProgress" src/views/SuggestionListView.vue
```

确认 `TaskProgress` 仍被 genTaskId 用、`TaskRun` 仍被 `onGenDone(task: TaskRun)` 用；`nextTick` 应已无引用，删除 L132 的 import：

```ts
import { computed, nextTick, onMounted, ref, watch } from 'vue'
```

替换为：

```ts
import { computed, onMounted, ref, watch } from 'vue'
```

- [ ] **Step 18：ElMessageBox 未使用删除**

```bash
grep -n "ElMessageBox" src/views/SuggestionListView.vue
```

应当 0 命中（原仅 `handlePush` 用）。清理 L131 import：

```ts
import { ElMessage, ElMessageBox } from 'element-plus'
```

替换为：

```ts
import { ElMessage } from 'element-plus'
```

- [ ] **Step 19：vue-tsc 校验**

```bash
cd frontend
pnpm vue-tsc --noEmit 2>&1 | grep "SuggestionListView" | head -20
```

Expected: 该文件 0 报错。

- [ ] **Step 20：commit**

```bash
git add frontend/src/views/SuggestionListView.vue
git commit -m "refactor(frontend): SuggestionListView 删除推送 UI"
```

---

## Task 6（B5）：`HistoryView.vue` 替换 push 列、重写 `canDelete`

**Files:**
- Modify: `frontend/src/views/HistoryView.vue`

- [ ] **Step 1：L22-28 状态筛选下拉收敛到 3 值**

```vue
      <el-select v-model="status" placeholder="状态" clearable style="width: 140px" @change="() => reload()">
        <el-option label="草稿" value="draft" />
        <el-option label="部分推送" value="partial" />
        <el-option label="已推送" value="pushed" />
        <el-option label="已归档" value="archived" />
        <el-option label="异常" value="error" />
      </el-select>
```

替换为：

```vue
      <el-select v-model="status" placeholder="状态" clearable style="width: 140px" @change="() => reload()">
        <el-option label="草稿" value="draft" />
        <el-option label="已归档" value="archived" />
        <el-option label="异常" value="error" />
      </el-select>
```

- [ ] **Step 2：L50-57 删除"已推送"/"失败数"/"推送成功率"列，替换为"快照数"**

原：
```vue
      <el-table-column label="条目数" prop="total_items" width="100" align="right" sortable="custom" show-overflow-tooltip />
      <el-table-column label="已推送" prop="pushed_items" width="100" align="right" sortable="custom" show-overflow-tooltip />
      <el-table-column label="失败数" prop="failed_items" width="100" align="right" sortable="custom" show-overflow-tooltip />
      <el-table-column label="推送成功率" prop="success_rate" width="120" align="right" sortable="custom">
        <template #default="{ row }">
          {{ successRate(row) }}
        </template>
      </el-table-column>
```

替换为：

```vue
      <el-table-column label="条目数" prop="total_items" width="100" align="right" sortable="custom" show-overflow-tooltip />
      <el-table-column label="快照数" prop="snapshot_count" width="100" align="right" sortable="custom" show-overflow-tooltip />
      <el-table-column label="导出状态" width="110" align="center">
        <template #default="{ row }">
          <el-tag :type="row.snapshot_count > 0 ? 'success' : 'info'" size="small">
            {{ row.snapshot_count > 0 ? '已导出' : '未导出' }}
          </el-tag>
        </template>
      </el-table-column>
```

- [ ] **Step 3：删除 `successRate` 函数（L144-148）**

```ts
function successRate(row: Suggestion): string {
  if (!row.total_items) return '-'
  const rate = (row.pushed_items / row.total_items) * 100
  return `${rate.toFixed(0)}%`
}
```

完全删除。

- [ ] **Step 4：重写 `canDelete` 语义（L160-162）**

```ts
function canDelete(row: Suggestion): boolean {
  return row.status !== 'pushed'
}
```

替换为：

```ts
function canDelete(row: Suggestion): boolean {
  return row.snapshot_count === 0
}
```

> 业务含义：凡有快照的建议单不可删（审计保留）。`snapshot_count` 已在 `api/suggestion.ts` Task 2 中加入。

- [ ] **Step 5：vue-tsc 校验**

```bash
cd frontend
pnpm vue-tsc --noEmit 2>&1 | grep "HistoryView" | head -20
```

Expected: 0 报错。

- [ ] **Step 6：commit**

```bash
git add frontend/src/views/HistoryView.vue
git commit -m "refactor(frontend): HistoryView 替换 push 列为 export_status + snapshot_count，canDelete 改用 snapshot_count === 0"
```

---

## Task 7（B6）：测试清理（保持 CI `npm run test:coverage` 全绿）

**Files:**
- Modify: `frontend/src/utils/status.test.ts`
- Modify: `frontend/src/views/__tests__/SuggestionDetailView.test.ts`
- Modify: `frontend/src/views/__tests__/SuggestionListView.test.ts`
- Modify: `frontend/src/views/__tests__/HistoryView.test.ts`

- [ ] **Step 1：运行 CI 测试命令初次诊断**

```bash
cd frontend
npm run test:coverage 2>&1 | tail -60
```

Expected: 多处因类型收敛/死字段被删而挂掉 —— 记录失败文件清单。

- [ ] **Step 2：修 `frontend/src/utils/status.test.ts`**

查看：
```bash
cat src/utils/status.test.ts
```

删除：
- 所有涉及 `getSuggestionPushStatusMeta` 的 `describe`/`it` 块（预计 ~3 处）
- `suggestionStatusMap` 对 `partial` / `pushed` 的断言（如 "partial → 部分推送"）

保留：
- `getSuggestionStatusMeta` 对 `draft` / `archived` / `error` 的断言
- 其他 map 测试（`getSyncStatusMeta` / `getShopStatusMeta` 等）

- [ ] **Step 3：修 `SuggestionDetailView.test.ts`**

```bash
grep -nE "push_status|push_blocker|push_error|saihu_po_number|'pushed'|pushItems" src/views/__tests__/SuggestionDetailView.test.ts
```

处理原则：
- mock 数据中 `push_status: 'pushed'` 改为 `export_status: 'exported'`
- `push_blocker: '...'` 整行删除
- `push_error` / `saihu_po_number` 整行删除
- 引用 `pushItems` 的 `describe`/`it` 整块删除
- 断言"已推送条目不可编辑" 改为"已导出条目不可编辑"

- [ ] **Step 4：修 `SuggestionListView.test.ts`**

```bash
grep -nE "push_status|push_blocker|pushItems|getSuggestionPushStatusMeta|filterPushStatus|handlePush|selectedIds" src/views/__tests__/SuggestionListView.test.ts
```

处理原则：
- 删除所有推送按钮/筛选/多选相关 `describe`/`it`（大部分）
- 保留：列表渲染、SKU 搜索、分页、排序（按 total_qty）测试
- mock 数据里 `push_status` / `push_blocker` 字段删除
- mock 对象需补 `export_status: 'pending'`（TS 严格模式必需）

- [ ] **Step 5：修 `HistoryView.test.ts`**

```bash
grep -nE "canDelete|'pushed'|status: 'pushed'|pushed_items|failed_items|successRate" src/views/__tests__/HistoryView.test.ts
```

处理原则：
- mock 对象添加 `snapshot_count: 0`（删除项）或 `snapshot_count: 2`（保留项）
- `canDelete({status:'pushed'})` 的 case 删除或改写成 `canDelete({snapshot_count: 2}) === false`
- `pushed_items` / `failed_items` / `successRate` 相关 case 删除
- 状态筛选 dropdown 如果有测试，更新到新 3 值

- [ ] **Step 6：跑完整测试套件**

```bash
cd frontend
npm run test:coverage 2>&1 | tail -40
```

Expected: 全绿，0 failed。

- [ ] **Step 7：vue-tsc 校验（测试文件的 TS 也要过）**

```bash
cd frontend
pnpm vue-tsc --noEmit
```

Expected: 0 报错。

- [ ] **Step 8：commit**

```bash
git add frontend/src/utils/status.test.ts \
        frontend/src/views/__tests__/SuggestionDetailView.test.ts \
        frontend/src/views/__tests__/SuggestionListView.test.ts \
        frontend/src/views/__tests__/HistoryView.test.ts
git commit -m "test(frontend): 删除推送相关测试块"
```

---

## Task 8（B7）：新建 `api/snapshot.ts` + `utils/download.ts`

**Files:**
- Create: `frontend/src/api/snapshot.ts`
- Create: `frontend/src/utils/download.ts`

- [ ] **Step 1：创建 `frontend/src/api/snapshot.ts`**

```ts
// 快照 API 客户端
import client from './client'

export interface SnapshotOut {
  id: number
  suggestion_id: number
  version: number
  note: string | null
  exported_by: number | null
  exported_by_name: string | null
  exported_at: string
  item_count: number
  generation_status: 'generating' | 'ready' | 'failed'
  file_size_bytes: number | null
  download_count: number
}

export interface SnapshotItemOut {
  id: number
  commodity_sku: string
  commodity_name: string | null
  main_image_url: string | null
  total_qty: number
  country_breakdown: Record<string, unknown>
  warehouse_breakdown: Record<string, unknown>
  urgent: boolean
  velocity_snapshot: Record<string, unknown> | null
  sale_days_snapshot: Record<string, unknown> | null
}

export interface SnapshotDetailOut extends SnapshotOut {
  items: SnapshotItemOut[]
  global_config_snapshot: Record<string, unknown>
}

export async function createSnapshot(
  suggestionId: number,
  itemIds: number[],
  note?: string,
): Promise<SnapshotOut> {
  const { data } = await client.post<SnapshotOut>(
    `/api/suggestions/${suggestionId}/snapshots`,
    { item_ids: itemIds, note },
  )
  return data
}

export async function listSnapshots(suggestionId: number): Promise<SnapshotOut[]> {
  // 后端按 version asc 返回，前端 reverse 让最新版本在表格顶部
  const { data } = await client.get<SnapshotOut[]>(
    `/api/suggestions/${suggestionId}/snapshots`,
  )
  return [...data].reverse()
}

export async function getSnapshot(snapshotId: number): Promise<SnapshotDetailOut> {
  const { data } = await client.get<SnapshotDetailOut>(`/api/snapshots/${snapshotId}`)
  return data
}

export async function downloadSnapshotBlob(
  snapshotId: number,
): Promise<{ blob: Blob; filename: string }> {
  const resp = await client.get(`/api/snapshots/${snapshotId}/download`, {
    responseType: 'blob',
  })
  const disposition = (resp.headers['content-disposition'] as string | undefined) || ''
  const match = disposition.match(/filename\*?=(?:UTF-8'')?["]?([^;"\r\n]+)["]?/i)
  const filename = match ? decodeURIComponent(match[1]) : `snapshot-${snapshotId}.xlsx`
  return { blob: resp.data as Blob, filename }
}
```

- [ ] **Step 2：创建 `frontend/src/utils/download.ts`**

```ts
// 浏览器 blob 下载：在用户点击 activation 上下文内触发
export function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
```

- [ ] **Step 3：vue-tsc 校验**

```bash
cd frontend
pnpm vue-tsc --noEmit
```

Expected: 0 报错。

- [ ] **Step 4：commit**

```bash
git add frontend/src/api/snapshot.ts frontend/src/utils/download.ts
git commit -m "feat(frontend): 新增 snapshot API 客户端与下载工具"
```

---

## Task 9（B8）：`SuggestionDetailView.vue` 加导出按钮 + 快照历史区

**Files:**
- Modify: `frontend/src/views/SuggestionDetailView.vue`

- [ ] **Step 1：顶部 header actions 加导出按钮**

找到 L19-22：

```vue
          <div class="actions">
            <el-button @click="goBack">返回</el-button>
          </div>
```

替换为：

```vue
          <div class="actions">
            <el-button
              v-if="auth.hasPermission('restock:export') && suggestion.status === 'draft'"
              type="primary"
              :disabled="!toggleEnabled || exportable.length === 0"
              :loading="exporting"
              @click="handleExport"
            >
              {{ exportButtonText }}
            </el-button>
            <el-button @click="goBack">返回</el-button>
          </div>
```

- [ ] **Step 2：底部加 `PageSectionCard` 快照历史**

在 L178 `</el-card>` 之后、L180 `<el-empty v-else-if="notFound"` 之前，插入：

```vue
    <PageSectionCard v-if="suggestion" title="历史快照" class="snapshot-section">
      <el-table v-loading="loadingSnapshots" :data="snapshots" empty-text="暂无导出记录">
        <el-table-column label="版本" width="96">
          <template #default="{ row }">v{{ row.version }}</template>
        </el-table-column>
        <el-table-column label="导出人" prop="exported_by_name" min-width="140">
          <template #default="{ row }">{{ row.exported_by_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="导出时间" min-width="180">
          <template #default="{ row }">{{ formatDateTime(row.exported_at) }}</template>
        </el-table-column>
        <el-table-column label="商品数" prop="item_count" width="100" align="right" />
        <el-table-column label="下载次数" prop="download_count" width="100" align="right" />
        <el-table-column label="操作" width="120" align="center">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              :disabled="row.generation_status !== 'ready'"
              :title="row.generation_status === 'failed' ? '生成失败' : ''"
              @click="downloadSnapshot(row.id)"
            >
              下载
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </PageSectionCard>
```

- [ ] **Step 3：script setup 部分加 import**

找到 L192-204 import 块，调整为：

```ts
import {
  getSuggestion,
  patchSuggestionItem,
  type AllocationExplanation,
  type SuggestionDetail,
  type SuggestionItem,
} from '@/api/suggestion'
import {
  createSnapshot,
  downloadSnapshotBlob,
  listSnapshots,
  type SnapshotOut,
} from '@/api/snapshot'
import { getGenerationToggle } from '@/api/config'
import PageSectionCard from '@/components/PageSectionCard.vue'
import SkuCard from '@/components/SkuCard.vue'
import { useAuthStore } from '@/stores/auth'
import { getActionErrorMessage } from '@/utils/apiError'
import { triggerBlobDownload } from '@/utils/download'
import { allocationModeLabel, allocationModeTagType, allocationSummary } from '@/utils/allocation'
import { getSuggestionStatusMeta } from '@/utils/status'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
```

> `getGenerationToggle` 在 Task 10 Step 1 会追加到 `api/config.ts`。此处先 import 等 Task 10 落地后统一过编译。

- [ ] **Step 4：加新 state（插入在 `loadError` 后 L232）**

```ts
const snapshots = ref<SnapshotOut[]>([])
const loadingSnapshots = ref(false)
const toggleEnabled = ref(true)
const exporting = ref(false)

const exportable = computed(() =>
  suggestion.value?.items.filter((it) => it.export_status !== 'exported') ?? [],
)

const exportButtonText = computed(() => {
  if (!toggleEnabled.value) return '生成开关已关闭'
  if (exportable.value.length === 0) return '无可导出条目'
  return '导出 Excel'
})
```

- [ ] **Step 5：加 `loadSnapshots` / `loadToggle` 函数**

在 `load()` 函数后插入：

```ts
async function loadSnapshots(): Promise<void> {
  if (!suggestion.value) return
  loadingSnapshots.value = true
  try {
    snapshots.value = await listSnapshots(suggestion.value.id)
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '加载快照历史失败'))
  } finally {
    loadingSnapshots.value = false
  }
}

async function loadToggle(): Promise<void> {
  try {
    const toggle = await getGenerationToggle()
    toggleEnabled.value = toggle.enabled
  } catch {
    // 业务人员已在 B0 迁移中获得 config:view；若仍失败（老用户未刷新），
    // 保留默认 true 不影响导出按钮可用性；导出接口后端不 gate 开关。
    toggleEnabled.value = true
  }
}
```

- [ ] **Step 6：加 `handleExport` / `downloadSnapshot`**

继续在后面追加：

```ts
async function handleExport(): Promise<void> {
  if (!suggestion.value || exportable.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      '确认导出？导出后当前建议单的商品将无法重复导出，生成开关将自动关闭。',
      '确认导出',
      { type: 'warning', confirmButtonText: '确认导出', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  exporting.value = true
  try {
    const itemIds = exportable.value.map((it) => it.id)
    const snapshot = await createSnapshot(suggestion.value.id, itemIds)
    const { blob, filename } = await downloadSnapshotBlob(snapshot.id)
    triggerBlobDownload(blob, filename)
    ElMessage.success('导出成功，生成开关已关闭')
    await Promise.all([load(), loadSnapshots(), loadToggle()])
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '导出失败'))
  } finally {
    exporting.value = false
  }
}

async function downloadSnapshot(snapshotId: number): Promise<void> {
  try {
    const { blob, filename } = await downloadSnapshotBlob(snapshotId)
    triggerBlobDownload(blob, filename)
    await loadSnapshots()
  } catch (error) {
    ElMessage.error(getActionErrorMessage(error, '下载失败'))
  }
}
```

- [ ] **Step 7：`load()` 成功后触发副任务刷新**

原 L243-272 `load()` 函数尾部（`try` 块内成功后）追加：

在 `await syncRouteItemFocus(data)` 下一行插入：

```ts
    await Promise.all([loadSnapshots(), loadToggle()])
```

最终样子：
```ts
  try {
    const data = await getSuggestion(id)
    suggestion.value = data
    syncEditingState(data)
    await syncRouteItemFocus(data)
    await Promise.all([loadSnapshots(), loadToggle()])
  } catch (error) {
    ...
```

- [ ] **Step 8：样式追加**

在 `<style lang="scss" scoped>` 内现有规则后追加：

```scss
.snapshot-section {
  margin-top: $space-4;
}
```

- [ ] **Step 9：vue-tsc 校验**

```bash
cd frontend
pnpm vue-tsc --noEmit 2>&1 | grep "SuggestionDetailView\|api/config\|api/snapshot" | head -20
```

Expected: `getGenerationToggle` 可能报"not exported"—— Task 10 会补。其他应干净。

- [ ] **Step 10：不 commit，等 Task 10 统一过 tsc 后提交**

> 该任务产物与 Task 10 耦合：`getGenerationToggle` 会在 Task 10 Step 1 加入 `api/config.ts`。先继续 Task 10。

---

## Task 10（B9）：`api/config.ts` 追加开关 API + `GlobalConfigView.vue` 加生成开关卡片

**Files:**
- Modify: `frontend/src/api/config.ts`
- Modify: `frontend/src/views/GlobalConfigView.vue`

- [ ] **Step 1：在 `frontend/src/api/config.ts` 顶部 `GlobalConfig` 后追加 GenerationToggle 类型与函数**

在 `frontend/src/api/config.ts:26` 行（现 `patchGlobalConfig` 的闭合 `}`）后插入：

```ts

// ========== Generation Toggle ==========
export interface GenerationToggle {
  enabled: boolean
  updated_by: number | null
  updated_by_name: string | null
  updated_at: string | null
}

export async function getGenerationToggle(): Promise<GenerationToggle> {
  const { data } = await client.get<GenerationToggle>('/api/config/generation-toggle')
  return data
}

export async function patchGenerationToggle(enabled: boolean): Promise<GenerationToggle> {
  const { data } = await client.patch<GenerationToggle>(
    '/api/config/generation-toggle',
    { enabled },
  )
  return data
}
```

- [ ] **Step 2：`GlobalConfigView.vue` 模板 - 顶部加生成开关 `PageSectionCard`**

在 `<template>` 内，`<PageSectionCard v-if="form" title="全局参数">` 标签 **前** 插入：

```vue
  <PageSectionCard v-if="toggle" title="补货建议生成开关" class="toggle-section">
    <div class="toggle-row">
      <el-switch
        v-model="toggleValue"
        :loading="togglePatching"
        :disabled="!auth.hasPermission('restock:new_cycle')"
        :active-text="toggleValue ? '已开启' : '已关闭'"
        @change="onToggleChange"
      />
      <div class="toggle-meta">
        <div>最近操作人：{{ toggle.updated_by_name ?? '—' }}</div>
        <div>最近操作时间：{{ toggle.updated_at ? formatDateTime(toggle.updated_at) : '—' }}</div>
      </div>
    </div>
    <div class="toggle-hint">
      <span v-if="!auth.hasPermission('restock:new_cycle')">你没有翻开关的权限（需要 <code>restock:new_cycle</code>）。</span>
      <span v-else>打开开关会归档所有草稿建议单。</span>
    </div>
  </PageSectionCard>
```

- [ ] **Step 3：script setup 加 import**

修改 `frontend/src/views/GlobalConfigView.vue:99-105`：

```ts
import { getGlobalConfig, patchGlobalConfig, type GlobalConfig } from '@/api/config'
import PageSectionCard from '@/components/PageSectionCard.vue'
import { getActionErrorMessage } from '@/utils/apiError'
import { COUNTRY_OPTIONS } from '@/utils/countries'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'
```

替换为：

```ts
import {
  getGenerationToggle,
  getGlobalConfig,
  patchGenerationToggle,
  patchGlobalConfig,
  type GenerationToggle,
  type GlobalConfig,
} from '@/api/config'
import PageSectionCard from '@/components/PageSectionCard.vue'
import { getActionErrorMessage } from '@/utils/apiError'
import { COUNTRY_OPTIONS } from '@/utils/countries'
import { useAuthStore } from '@/stores/auth'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'
```

- [ ] **Step 4：加 state + formatDateTime**

在 `const saving = ref(false)` 后面（约 L110）插入：

```ts
const toggle = ref<GenerationToggle | null>(null)
const toggleValue = ref(false)
const togglePatching = ref(false)

function formatDateTime(value: string | null | undefined): string {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : '—'
}
```

- [ ] **Step 5：`onMounted` 内追加加载开关状态**

`onMounted(async () => {` 的 try 块末尾追加：

```ts
    const t = await getGenerationToggle()
    toggle.value = t
    toggleValue.value = t.enabled
```

完整：
```ts
onMounted(async () => {
  try {
    form.value = await getGlobalConfig()
    snapshotCalcParams()
    initCronState()
    const t = await getGenerationToggle()
    toggle.value = t
    toggleValue.value = t.enabled
  } catch (e) {
    ElMessage.error(getActionErrorMessage(e, '加载全局配置'))
  }
})
```

- [ ] **Step 6：加 `onToggleChange` 处理函数**

在 `save()` 函数前插入：

```ts
async function onToggleChange(next: boolean | string | number): Promise<void> {
  const target = Boolean(next)
  const prev = !target  // Element Plus 已把值改为 target；prev 是翻之前的值
  if (target) {
    try {
      await ElMessageBox.confirm(
        '打开开关将归档所有草稿建议单，确认继续？',
        '打开生成开关',
        { type: 'warning', confirmButtonText: '确认打开', cancelButtonText: '取消' },
      )
    } catch {
      // 用户取消：rollback switch
      toggleValue.value = prev
      return
    }
  }
  togglePatching.value = true
  try {
    const updated = await patchGenerationToggle(target)
    toggle.value = updated
    toggleValue.value = updated.enabled
    ElMessage.success(target ? '开关已打开，已归档所有草稿' : '开关已关闭')
  } catch (err) {
    toggleValue.value = prev
    ElMessage.error(getActionErrorMessage(err, '开关切换失败'))
  } finally {
    togglePatching.value = false
  }
}
```

- [ ] **Step 7：样式补充**

在 `<style lang="scss" scoped>` 末尾追加：

```scss
.toggle-section {
  margin-bottom: $space-4;
}

.toggle-row {
  display: flex;
  align-items: center;
  gap: $space-4;
}

.toggle-meta {
  display: flex;
  flex-direction: column;
  gap: $space-1;
  color: $color-text-secondary;
  font-size: $font-size-sm;
}

.toggle-hint {
  margin-top: $space-3;
  color: $color-text-secondary;
  font-size: $font-size-xs;
}
```

- [ ] **Step 8：vue-tsc + build 全量过**

```bash
cd frontend
pnpm vue-tsc --noEmit
pnpm build
```

Expected: 0 报错，build 成功。Task 9（B8）残留的 `getGenerationToggle not exported` 也会在此消除。

- [ ] **Step 9：commit（把 Task 9 和 Task 10 合并提交）**

```bash
git add frontend/src/api/config.ts \
        frontend/src/views/GlobalConfigView.vue \
        frontend/src/views/SuggestionDetailView.vue
git commit -m "feat(frontend): 建议单详情页新增导出按钮与历史快照区；全局配置页新增生成开关卡片"
```

> 合并原因：Task 9 依赖 Task 10 的 `getGenerationToggle` 通过 tsc，两个变更天然耦合；按 CLAUDE.md "最小化 + 可回滚" 原则，打包成一个 feat commit。

---

## Task 11（B10）：`SuggestionListView.vue` 加开关只读 tag

**Files:**
- Modify: `frontend/src/views/SuggestionListView.vue`

- [ ] **Step 1：template 顶部 actions 加 tag**

找到 L3-10：

```vue
    <PageSectionCard title="补货发起">
      <template #actions>
        <el-tag v-if="suggestion" :type="statusMeta.tagType" size="small">
          {{ statusMeta.label }} · {{ suggestion.total_items }} 条
        </el-tag>
        <el-button @click="loadCurrent">刷新</el-button>
        <el-button v-if="auth.hasPermission('restock:operate')" type="primary" :loading="generating" @click="triggerEngine">生成补货建议</el-button>
      </template>
```

替换为：

```vue
    <PageSectionCard title="补货发起">
      <template #actions>
        <el-tag v-if="suggestion" :type="statusMeta.tagType" size="small">
          {{ statusMeta.label }} · {{ suggestion.total_items }} 条
        </el-tag>
        <el-tag
          v-if="toggle"
          :type="toggle.enabled ? 'success' : 'info'"
          size="small"
          :title="toggleTitle"
        >
          生成开关：{{ toggle.enabled ? '开启' : '已关闭' }}
        </el-tag>
        <el-button @click="loadCurrent">刷新</el-button>
        <el-button v-if="auth.hasPermission('restock:operate')" type="primary" :loading="generating" @click="triggerEngine">生成补货建议</el-button>
      </template>
```

- [ ] **Step 2：script setup 加 import + state**

在 L114 `import type { TaskRun } from '@/api/task'` 后追加：

```ts
import { getGenerationToggle, type GenerationToggle } from '@/api/config'
```

加 state（紧跟现有 state 之后）：

```ts
const toggle = ref<GenerationToggle | null>(null)

const toggleTitle = computed(() => {
  if (!toggle.value) return ''
  const by = toggle.value.updated_by_name ?? '—'
  const at = toggle.value.updated_at ?? '—'
  return `最近操作：${by} @ ${at}`
})
```

- [ ] **Step 3：加 `loadToggle` + `onActivated` 双钩子**

调整 `import` 里的 vue hooks：

```ts
import { computed, onMounted, ref, watch } from 'vue'
```

替换为：

```ts
import { computed, onActivated, onMounted, ref, watch } from 'vue'
```

在 `onMounted(loadCurrent)` 之前加：

```ts
async function loadToggle(): Promise<void> {
  try {
    toggle.value = await getGenerationToggle()
  } catch {
    // 无权限或后端异常时保持上一次状态，不阻断主流程
  }
}

onMounted(() => {
  void loadCurrent()
  void loadToggle()
})

onActivated(() => {
  void loadToggle()
})
```

原来的 `onMounted(loadCurrent)` 一行删除。

- [ ] **Step 4：vue-tsc + build 校验**

```bash
cd frontend
pnpm vue-tsc --noEmit
pnpm build
```

Expected: 0 报错，build 成功。

- [ ] **Step 5：commit**

```bash
git add frontend/src/views/SuggestionListView.vue
git commit -m "feat(frontend): 建议单列表页显示生成开关只读状态"
```

---

## Task 12（B11）：文档同步

**Files:**
- Modify: `docs/PROGRESS.md`
- Modify: `docs/Project_Architecture_Blueprint.md`

- [ ] **Step 1：更新 `docs/PROGRESS.md`**

- 顶部"最近更新"改为 `2026-04-19`
- Plan A 条目下新增前端收尾摘要：
  > 前端：新增快照 API 客户端与 blob 下载工具；建议单详情页加导出按钮（一步式 POST+GET blob）与历史快照区；全局配置页加生成开关卡片（即时保存 + 翻 ON 二次确认）；列表页加开关只读 tag；全量清理赛狐推送时代死代码（~110 行 UI + 8 死字段 + `utils/status.ts` map + 4 个测试文件的推送相关 case）；`Suggestion.status` TS 枚举收敛为 `'draft'|'archived'|'error'`；`HistoryView.canDelete` 改用 `snapshot_count === 0`。
  > 后端：alembic 迁移 `20260419_0000_grant_export_and_config_view_to_business_role` 给"业务人员"角色补齐 `restock:export` + `config:view`。

- [ ] **Step 2：更新 `docs/Project_Architecture_Blueprint.md`**

涉及章节：
- RBAC / 角色权限矩阵：给"业务人员"行追加 `restock:export` + `config:view`
- 前端数据模型章节：`Suggestion.status` 枚举更新为 3 值；`SuggestionItem` 删除 push_* 字段描述，新增 `export_status` / `exported_snapshot_id` / `exported_at`
- 前端视图章节：`SuggestionDetailView` 补充"导出 + 历史快照"职责；`GlobalConfigView` 补充"生成开关"卡片；`SuggestionListView` 移除"推送"职责、补充"开关只读状态"；`HistoryView` 更新 `canDelete` 规则描述
- 模块依赖图：`api/snapshot.ts` → `backend/app/api/snapshot.py`；`utils/download.ts`（新节点）

- [ ] **Step 3：运行自检清单**

```bash
cd /e/Ai_project/restock_system
# 后端
docker exec restock-dev-backend pytest tests/unit -q
# 前端
cd frontend && pnpm vue-tsc --noEmit && pnpm build && npm run test:coverage
# 全仓 grep 确认死字段零残留
cd ..
grep -rn "push_status\|push_blocker\|push_error\|push_attempt_count\|pushed_at\|saihu_po_number\|pushItems\|suggestionPushStatusMap\|getSuggestionPushStatusMeta" frontend/src
```

Expected:
- pytest 绿
- vue-tsc 0 错
- build 成功
- test:coverage 绿
- grep 零命中

- [ ] **Step 4：commit**

```bash
git add docs/PROGRESS.md docs/Project_Architecture_Blueprint.md
git commit -m "docs(sync): Plan A 前端收尾同步 PROGRESS/Blueprint"
```

---

## Task 13：手动功能验证（在 dev 容器里跑真实流程）

- [ ] **Step 1：重建镜像并启动**

```bash
cd deploy
docker compose -f docker-compose.dev.yml down
docker compose -f docker-compose.dev.yml build backend worker scheduler frontend
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml ps
```

Expected: 全部 healthy。

- [ ] **Step 2：浏览器验收**

访问 `http://localhost:8088`，使用**业务人员**账号登录，逐项验证：

- [ ] 开关 ON + 有 draft 建议单 → 详情页导出按钮可用 → 点击"确认导出" → 下载 `.xlsx`
- [ ] 导出后开关自动翻 OFF；详情页底部历史快照区多一行 v1
- [ ] 再次点击导出 → 按钮应显示"生成开关已关闭"并禁用
- [ ] 历史快照区"下载"按钮可重复下载；`download_count` +1
- [ ] 切换到全局配置页：看到生成开关卡片，显示最近操作人/时间
- [ ] 业务人员 Switch 应禁用（`restock:new_cycle` 权限没有）
- [ ] 换**超级管理员**登录：
  - Switch 可操作；翻 OFF→ON 弹确认框，确认后归档所有 draft
  - 列表页 actions 栏看到 "生成开关：开启/已关闭" tag
- [ ] **阅读者**角色登录：
  - 详情页无"导出 Excel"按钮
  - 列表页仍可见开关 tag（因 `config:view` 是 `*:view` 类，阅读者已有）
  - 配置页 Switch 禁用
- [ ] HistoryView：含快照的建议单"删除"按钮禁用；不含快照的可删除

- [ ] **Step 3：边界与错误路径**

- [ ] 手动 SQL 删除某 snapshot 的文件路径 `file_path = NULL` → 下载应提示"已过期"（后端 410）
- [ ] 构造一个全部 item 都 `export_status='exported'` 的 draft → 导出按钮自动禁用（文案"无可导出条目"）
- [ ] 网络异常模拟（dev tools offline）→ 开关 PATCH 失败 → Switch rollback 到原值 + Toast 错误
- [ ] 已归档建议单详情页：导出按钮不出现

- [ ] **Step 4：若全部通过，准备 PR**

```bash
git log --oneline master..HEAD
```

Expected: ~12 个 commit 按 Task 顺序。

- [ ] **Step 5：push + 开 PR**

```bash
git push -u origin feature/plan-a-frontend-completion
gh pr create --base master \
  --title "feat: Plan A 前端收尾 —— 导出 + 快照历史 + 生成开关" \
  --body "$(cat <<'EOF'
## Summary
- 前端新增 Excel 导出按钮（一步式：确认 → POST 创建快照 → GET blob 下载 → 开关自动关闭）
- 建议单详情页底部新增历史快照区（版本降序、可重复下载）
- 全局配置页新增"生成开关"卡片（即时保存 + 翻 ON 二次确认 + 失败 rollback）
- 建议单列表页展示开关只读 tag（onMounted/onActivated 双钩子刷新）
- 历史页 `canDelete` 改用 `snapshot_count === 0`，状态列替换为导出状态
- 后端 alembic 迁移：业务人员角色补齐 `restock:export` + `config:view`
- 全量清理赛狐推送时代死代码：~110 行 UI、8 死字段、死函数 `pushItems`、`utils/status.ts` 两张死 map、4 个测试文件的推送相关 case
- `Suggestion.status` TS 枚举收敛为 `'draft'|'archived'|'error'`（与后端 CHECK 约束对齐）

## Test plan
- [x] backend pytest 绿
- [x] frontend vue-tsc 0 错
- [x] frontend `pnpm build` 成功
- [x] frontend `npm run test:coverage` 绿
- [x] alembic upgrade head 幂等通过；业务人员角色权限验证（2 条新 role_permission）
- [x] 浏览器手动流程验证（业务人员 / 超管 / 阅读者 三种角色，见设计稿 §5.2）
EOF
)"
```

Expected: PR 创建成功，返回 URL。CI 三个 job（backend / frontend / docker-build）应绿。

- [ ] **Step 6：CI 绿后合并**

```bash
# 等 CI 绿
gh pr checks --watch
# 切 master + no-ff 合并
git checkout master
git pull
git merge --no-ff feature/plan-a-frontend-completion
git push
```

Expected: master 含 merge commit，12 commit 历史保留，工作树干净。

---

## 回归与回滚

**回归点**：
- Task 1 的 alembic 迁移幂等；下线可 `alembic downgrade -1`
- Task 2-11 的前端变更集中在同一 feature 分支；若 PR 需整体回滚，`git revert -m 1 <merge-commit>`
- Task 7 测试文件回滚：只回 `refactor` 族会留下失败 case，需同批回 `test:` commit

**观察指标**（合并后一周）：
- 生产日志搜索 `restock:export` 权限 403：业务人员是否还有漏配
- 快照 `generation_status = 'failed'` 发生次数（应 0）
- 前端报错监控是否有 `getGenerationToggle is not a function` 之类的运行时错

---

## Self-Review 记录

已核对 `docs/superpowers/specs/2026-04-19-plan-a-frontend-completion-design.md` §1-§7 全部要求：

| Spec 要求 | 覆盖 Task |
| --- | --- |
| §1.1 Scope：导出 + 快照历史 + 开关 + 清理 + 权限迁移 | Task 1-13 |
| §2 决策 A：单 PR 多 commit | Task 0 分支 + Task 13 PR |
| §2 决策 Q1：列表推送 UI 全清 | Task 5 |
| §2 决策 Q2：HistoryView 替换 export_status + snapshot_count | Task 6 |
| §2 决策 Q3-B：测试删除 push case（CI 走 `npm run test:coverage`） | Task 7 |
| §2 决策 Q4：前端 reverse（api/snapshot.ts 内） | Task 8 Step 1 `listSnapshots` |
| §2 决策 Q5：即时保存 + loading + 二次确认 | Task 10 Step 2-6 |
| §2 决策 Q6-A：Status 收敛 3 值 | Task 2 |
| §2 决策 Q6-丙：`canDelete = snapshot_count === 0` | Task 6 Step 4 |
| §3.0 后端迁移幂等 + 独立版本 + downgrade | Task 1 |
| §3.1 snapshot.ts 默认 import client / main_image_url / reverse | Task 8 |
| §3.1.1 download.ts triggerBlobDownload | Task 8 Step 2 |
| §3.2 导出按钮条件 + 流程 6 步 + 下载弹兜底 | Task 9 Step 1/6 |
| §3.2 历史表 6 列 | Task 9 Step 2 |
| §3.3 开关卡片：即时保存 + loading + rollback + 二次确认 | Task 10 Step 2/6 |
| §3.4 列表页清 UI + 加开关 tag + onActivated | Task 5 + Task 11 |
| §3.5 api/suggestion.ts 类型收敛 + pushItems 删除 | Task 2 |
| §3.6 HistoryView 3 处 push 删 + canDelete 改写 | Task 6 |
| §3.7 utils/status.ts 三项清理 | Task 3 |
| §3.8 4 个测试文件清理 | Task 7 |
| §3.9 status 枚举收敛后处 | Task 4 Step 4/5 + Task 6 + Task 7 |
| §4.1 统一 getActionErrorMessage；409 不特别处理 | Task 9 Step 6 |
| §4.2 下载错误统一 getActionErrorMessage | Task 9 Step 6 |
| §4.3 开关 rollback | Task 10 Step 6 |
| §4.4 exportable 前端过滤 | Task 9 Step 4 computed |
| §4.5 不展示 last_downloaded_at | Task 8 Step 1（字段未加入 SnapshotOut） |
| §4.6 failed 快照下载禁用 + tooltip | Task 9 Step 2 `:disabled` + `:title` |
| §5.1 12-commit 顺序 | Task 1-12 |
| §5.2 验收 + CI 绿 + grep 零残留 | Task 12 Step 3 + Task 13 |
| §7 AGENTS.md 第 9 节文档同步 | Task 12 |

Placeholder scan：无 "TBD" / "implement later" / "similar to Task N"。
Type consistency：`SnapshotOut` / `GenerationToggle` / `SuggestionItem.export_status` 在引用任务中完全一致；`main_image`（SuggestionItemOut）与 `main_image_url`（SnapshotItemOut）区分清楚。
