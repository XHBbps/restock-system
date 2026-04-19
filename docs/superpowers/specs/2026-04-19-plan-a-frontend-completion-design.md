# Plan A 前端收尾：导出 + 快照历史 + 生成开关（设计）

- **Date**: 2026-04-19
- **Branch**: `feature/plan-a-frontend-completion`（拟）
- **Base**: `master` (`b4a803a`)
- **Scope**: Plan A 后端已全量落地，前端补齐 Excel 导出、快照历史展示、生成开关 UI；**全量清理赛狐推送时代残余代码**（列表页 UI / 历史页逻辑 / 类型枚举 / 单元测试）；附带一个后端迁移给"业务人员"角色补齐 `restock:export` + `config:view`

---

## 1. 目标与现状

### 1.1 背景

Plan A 的 18 项后端改造已通过 PR #10 合并至 master（2026-04-19T04:16:46Z）。后端将"赛狐推送"整体替换为：

- Excel 导出 + 不可变快照版本化（`SuggestionSnapshot`）
- 全局生成开关（`GenerationToggle`，首次导出后自动置 OFF）
- 重复导出保护（`SuggestionItem.exported_snapshot_id`）

### 1.2 前端现状（已校验实际代码，70 处 push 引用分布 9 个文件）

**`api/suggestion.ts`**：
- 残留 8 个死字段：`Suggestion.pushed_items/failed_items`；`SuggestionItem.push_blocker/push_status/push_error/push_attempt_count/pushed_at/saihu_po_number`
- 残留死函数：`pushItems()` L93-102（调用已废弃的 `POST /suggestions/{id}/push`）
- 缺少后端已暴露的 `export_status` / `exported_snapshot_id` / `exported_at` 字段
- `Suggestion.status` 枚举含 2 个后端 CHECK 拒绝的死值 `'partial'` / `'pushed'`（后端实际只允许 `'draft'|'archived'|'error'`）

**`SuggestionDetailView.vue`** (9 处)：
- L34：`<SkuCard :blocker="item.push_blocker">`
- L125：描述性注释"推送状态和异常信息"
- L131-146：状态信息侧栏（push_status tag + push_blocker + saihu_po_number + push_error 四行）
- L168：不可编辑提示 tag 文案判断 `push_status === 'pushed'`
- L309：`isEditable` 中 `push_status !== 'pushed'` 判断

**`SuggestionListView.vue`** (26 处，~110 行死代码)：
- L13-16：`<TaskProgress v-if="pushTaskId">` 推送任务
- L28-33：推送状态筛选下拉
- L35-43：`推送（N）` 多选按钮
- L51-55、L55 row-key="id"：selection 多选逻辑（仅为推送服务）
- L88-94：表格"推送状态"列
- L115：`pushItems` import
- L121：`getSuggestionPushStatusMeta` import
- L139-146 / L152+：`selectedIds` / `filterPushStatus` / `pushing` / `pushTaskId` / `handlePush` / `onPushDone` / `canSelect` / `PUSH_STATUS_SORT_ORDER`

**`HistoryView.vue`** (3 处)：
- `row.push_status` / `row.push_blocker` 列显示
- L161：`canDelete(row): return row.status !== 'pushed'` —— 恒真死 guard

**`utils/status.ts`**：
- L15-16：`suggestionStatusMap` 中 `partial` / `pushed` 死项
- L21-26 + L48-50：`suggestionPushStatusMap` + `getSuggestionPushStatusMeta` 整块死代码

**测试（4 文件，共 ~24 处）**：
- `views/__tests__/SuggestionDetailView.test.ts`(7)、`SuggestionListView.test.ts`(12)、`HistoryView.test.ts`(2)、`utils/status.test.ts`(3)

**其他**：
- 无导出按钮 / 快照历史区 / 生成开关 UI
- `api/snapshot.ts` 未建立
- 无 blob 下载工具函数

### 1.3 权限现状与缺口（已校验 `backend/alembic/versions/20260414_2400_add_rbac_tables.py`）

现有默认角色权限清单：

| 角色 | 权限 |
| --- | --- |
| 超级管理员 | 全部 |
| 业务人员 | `home:view`, `restock:view`, `restock:operate`, `history:view`, `history:delete`, `data_base:view`, `data_biz:view` |
| 阅读者 | 仅 `*:view` 类 |

**缺口**：业务人员既无 `restock:export`（导不了），也无 `config:view`（读不到开关状态）。本 PR 需补一个 alembic 数据迁移给业务人员角色追加这 2 个 code（新装 & 已有实例都覆盖）。

### 1.4 交付目标

一次 PR 完成 B0-B10：
- **B0**：后端迁移 —— 业务人员角色补 `restock:export` + `config:view`
- **B1**：类型/API 客户端清理 —— 删 8 死字段 + 死函数、加 3 新字段、收敛 status 枚举
- **B2**：`utils/status.ts` 清理 —— 删 `partial/pushed` 映射 + `getSuggestionPushStatusMeta`
- **B3**：新建 `api/snapshot.ts` + `utils/download.ts`
- **B4**：`SuggestionDetailView.vue` —— 清 push 引用 + 加导出按钮 + 加快照历史区
- **B5**：`SuggestionListView.vue` —— 删全部推送 UI（~110 行） + 加开关只读 tag
- **B6**：`GlobalConfigView.vue` —— 加生成开关卡片（即时保存）
- **B7**：`HistoryView.vue` —— 改展示 export_status + snapshot_count + `canDelete` 新语义
- **B8**：测试清理 —— 删 4 个测试文件的 push 相关 describe/it 块
- **B9**：`vue-tsc` / `npm run build` / `npm run test:coverage` 全绿
- **B10**：文档同步（`docs/PROGRESS.md` + `docs/Project_Architecture_Blueprint.md`）

---

## 2. 决策（已与用户确认）

| 决策点 | 选择 | 理由 |
| --- | --- | --- |
| 提交粒度 | **A：一个 PR 包所有 B1-B7** | 功能强耦合，分批 review 反增噪；项目 1-5 人，单 PR 便于回滚 |
| 导出交互 | **A：一步式** — 确认 → POST → 自动下载 → Toast 提示开关已关闭 | 降低点击次数；后端已原子完成"创建快照 + 关闭开关"，前端无需分步 |
| 快照历史位置 | **A：详情页底部 PageSectionCard** | 与建议单强绑定；不新增独立页面，维持扁平导航 |
| 生成开关位置 | **C：GlobalConfigView 可编辑 + SuggestionListView 只读状态** | 配置页是权限入口；列表页让操作者一眼看到当前是否可生成 |
| 前端测试 | **推迟** — 本 PR 不引入 vitest 覆盖，单独 follow-up PR | 项目无既存前端测试基建，先交付功能 |
| 实施顺序 | **A：先清死代码，再加功能** | 避免新代码又引用旧类型，重构/新增边界清晰 |
| 业务人员缺权限补法 | **方案甲：给角色追加 `restock:export` + `config:view`** | 复用现有权限码；业务人员只读查看补货参数无安全问题；未来扩展新配置项免手动放行 |
| Q1 列表页推送 UI | **A：全部清除** ~110 行 | CLAUDE.md "最小化改动 = 只保留有用的"；死按钮比工作量危险 |
| Q2 HistoryView 清理方向 | **A：替换成 `export_status` + `snapshot_count`** | `SuggestionOut.snapshot_count` 后端已暴露；与 Plan A 语义对齐 |
| Q3 现存测试文件 | **B：删除 push 相关 describe/it 块** | 与"前端测试独立 PR"决策一致；CI 要跑 `npm run test:coverage`（`.github/workflows/ci.yml:57`），不能红 |
| Q4 快照历史排序 | **A：前端 reverse（最新在上）** | 后端 API 契约稳定；UI 一行代码 |
| Q5 开关卡片交互 | **A：即时保存 + loading + 二次确认** | 开关副作用不可撤销（归档 draft），必须强反馈机制 |
| Q6 Status 枚举收敛 + canDelete | **A 收敛 3 值 + 丙：`canDelete = snapshot_count === 0`** | 类型准确；"导出过不能删"与快照审计语义天然对齐 |

---

## 3. 组件与数据流

### 3.0 后端迁移：业务人员角色权限补齐（新建 alembic 版本）

**文件**：`backend/alembic/versions/20260419_XXXX_grant_export_and_config_view_to_business_role.py`

**表结构参考**（`20260414_2400_add_rbac_tables.py`）：
- `role(id, name, ...)` — `name` 唯一
- `permission(id, code, ...)` — `code` 唯一
- `role_permission(role_id, permission_id)` — 联合主键，带级联

**upgrade**：
```python
from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # 幂等插入：业务人员 += restock:export, config:view
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
```

**downgrade**：
```python
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

**实施说明**：
- **不**改 20260414 老迁移，新增独立版本保留审计轨迹
- 若"业务人员"角色不存在（如开发环境尚未 seed），迁移空操作，无副作用
- `ON CONFLICT` 兜底已授权过的实例不重复插入
- 超级管理员 / 阅读者角色不受影响

### 3.1 API 客户端：`frontend/src/api/snapshot.ts`（新建）

> **说明**：
> - `client.ts` 的 `export default client`（`api/client.ts:44`），import 用 **default**：`import client from './client'`
> - interceptor 不做 `data` 解包，各 API 函数内 `const { data } = await client.get(...); return data`（见 `api/suggestion.ts:67`）

```ts
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
  main_image_url: string | null  // 注意：此处字段名与 SuggestionItemOut.main_image 不同
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

export async function createSnapshot(suggestionId: number, itemIds: number[], note?: string): Promise<SnapshotOut> {
  const { data } = await client.post<SnapshotOut>(`/api/suggestions/${suggestionId}/snapshots`, { item_ids: itemIds, note })
  return data
}

export async function listSnapshots(suggestionId: number): Promise<SnapshotOut[]> {
  // 后端按 version asc 返回（snapshot.py:271），前端 reverse 让最新在表格顶部
  const { data } = await client.get<SnapshotOut[]>(`/api/suggestions/${suggestionId}/snapshots`)
  return [...data].reverse()
}

export async function getSnapshot(snapshotId: number): Promise<SnapshotDetailOut> {
  const { data } = await client.get<SnapshotDetailOut>(`/api/snapshots/${snapshotId}`)
  return data
}

export async function downloadSnapshotBlob(snapshotId: number): Promise<{ blob: Blob; filename: string }> {
  const resp = await client.get(`/api/snapshots/${snapshotId}/download`, { responseType: 'blob' })
  const disposition = resp.headers['content-disposition'] || ''
  const match = disposition.match(/filename\*?=(?:UTF-8'')?["]?([^;"\r\n]+)["]?/i)
  const filename = match ? decodeURIComponent(match[1]) : `snapshot-${snapshotId}.xlsx`
  return { blob: resp.data as Blob, filename }
}
```

### 3.1.1 文件下载工具：`frontend/src/utils/download.ts`（新建）

```ts
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

> id 与外键类型按后端实际为 `int`（`SnapshotOut.id: int`，见 `backend/app/schemas/suggestion_snapshot.py:17`）。前端类型跟进修正为 `number`。

### 3.2 `SuggestionDetailView.vue` 改造

**顶部工具栏**新增导出按钮：
- 条件显示：`auth.hasPermission('restock:export') && detail.status === 'draft'`
- 禁用条件：`!generationToggle.enabled`（前端主动 gate，后端不检查）
- 文案：开关 ON → "导出 Excel"；OFF → tooltip "生成开关已关闭，无法导出"

**点击流程**：
1. `ElMessageBox.confirm` "确认导出？导出后当前建议单的商品将无法重复导出，生成开关将自动关闭。"
2. 收集所有 `export_status !== 'exported'` 的 item.id 作为 `item_ids`
3. `await createSnapshot(id, itemIds)` → 拿到 `snapshot`
4. `await downloadSnapshotBlob(snapshot.id)` → 调 `triggerBlobDownload(blob, filename)`
5. 成功 Toast：`"导出成功，生成开关已关闭"`
6. 调 `load()`（`SuggestionDetailView.vue:243`）刷新 detail；同时刷新快照历史列表

> **浏览器 user activation 风险**：一步式在 confirm 用户点击后同连发 POST+GET blob，主流浏览器（Chrome/Edge/Firefox）已验证允许同 activation context 内触发单个 `<a>.download`。若后期观察到下载拦截，降级为"POST 成功后在 toast 里放'点击下载' 按钮"二步式。

**中部清理**（L131-145）：删除 push_status / push_error 渲染块

**底部**新增 `PageSectionCard` 快照历史：

| 列 | 取值 |
| --- | --- |
| 版本 | `v${version}` |
| 导出人 | `exported_by_name` |
| 导出时间 | `exported_at`（本地化格式化） |
| 商品数 | `item_count` |
| 下载次数 | `download_count` |
| 操作 | "下载"按钮 → `downloadSnapshot(id)` |

> 不展示 `last_downloaded_at`，后端 `SnapshotOut` 未暴露该字段；若后续需要，单独 PR 扩 schema。

### 3.3 `GlobalConfigView.vue`：生成开关卡片

`PageSectionCard` + `ElSwitch`：
- 加载 `GET /api/config/generation-toggle` 填充
- 显示 `updated_at` + `updated_by_name`；**`updated_by_name` 可能为 null**（首次启用未被操作过时），UI 降级为 "—" 或 "从未操作"
- 权限 gate：`auth.hasPermission('restock:new_cycle')` 决定 Switch 是否禁用
- **交互模式**：即时保存（Switch 带 `:loading` 态 + `@change` 立即 PATCH），不走"改值 + 保存按钮"模式。理由：项目现有 `calc_enabled` 是批量保存，但本开关语义重（翻 ON 会归档所有 draft 建议单），即时保存 + loading 反馈更直观
- **二次确认**：翻 OFF → ON 前弹 `ElMessageBox.confirm`："打开开关将归档所有草稿建议单，确认继续？"（后端 `config.py:213-225` 在 OFF→ON 时自动归档 draft）
- 失败 rollback：`PATCH` 报错时恢复 Switch 到原值，Toast 走 `getActionErrorMessage`

### 3.4 `SuggestionListView.vue`：全量清理推送 UI + 新增开关 tag

#### 3.4.1 删除（~110 行）

**模板**：
- L13-16 `<TaskProgress v-if="pushTaskId">`
- L28-33 推送状态筛选下拉
- L35-43 推送多选按钮
- L45 的 `@selection-change` / `@select-all` / `:selectable="canSelect"` 移除，第一列 `<el-table-column type="selection">` 整列删（多选仅为推送服务，导出只在详情页）
- L88-94 表格"推送状态"列

**脚本**：
- L115 `pushItems` import（连带 `api/suggestion.ts` 该函数在 §3.5 已删）
- L121 `getSuggestionPushStatusMeta` import（连带 `utils/status.ts` 该函数在 §3.7 已删）
- L139-146 state：`selectedIds` / `suppressSelectionSync` / `filterPushStatus` / `pushing` / `pushTaskId`
- `handlePush` / `onPushDone` / `canSelect` 函数
- `PUSH_STATUS_SORT_ORDER` 常量
- 其中 `genTaskId` / `generating` / `triggerEngine` / `onGenDone`、`searchSku` **保留**（是"生成新一轮"和 SKU 搜索，非推送相关）

#### 3.4.2 新增：开关状态 tag

`PageSectionCard` 的 `#actions` 插槽（已有建议单状态 tag 在 L5-8）并排新增：
- ON → success 色 "生成开关：开启"
- OFF → info 色 "生成开关：已关闭"
- `title` 属性显示 `updated_by_name ?? '—'` + `updated_at` 本地化
- 组件 `onMounted` + `onActivated` 双钩子调用 `GET /api/config/generation-toggle`（防御式）
- 由 §3.0 迁移确保业务人员具有 `config:view`，读接口不会返回 403

### 3.5 `api/suggestion.ts`：类型与死代码清理

**`Suggestion` 接口**：
- 删：`pushed_items`、`failed_items`
- 改：`status: 'draft' | 'partial' | 'pushed' | 'archived' | 'error'` → `status: 'draft' | 'archived' | 'error'`（Q6-A 收敛，后端 CHECK 约束实际只允许这 3 个值，见 `backend/app/models/suggestion.py:29`）

**`SuggestionItem` 接口**：
- 删：`push_blocker`、`push_status`、`push_error`、`push_attempt_count`、`pushed_at`、`saihu_po_number`
- 加：`export_status: 'pending' | 'exported'`（后端 CHECK 约束，见 `backend/app/models/suggestion.py:68`）
- 加：`exported_snapshot_id: number | null`
- 加：`exported_at: string | null`

**函数**：
- 删：`pushItems()` L93-102（调用已废弃的 `POST /suggestions/{id}/push`）

**`SuggestionDetailView.vue` 引用清理点**：
- L34：`<SkuCard :blocker="item.push_blocker">` prop 传值移除（`SkuCard.vue:18` 中 `blocker?` 是可选 prop）
- L125：描述性注释"推送状态和异常信息"改为"导出状态和异常信息"
- L131-146：状态信息侧栏整块替换为导出状态展示（展示 `export_status` tag + `exported_at` + `exported_snapshot_id` 跳转）
- L168：不可编辑 tag 文案 `push_status === 'pushed' ? '已推送条目不可编辑' : '已归档建议单不可编辑'` 改为 `export_status === 'exported' ? '已导出条目不可编辑' : '已归档建议单不可编辑'`
- L309：`isEditable` 中 `push_status !== 'pushed'` 改判 `export_status !== 'exported'`

> 本次**不**新建集中权限常量文件（现有代码风格一律硬编码字符串）。沿用 `'restock:export'` / `'restock:new_cycle'` 硬编码。

### 3.6 `HistoryView.vue`：换 export 语义 + canDelete 新规则

- 删除 `push_status` / `push_blocker` 引用（3 处）
- 新增表格列：
  - "导出状态"：展示 `snapshot_count > 0 ? '已导出' : '未导出'`（或直接显示数字）
  - "快照数"：展示 `snapshot_count`
- `canDelete(row)` 改为：`return row.snapshot_count === 0`（Q6-丙）
  - 业务含义：凡有快照的建议单不可删（审计保留）
  - 依赖 `Suggestion.snapshot_count: number` 字段，后端 `SuggestionOut:21` 已暴露
- **需要同步改 `api/suggestion.ts` 的 `Suggestion` 接口**：追加 `snapshot_count: number`

### 3.7 `utils/status.ts`：死 map 清理

- L15-16：删除 `suggestionStatusMap` 中的 `partial` / `pushed` 两行
- L21-26：删除整个 `suggestionPushStatusMap` 常量
- L48-50：删除 `getSuggestionPushStatusMeta` 函数导出

其他 map 和函数（`getSyncStatusMeta` / `getShopStatusMeta` 等）保留。

### 3.8 测试清理（Q3-B 决策：删除 push 相关 case）

- `views/__tests__/SuggestionDetailView.test.ts`：删除涉及 `push_status`/`push_blocker` 的 describe/it（7 处），特别是 mock `makeItem({ push_status: 'pushed' })` 相关 guard 测试；替换 mock 使用 `export_status: 'exported'`
- `views/__tests__/SuggestionListView.test.ts`：删除整块推送相关测试（12 处）；保留列表渲染、SKU 搜索、分页测试
- `views/__tests__/HistoryView.test.ts`：删除 `canDelete({status:'pushed'})` 及 `status: 'pushed'` 的 mock；新增 `canDelete({snapshot_count: N})` 的 case（如果时间允许；否则只删旧 case）
- `utils/status.test.ts`：删除 `getSuggestionPushStatusMeta` 相关测试（3 处），删除 `suggestionStatusMap` 对 `partial` / `pushed` 的断言

**验收**：`npm run test:coverage` 全绿（CI 依赖此命令，见 `.github/workflows/ci.yml:57`）

### 3.9 `Suggestion.status` 枚举收敛（Q6-A）

见 §3.5 类型修改。已验证散落引用点并检查连锁反应：

| 引用点 | 处理 |
| --- | --- |
| `utils/status.ts:15-16` | §3.7 删除死 map |
| `HistoryView.vue:161` canDelete | §3.6 改为 `snapshot_count === 0` |
| `HistoryView.test.ts:132` | §3.8 删除 |
| `SuggestionListView.test.ts:77` | §3.8 删除 push 相关 |
| `SuggestionDetailView.vue:309` | §3.5 已覆盖 |

实施后跑 `npm run build` + `npm run test:coverage` 兜底。

---

## 4. 错误处理与边界（已校验后端实现）

### 4.1 导出 `POST /api/suggestions/{id}/snapshots`

**统一处理策略**：所有 4xx / 5xx 都走 `ElMessage.error(getActionErrorMessage(err, '导出失败'))`。`apiError.ts:28` 已自动提取后端 `detail` 字段，后端的中文描述（"建议单已归档"、"部分 item 已导出" 等）会直接展示，**前端无需针对每个状态码硬编码文案**。

后端实际状态码清单（仅作认知，不单独分支）：

| 场景 | 后端状态码 |
| --- | --- |
| 建议单已归档 | 409 Conflict（detail: "建议单状态 archived，不可导出"） |
| item_ids 为空 | 422（Pydantic min_length=1） |
| item_ids 含非本单 item | 400 |
| item_ids 含已导出过的 item | 409（注：代码用 409，见 `snapshot.py:80`） |

**⚠️ 关键**：后端**不检查**全局开关，OFF 时照样允许导出。前端 UI 自行 gate（按钮置灰 + tooltip）。后端无并发锁，不处理并发 409。前端在 items 为空时按钮 `disabled`，不依赖 422 反馈。

### 4.2 下载 `GET /api/snapshots/{id}/download`

所有错误走 `getActionErrorMessage(err, '下载失败')` 统一提示。后端状态码：410 Gone（文件被清理）/ 404（快照不存在）/ 403（无权限）。

### 4.3 开关 `PATCH /api/config/generation-toggle`

后端 last-write-wins，无并发锁。前端：
- 切换时 Switch `:loading` 态禁用控件
- 成功后刷新 `enabled` / `updated_at` / `updated_by_name`
- 失败时**手动 rollback** Switch 到原值（否则 UI 与后端状态不一致），Toast 走 `getActionErrorMessage`

### 4.4 item_ids 构造规则

前端从详情页当前 items 取 `export_status !== 'exported'` 的 id（等价于 `exported_snapshot_id === null`）。后端 re-export 保护兜底，但前端主动过滤避免 400。

### 4.5 `last_downloaded_at` 字段

后端 model 有，**SnapshotOut schema 未暴露**。按 CLAUDE.md "最小化改动"：本 PR **不展示**该列；如需展示，单独 PR 扩 schema。

### 4.6 `generation_status` 字段

后端 `SnapshotOut.generation_status` 取值：`'generating' | 'ready' | 'failed'`。创建接口在同一请求内同步生成文件后才返回，正常路径拿到的是 `'ready'`；但历史列表若遇到 `'failed'` 快照，前端：
- 历史表该行下载按钮禁用 + tooltip "生成失败"
- 不因此阻断其他正常快照的展示

---

## 5. 提交顺序与验收清单

### 5.1 Commit 序列（approach A：先权限 → 先清死代码 → 再加功能）

| # | Commit | 范围 |
| --- | --- | --- |
| 0 | `feat(backend): 业务人员角色追加 restock:export 与 config:view` | 新 alembic 版本 + 本地 `alembic upgrade head` 验证 |
| 1 | `refactor(frontend): 收敛 Suggestion/SuggestionItem 类型并删除 pushItems` | `api/suggestion.ts` 删 8 死字段 + 死函数、加 3 新字段、status 枚举收敛为 3 值、加 `snapshot_count` |
| 2 | `refactor(frontend): 清理 utils/status 推送相关死代码` | `utils/status.ts` 删 `partial`/`pushed` map 项 + `suggestionPushStatusMap` + `getSuggestionPushStatusMeta` |
| 3 | `refactor(frontend): SuggestionDetailView 移除 push 引用` | L34/L125/L131-146/L168/L309 清理，未新增功能 |
| 4 | `refactor(frontend): SuggestionListView 删除推送 UI` | 模板 ~110 行 + state + handler 清理，保留生成/搜索/分页 |
| 5 | `refactor(frontend): HistoryView 替换 push 列为 export_status + snapshot_count，canDelete 改用 snapshot_count === 0` | 3 处 push 列删 + canDelete 语义更新 |
| 6 | `test(frontend): 删除推送相关测试块` | 4 个测试文件共 ~24 处 describe/it，保留 SKU 搜索/分页/列表渲染等 |
| 7 | `feat(frontend): 新增 snapshot API 客户端与下载工具` | 新建 `api/snapshot.ts` + `utils/download.ts` |
| 8 | `feat(frontend): 建议单详情页新增导出按钮与历史快照区` | `SuggestionDetailView.vue` 顶部导出 + 底部 `PageSectionCard` 历史表 |
| 9 | `feat(frontend): 全局配置页新增生成开关卡片` | `GlobalConfigView.vue` 即时保存 + 二次确认 + rollback |
| 10 | `feat(frontend): 建议单列表页显示开关只读状态` | `SuggestionListView.vue` `#actions` 加 tag + onMounted/onActivated 拉取 |
| 11 | `docs(sync): Plan A 前端收尾同步 PROGRESS/Blueprint` | `docs/PROGRESS.md` + `docs/Project_Architecture_Blueprint.md` |

> commits 1-6 为"清理 pass"（B1/B2/B7/B8 全部落完）；commits 7-10 为"功能 pass"（B3-B6）；commit 0/11 为两端包围。全部合并在**单 PR** 内（决策 A）。

### 5.2 验收清单

**构建 & 后端迁移**
- [ ] `cd backend && alembic upgrade head` 干净通过
- [ ] 迁移后查询确认"业务人员"角色含 `restock:export` + `config:view`（两条 `role_permission` 新记录，再次执行迁移无副作用）
- [ ] `pytest tests/unit -q` 零回归
- [ ] `pnpm vue-tsc --noEmit` 零错（Q6-A 收敛后无残留 `'partial'|'pushed'` 引用）
- [ ] `pnpm build` 成功
- [ ] `npm run test:coverage` 全绿（CI 入口，见 `.github/workflows/ci.yml:57`；push 相关 case 已全部删除）
- [ ] 全仓 `grep -rn "push_status\|push_blocker\|push_error\|push_attempt_count\|pushed_at\|saihu_po_number\|pushItems\|suggestionPushStatusMap\|getSuggestionPushStatusMeta" frontend/src` 零命中

**手动流程**（dev 容器 `http://localhost:8088`）
- [ ] 开关 ON → 详情页导出按钮可用 → 确认 → 下载 Excel → 开关自动关闭
- [ ] 开关 OFF → 导出按钮置灰 + tooltip 提示
- [ ] 已归档建议单 → 导出按钮禁用
- [ ] 导出后历史表新增一行，版本号递增
- [ ] 历史表"下载"按钮可重复下载，`download_count` +1
- [ ] 文件被清理时下载提示"已过期"
- [ ] 全局配置页翻 OFF → ON 弹确认框 → 确认后自动归档所有 draft 建议单
- [ ] 全局配置页切换开关 → 建议单列表页状态 tag 同步更新（切回列表页后触发刷新）
- [ ] 开关 PATCH 失败 → Switch 回滚到原值
- [ ] 用**业务人员角色**账号登录验证：可见导出按钮、可读列表页 tag、**不能**翻开关（Switch 置灰）
- [ ] 无 `restock:export` 权限用户（如"阅读者"）看不到导出按钮
- [ ] 无 `restock:new_cycle` 权限用户在配置页看到开关置灰
- [ ] 历史页：含快照的建议单"删除"按钮禁用；无快照的建议单（draft/archived/error 任意 status）可删除（验证 `canDelete = snapshot_count === 0` 新语义）

**文档同步**（AGENTS.md 第 9 节）
- [ ] `docs/PROGRESS.md` "最近更新" 日期 = 2026-04-19
- [ ] `docs/Project_Architecture_Blueprint.md` 前端章节反映新导出流程
- [ ] commit message 符合 feat / fix / refactor / docs 前缀规范

### 5.3 范围外（确认不做）

- 前端单元测试：后续独立 PR
- `last_downloaded_at` 后端 schema 扩展：后续独立 PR
- 快照详情页（`/api/snapshots/{id}`）：仅 API 保留，UI 暂不消费

---

## 6. 风险

| 风险 | 概率 | 影响 | 缓解 |
| --- | --- | --- | --- |
| 浏览器 Blob 下载在部分企业代理下被剥离 | 低 | 文件无法保存 | 复用项目中已验证的 Excel 下载模式（若存在） |
| 前端过滤 `exported_snapshot_id === null` 后得到空列表，误触发 422 | 中 | 用户看到无意义错误 | 按钮在空列表时自动禁用 |
| 开关状态在不同页面间不同步 | 中 | 列表页显示陈旧状态 | 列表页 `onMounted` + `onActivated` 双钩子拉取；App.vue 当前无 `<keep-alive>`，实际每次都重拉 |
| 浏览器拦截 blob 下载（user activation 丢失） | 低 | 首次导出文件不落地 | 主流浏览器已验证通过；如实测受阻，降级二步式 |
| `updated_by_name` 为 null（首次访问或 seed 数据） | 中 | UI 显示 "undefined" / 空白 | 前端统一渲染 `name ?? '—'` |
| 重构死字段时漏删引用导致 vue-tsc 报错 | 低 | CI 红 | 由 `vue-tsc --noEmit` 兜底，本地提交前必跑 |
| 已有实例的"业务人员"角色名被手动改过 → `WHERE r.name = '业务人员'` 无匹配 | 低 | 迁移对该实例空操作 | 迁移幂等无副作用；文档注明需手动核对；管理员可通过 AuthManageView 界面手动勾选 |
| 新权限码 `restock:export` / `config:view` 未存在 permission 表 | 极低 | 迁移插入 0 行 | 两者已在 `backend/app/core/permissions.py` REGISTRY 注册，20260414 初始迁移已 seed |

---

## 7. 下一步

1. 本设计稿通过用户 review 后，调用 `writing-plans` skill 产出实施计划
2. 实施计划拆分为 B1~B6 任务清单，逐步实施
3. 每步完成后按 AGENTS.md 第 9 节同步文档
