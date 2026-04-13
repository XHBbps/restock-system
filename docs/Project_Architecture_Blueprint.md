# Restock System 架构蓝图

> 生成时间：2026-04-11
> 代码库版本：`001-saihu-replenishment` 分支
> 文档目的：定义架构基线，供新增功能和重构时保持一致性

---

## 1. 架构概览

**Restock System** 是一套跨境电商海外仓补货管理系统，采用**分层单体架构（Layered Monolith）**，后端围绕领域业务（补货计算）组织代码，前端采用标准 Vue SPA 结构。

### 核心设计原则

1. **纯异步 I/O**：后端从 Web 层（FastAPI）到数据库层（asyncpg）全链路 async/await，避免阻塞
2. **数据库即队列**：自研 TaskRun 表替代 Celery/Redis，减少部署复杂度
3. **进程内编排**：Worker、Scheduler、Reaper 与 FastAPI 在同一 Python 进程中运行（可通过环境变量分离）
4. **快照即历史**：补货建议生成时快照输入（velocity、sale_days、配置，含 `restock_regions`），已生成的建议单不会因配置变更而改动
5. **批量优先于迭代**：引擎和同步层尽量批量加载，避免 N+1 查询
6. **前端本地分页**：数据页一次拉取全量，前端做筛选和分页（内部用户 1-5 人，数据量有限）

### 技术栈

| 层级 | 技术 |
|---|---|
| 前端 | Vue 3.5 / TypeScript 5.7 / Pinia 2 / Vue Router 4 / Element Plus 2.9 / Vite 6 / ECharts 6 |
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy 2.0 async / Pydantic 2 / APScheduler / httpx / structlog |
| 数据库 | PostgreSQL 16（asyncpg 驱动）/ Alembic 迁移 |
| 部署 | Docker Compose / Caddy 反向代理 / Nginx 静态托管 |

---

## 2. 系统分层

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Frontend (Vue 3 SPA)                          │
│  views → components → stores (Pinia) → api client (Axios)          │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTP + JWT
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       Backend (FastAPI)                             │
│                                                                      │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ API Layer (app/api)                                           │ │
│  │ REST 端点: auth / data / suggestion / sync / config / monitor │ │
│  └──────────────────────┬────────────────────────────────────────┘ │
│                         │                                           │
│  ┌──────────────────────▼────────────────────────────────────────┐ │
│  │ Schema Layer (app/schemas) — Pydantic DTO                     │ │
│  └──────────────────────┬────────────────────────────────────────┘ │
│                         │                                           │
│  ┌──────────────────────▼────────────────────────────────────────┐ │
│  │ Business Layer                                                │ │
│  │ ┌───────────┬────────────┬─────────────┬──────────────────┐ │ │
│  │ │ engine/   │ sync/      │ pushback/   │ tasks/           │ │ │
│  │ │ 6 步计算  │ 赛狐数据同步│ 采购单回写  │ 队列+调度+worker │ │ │
│  │ └───────────┴────────────┴─────────────┴──────────────────┘ │ │
│  └──────────────────────┬────────────────────────────────────────┘ │
│                         │                                           │
│  ┌──────────────────────▼────────────────────────────────────────┐ │
│  │ Integration Layer (app/saihu) — 赛狐 HTTP 客户端              │ │
│  └──────────────────────┬────────────────────────────────────────┘ │
│                         │                                           │
│  ┌──────────────────────▼────────────────────────────────────────┐ │
│  │ Model Layer (app/models) — SQLAlchemy ORM                     │ │
│  └──────────────────────┬────────────────────────────────────────┘ │
│                         │                                           │
│  ┌──────────────────────▼────────────────────────────────────────┐ │
│  │ DB Layer (app/db) — AsyncSession Factory                      │ │
│  └──────────────────────┬────────────────────────────────────────┘ │
│                         │                                           │
│  ┌──────────────────────▼────────────────────────────────────────┐ │
│  │ Core (app/core) — logging / exceptions / security / timezone │ │
│  └───────────────────────────────────────────────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ async SQL
                               ▼
                     ┌─────────────────────┐
                     │  PostgreSQL 16      │
                     │  20+ tables         │
                     │  (业务 + 队列 + 日志)│
                     └─────────────────────┘
                               ▲
                               │ sync_*
                               │
                     ┌─────────────────────┐
                     │  Sellfox (赛狐 API) │
                     │  店铺/商品/订单/库存 │
                     └─────────────────────┘
```

**依赖方向**：自上而下，下层不反向依赖上层。跨层通信通过 Pydantic DTO（API ↔ 业务）和 ORM 对象（业务 ↔ DB）。

---

## 3. 后端核心组件

### 3.1 补货计算引擎（app/engine）

**职责**：将同步下来的数据（订单、库存、商品、仓库）转换为可执行的采购建议单。

**流水线（runner.py）**：

| Step | 模块 | 输入 | 输出 | 说明 |
|---|---|---|---|---|
| 1 | `step1_velocity.py` | 近 30 天订单 | `velocity[sku][country]` | 加权日均销量：7日×0.5 + 14日×0.3 + 30日×0.2；若 `global_config.restock_regions` 非空，则仅统计这些国家的订单 |
| 2 | `step2_sale_days.py` | velocity + 海外库存 + 在途 | `sale_days[sku][country]`, `inventory[sku][country]` | 可售天数 = 库存总和 / velocity；`load_in_transit` 基于已推送未归档的建议条目 |
| 3 | `step3_country_qty.py` | velocity + inventory + target_days | `country_qty[sku][country]` | `max(target × v − 库存, 0)`，纯函数无 DB |
| 4 | `step4_total.py` | country_qty + velocity + 国内库存 + buffer_days | `total_qty[sku]` | 汇总各国补货量 + 缓冲天数 − 国内库存 |
| 5 | `step5_warehouse_split.py` | country_qty + 订单邮编 + 邮编规则 + 国家仓库映射 | `warehouse_breakdown[country][wh_id]` | 按邮编规则分配到具体仓库，无订单时均分；若配置了 `global_config.restock_regions`，仅消费这些国家的订单明细作为分仓依据；**2026-04-11 起**同优先级 tied 均分：`match_warehouses()` 返回首批同 priority 命中列表，qty 按 `1/N` 均分（先过滤不可用仓再定 N） |
| 6 | `step6_timing.py` | sale_days + lead_time | `t_purchase[country]`, `urgent` | 计算建议采购日，判断紧急标志 |

**并发控制**：通过 `pg_advisory_xact_lock(7429001)` 事务级咨询锁（`runner.py:58-61`），防止并发引擎覆盖彼此。

**持久化**：一次完整计算作为原子事务 → 旧的 draft/partial 建议归档 → 新建 Suggestion + SuggestionItem[] 批量 INSERT。

**快照特性**：`velocity_snapshot`、`sale_days_snapshot`、`global_config_snapshot` 均存入 JSONB 字段，支持历史追溯；其中 `global_config_snapshot` 会记录生成时的 `restock_regions`，用于说明当次建议有哪些国家订单参与了计算。

### 3.2 数据同步层（app/sync）

**职责**：从赛狐 API 增量同步店铺、仓库、商品、订单、库存、出库记录到本地库。

**模式**：每个赛狐资源对应一个 sync job：

```python
@register("sync_inventory")
async def sync_inventory_job(ctx: JobContext) -> None:
    await mark_sync_running(db, JOB_NAME)
    try:
        async for raw in list_inventory_items(...):  # Saihu 分页拉取
            await _upsert_inventory(db, raw, warehouse_country_map)
            if count % 100 == 0:
                await db.commit()
        await mark_sync_success(db, JOB_NAME, started)
    except Exception as exc:
        await mark_sync_failed(db, JOB_NAME, str(exc))
        raise
```

**批量 UPSERT**：使用 `pg_insert(...).on_conflict_do_update(...)` 模式，避免先 SELECT 后 INSERT/UPDATE 的竞态。

**状态追踪**：每个 job 在 `sync_state` 表中维护最后运行时间、状态、错误信息。

**出库记录同步**：`sync_out_records` 会把赛狐“其他出库”记录同步到 `in_transit_record` / `in_transit_item`，除在途状态观测所需字段外，还保留 `warehouseId`、`updateTime`、`type/typeName`、`commodityId`、`perPurchase`，用于数据页直接展示“出库记录”主表和明细表字段。

**订单详情获取**：除自动 `sync_order_detail` 外，订单页还提供右侧独立“详情获取”组件，前端仅提交回溯天数到 `POST /api/sync/order-detail/refetch`。接口层会先检查活跃的 `refetch_order_detail`、`sync_order_detail`、`sync_all` 任务并直接返回现有 task_id，避免手动触发与定时 / 全量同步并发重复抓取；仅在无冲突时才按“最近 N 天”筛选本地缺少详情的全部订单并创建 `refetch_order_detail` TaskRun 后台任务，不再设置手动单次数量上限。该任务绕过 `order_detail_fetch_log` 的去重过滤，但继续复用既有失败分类、2 QPS / 2 并发抓取与落库逻辑，并按“已完成 X / 失败 Y / 总数 N”精确回写进度。

### 3.3 任务队列系统（app/tasks）

**核心表**：`task_run`

```sql
CREATE TABLE task_run (
  id BIGSERIAL PRIMARY KEY,
  job_name VARCHAR NOT NULL,
  status VARCHAR NOT NULL,  -- pending / running / success / failed / skipped / cancelled
  dedupe_key VARCHAR,
  trigger_source VARCHAR,   -- scheduler / manual / api
  priority INT DEFAULT 0,
  payload JSONB,
  worker_id VARCHAR,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  heartbeat_at TIMESTAMPTZ,
  lease_expires_at TIMESTAMPTZ,
  current_step VARCHAR,
  step_detail TEXT,
  total_steps INT,
  error_msg TEXT
);

-- 活跃任务去重（仅对 pending/running 生效）
CREATE UNIQUE INDEX uq_task_run_active_dedupe 
  ON task_run (dedupe_key) 
  WHERE status IN ('pending', 'running');

-- Worker 调度索引（仅 pending）
CREATE INDEX ix_task_run_pending_priority 
  ON task_run (status, priority, created_at) 
  WHERE status = 'pending';

-- Reaper 过期索引（仅 running）
CREATE INDEX ix_task_run_lease 
  ON task_run (lease_expires_at) 
  WHERE status = 'running';
```

**四个组件协同**：

```
┌───────────────┐    enqueue    ┌──────────┐    claim     ┌────────┐
│   Scheduler   │──────────────▶│ task_run │◀─────────────│ Worker │
│ (APScheduler) │               │   (DB)   │              │ (poll) │
└───────────────┘               └─────┬────┘              └────────┘
       ▲                              │                        │
       │                              │ reap expired           │ heartbeat
       │ cron/interval                ▼                        │
       │                        ┌──────────┐                   │
       └────── register jobs ───┤  Reaper  │◀──────────────────┘
                                └──────────┘
```

- **Scheduler**：APScheduler 按间隔/cron 触发，调用 `enqueue_task()`（不直接执行任务）
- **Worker**：每 2 秒轮询一次，用 `FOR UPDATE SKIP LOCKED` 原子抢占 pending 任务，启动执行 + 心跳协程
- **Reaper**：每 60 秒扫描 `lease_expires_at < now()` 的 running 任务，标记为 failed（worker 死亡回收）
- **Heartbeat**：每 30 秒延长 `lease_expires_at`，约束 `heartbeat × 2 < lease_minutes × 60`

**进度追踪**：`TaskRun.current_step / step_detail / total_steps` 由 worker 在执行中写入，前端 `TaskProgress` 组件轮询 `/api/tasks/{id}`。`sync_order_detail` / `refetch_order_detail` 直接按目标订单数回写精确进度；店铺、仓库、商品、库存、订单、出库等分页同步任务则复用赛狐分页响应里的 `totalPage` 输出“第 P / N 页”进度，不额外发起预扫描请求。

### 3.4 赛狐集成层（app/saihu）

**单例客户端 + 端点包装器 + Token 管理 + 限流 + 重试**：

```
调用方
  │
  ▼
endpoints/xxx.py  ← 薄包装，负责参数构造和分页迭代
  │
  ▼
SaihuClient.post()  ← 统一重试 + 日志
  │
  ├─▶ TokenManager.get_token()  ← 单飞模式 + 5 分钟预刷新
  │
  ├─▶ rate_limit.get_limiter(endpoint)  ← per-endpoint QPS
  │
  ├─▶ httpx.AsyncClient.post()  ← 实际 HTTP
  │
  └─▶ ApiCallLog INSERT  ← 每次调用必记录
```

**重试策略**（tenacity）：
- 指数退避：1s → 2s → 4s → 10s
- 可重试：`SaihuRateLimited`（40019）、`SaihuNetworkError`
- 不重试：`SaihuBizError`（业务错误码）
- **特殊处理**：`SaihuAuthExpired`（40001）→ 在重试预算**之外**强制刷新 token 后再重试一次

**限流**：
```python
_ENDPOINT_RATE_OVERRIDES = {
    "/api/order/detailByOrderId.json": 3,  # 该接口放宽到 3 QPS
}
# 默认 1 QPS per endpoint
```

**Token 单飞**：并发 `get_token()` 调用共享同一个刷新 Future，避免同时发起多个刷新请求。

### 3.5 横切关注点

| 关注点 | 实现 | 位置 |
|---|---|---|
| **认证** | JWT HS256，24h 有效，单用户 `sub="owner"` | `core/security.py`, `api/deps.py` |
| **异常** | `BusinessError` 层次（NotFound/Unauthorized/ValidationFailed/...）+ `SaihuAPIError` 层次，全局 exception handler 转 JSON | `core/exceptions.py`, `main.py:113-131` |
| **日志** | structlog + contextvars 绑定 `request_id`，dev ConsoleRenderer / prod JSONRenderer | `core/logging.py`, `core/middleware.py` |
| **中间件** | `RequestLoggingMiddleware` 记录 method/path/status/duration_ms，注入 X-Request-Id 响应头 | `core/middleware.py` |
| **时区** | 存储 UTC，展示北京时间；`parse_saihu_time` 按 marketplace_id 推断源时区再转换 | `core/timezone.py` |
| **配置** | `pydantic-settings` 从环境变量/`.env` 加载，`get_settings()` 单例 | `config.py` |

---

## 4. 前端核心组件

### 4.1 目录结构

```
src/
├── views/           # 页面（18 个）
│   ├── LoginView / WorkspaceView / NotFoundView
│   ├── SuggestionListView / SuggestionDetailView / HistoryView
│   ├── data/        # 6 个数据页
│   └── SyncConsoleView / GlobalConfigView / ZipcodeRuleView / ApiMonitorView / PerformanceMonitorView
├── components/      # 可复用组件
│   ├── AppLayout / PageSectionCard / SkuCard / StatusTag / TablePaginationBar / TaskProgress
│   ├── charts/      # BaseChart (ECharts wrapper)
│   ├── dashboard/   # Dashboard 专用卡片
│   └── sync/        # 同步专用组件
├── api/             # API 客户端（每个领域一个文件）
├── stores/          # Pinia 状态（auth / sidebar / task）
├── router/          # 路由 + 鉴权守卫
├── utils/           # 工具函数（format / tableSort / countries / warehouse / status / monitoring / ...）
├── styles/          # 设计系统（tokens.scss + element-overrides.scss）
├── config/          # 导航配置
└── main.ts
```

### 4.2 设计系统

**基于 shadcn/ui Zinc 主题**，在 `src/styles/tokens.scss` 中定义：
- **颜色**：50+ 设计令牌，主色 `#18181b`（zinc-900）
- **间距**：4px 网格（`$space-1` 至 `$space-16`）
- **字体**：Inter + JetBrains Mono
- **圆角**：4 / 6 / 8 / 12 / pill
- **阴影**：card / popup 两级

`element-overrides.scss` 通过 Element Plus 的 `--el-*` CSS 变量机制，将所有 UI 组件样式对齐到设计令牌。

### 4.3 状态管理

| Store | 状态 | 持久化 |
|---|---|---|
| `useAuthStore` | token, isAuthenticated | localStorage |
| `useSidebarStore` | isCollapsed, expandedCategories | localStorage |
| `useTaskStore` | tasksById, polling | 内存（刷新丢失） |

**全局状态仅保留 3 个 store**，其余状态局部保存在 view 的 `ref/reactive` 中。

### 4.4 API 客户端

**`src/api/client.ts`**：
```typescript
const client = axios.create({ baseURL: '/', timeout: 30000 })

// 请求拦截器：注入 Bearer token
client.interceptors.request.use((config) => {
  const token = useAuthStore().token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 响应拦截器：401 自动清除 token + 跳转登录
client.interceptors.response.use(undefined, (error) => {
  if (error.response?.status === 401) {
    useAuthStore().clearToken()
    router.push('/login')
  }
  return Promise.reject(error)
})
```

**按领域拆分**：`auth.ts` / `data.ts` / `suggestion.ts` / `config.ts` / `monitor.ts` / `sync.ts` / `task.ts` / `dashboard.ts`。每个文件导出类型定义和异步函数。

`dashboard.ts` 当前消费 `/api/metrics/dashboard`，用于信息总览页展示顶部风险卡片、左侧“各国缺货风险分布”和右侧“补货量国家分布”。其中风险分布基于当前 `draft/partial` 建议单快照的 `sale_days_snapshot`，按全局 `lead_time_days`、`target_days` 分桶为“紧急 / 临近补货 / 安全”；右侧国家分布则汇总当前建议单全部条目的 `country_breakdown`。

### 4.5 数据流模式

**统一的"加载全量 + 前端筛选 + 本地分页"模式**：

```typescript
const rows = ref<T[]>([])                    // 全量数据
const filters = reactive({ ... })            // 筛选条件
const page = ref(1)
const pageSize = ref(20)

const filteredRows = computed(() => {        // 筛选
  return rows.value.filter(r => ...)
})

const pagedRows = computed(() => {           // 分页
  const start = (page.value - 1) * pageSize.value
  return filteredRows.value.slice(start, start + pageSize.value)
})

async function reload() {
  const resp = await listData({ page: 1, page_size: 5000 })  // 一次拉完
  rows.value = resp.items
  page.value = 1
}
```

**优势**：筛选即时响应无需 API、代码简单、跨页选择容易实现。
**限制**：数据量不宜超过数千条（当前内部用户场景完全满足）。

### 4.6 路由与鉴权

**`src/router/index.ts`**：
- 所有业务路由嵌套在 `AppLayout` 下
- `meta.public: true` 允许未登录访问（仅 `/login`）
- `authGuard` 在 `beforeEach` 中检查，失败时跳转 `/login?redirect=<origin>`
- 支持 legacy redirect（旧路径自动重定向到新路径）

### 4.7 共享组件模式

| 组件 | 用途 | 复用位置 |
|---|---|---|
| `PageSectionCard` | 统一页面卡片容器，`title` + `#actions` slot | 所有列表页 |
| `SkuCard` | 商品展示（图片 + 名称 + SKU + blocker 标签） | 商品、库存、订单、建议单 |
| `StatusTag` | 状态标签（基于 StatusMeta 对象） | 所有状态展示 |
| `TablePaginationBar` | 分页条，v-model 绑定 currentPage 和 pageSize | 所有数据表格 |
| `TaskProgress` | 长任务进度展示，自动轮询 `/api/tasks/{id}`；可解析按条数和按页数/步骤的确定型进度 | 引擎生成、推送、同步 |
| `sync/OrderDetailFetchAction` | 订单页右侧“详情获取”动作组件，封装回溯天数、触发逻辑与冲突提示 | 订单页 |

**前端监控命名约定**：
- `src/utils/monitoring.ts` 统一负责监控页的名称展示口径，包括赛狐接口 `endpoint`、性能监控 `request/resource` 名称中文化，以及 tooltip 中保留原始路径
- `ApiMonitorView`、`PerformanceMonitorView`、`sync/FailedApiCallTable` 只消费该工具，不在页面内各自维护映射表，避免图表、表格、tooltip 口径漂移

**信息总览页口径**：
- `WorkspaceView` 首行卡片展示当前建议单的风险概览：`urgent_count`、`warning_count`、`safe_count` 按 SKU 最小可售天数相对全局阈值分桶，`risk_country_count` 表示风险分布中出现的国家数
- 左图使用分组柱状图展示各国缺货风险分布，统计对象是当前建议单快照中存在该国家 `sale_days_snapshot` 的 SKU 数量，而不是实时库存平均值
- 右图继续使用饼图，但数据改为 `country_restock_distribution`，即当前建议单全部条目的 `country_breakdown` 汇总，用于展示实际建议补货量的国家分布

---

## 5. 数据流程示例

### 场景 1：用户触发补货计算

```
用户点击"生成补货建议"
  │
  ▼
前端 POST /api/engine/run
  │
  ▼
api/suggestion.py: enqueue_task("calc_engine", "manual")
  │
  ▼
task_run 表 INSERT status=pending, dedupe_key="calc_engine"
  │
  ▼ （2 秒内）
Worker 轮询 → 抢占 → status=running, 启动 heartbeat
  │
  ▼
runner.run_engine(ctx, "manual")
  │
  ├─▶ 申请 advisory lock 7429001
  ├─▶ 读 GlobalConfig、SkuConfig（启用列表）
  ├─▶ Step 1: run_step1() → velocity
  ├─▶ Step 2: run_step2() → sale_days, inventory（含 in_transit 来自已推送建议）
  ├─▶ Step 3: compute_country_qty() → country_qty
  ├─▶ Step 4: compute_total() → total_qty（按 SKU 循环）
  ├─▶ Step 5: explain_country_qty_split() → warehouse_breakdown
  ├─▶ Step 6: compute_timing_for_sku() → t_purchase, urgent
  ├─▶ _archive_active()：旧 draft/partial 归档
  └─▶ INSERT Suggestion + SuggestionItem[]（批量）
  │
  ▼
Worker 标记 status=success, finished_at
  │
  ▼
前端 TaskProgress 轮询到 terminal → 触发 onDone → 刷新建议单列表
```

### 场景 2：推送采购单到赛狐

```
用户勾选条目，点击"推送"
  │
  ▼
POST /api/suggestions/{id}/push, body={ item_ids: [...] }
  │
  ▼
api/suggestion.py: push_items() → enqueue_task("push_saihu", dedupe="push_saihu#<id>")
  │
  ▼
Worker 执行 pushback/purchase.py
  │
  ├─▶ 加载 GlobalConfig.default_purchase_warehouse_id
  ├─▶ 检查所有条目都有 commodity_id（否则 PushBlockedError）
  ├─▶ 构造 saihu_items = [{commodityId, num}]
  │
  ▼
SaihuClient.post("/api/purchase/create.json", items)
  │
  ├─▶ tenacity 重试（SaihuRateLimited / SaihuNetworkError）
  ├─▶ 获取 token（单飞）
  ├─▶ 生成签名 + 注入公共参数
  ├─▶ 等待 limiter（1 QPS）
  └─▶ httpx POST → 解析响应 → 返回 PO 号
  │
  ▼
UPDATE suggestion_item SET push_status='pushed', saihu_po_number=..., pushed_at=now()
  │
  ▼
_refresh_suggestion_counts() → 更新 Suggestion.status 为 partial/pushed
  │
  ▼
Worker 标记 task 成功 → 前端 TaskProgress 触发刷新
```

### 场景 3：去重机制防止重复补货

```
用户推送了 SKU-A 的建议 → push_status=pushed, country_breakdown={US: 100, GB: 50}
  │
  ▼（时间推移，赛狐还没同步回来新的在途数据）
用户再次触发补货计算
  │
  ▼
Step 2: load_in_transit(db, sku_list)
  │
  └─▶ 查询 SuggestionItem WHERE push_status='pushed' AND suggestion.status != 'archived' 
      AND suggestion.created_at >= now() - 90 days
      │
      └─▶ 汇总 country_breakdown → {(SKU-A, US): 100, (SKU-A, GB): 50}
  │
  ▼
merge_inventory() 将在途加入 total，inventory[SKU-A][US].total 增加 100
  │
  ▼
Step 3: country_qty 计算时已把已推送量视为库存一部分
  │
  ▼
新建议中 SKU-A 的 US/GB 补货量减少 100 和 50，避免重复
```

---

## 6. 数据库设计

### 6.1 核心表

| 表 | 职责 | 关键约束 |
|---|---|---|
| `global_config` | 全局配置单行表；包含 `target_days`、`buffer_days`、`lead_time_days`、`calc_cron`、`scheduler_enabled`、`restock_regions` 等参数，其中 `restock_regions=[]` 表示全部国家参与补货计算 | `CHECK id=1` |
| `sku_config` | SKU 级覆盖配置（enabled, lead_time_days）；商品同步/初始化会为全部 SKU 建立配置，但仅 active + matched 的 SKU 自动启用 | PK `commodity_sku` |
| `warehouse` | 仓库主数据（type, country, replenish_site） | `type IN (-1,0,1,2,3)` |
| `shop` | 店铺（同步自赛狐） | — |
| `product_listing` | 在线商品列表（店铺 × 站点粒度） | 索引 `(commodity_sku, marketplace_id)` |
| `order_header` | 订单头 | `purchase_date DESC` 索引 |
| `order_item` | 订单行（含 quantity_shipped, refund_num） | — |
| `order_detail` | 订单详情（含地址） | — |
| `order_detail_fetch_log` | 详情拉取日志（自动同步防重复拉取；人工补拉可绕过） | — |
| `inventory_snapshot_latest` | 当前库存快照 | 唯一键 `(commodity_sku, warehouse_id)` |
| `in_transit_record` / `in_transit_item` | 出库记录（赛狐同步）；包含 `warehouseId`、`updateTime`、`type/typeName`、`commodityId`、`perPurchase` 等展示字段 | — |
| `zipcode_rule` | 邮编 → 仓库分配规则 | `operator_enum` CHECK 约束；`operator String(10)`，`compare_value String(200)` |
| `suggestion` | 补货建议单头 | `status IN ('draft','partial','pushed','archived','error')` |
| `suggestion_item` | 补货建议条目 | `push_status IN ('pending','pushed','push_failed','blocked')`，索引 urgent 部分索引 |
| `task_run` | 任务队列 + 执行日志 | 部分唯一索引 `dedupe_key WHERE status IN ('pending','running')` |
| `sync_state` | 同步任务状态 | — |
| `api_call_log` | 赛狐 API 调用日志 | — |
| `access_token_cache` | 赛狐 token 缓存 | PK id=1 |
| `login_attempt` | 登录尝试日志（防暴力） | — |

#### `zipcode_rule`（邮编→仓库规则）

- 字段：`country`, `prefix_length`, `value_type`, `operator`, `compare_value`, `warehouse_id`, `priority`
- `operator ∈ {=, !=, >, >=, <, <=, contains, not_contains, between}`（`String(10)`，CHECK 约束 `operator_enum`）
- `compare_value: String(200)`，`between` 运算符承载一段或多段 `lo-hi` 闭区间（多段逗号分隔，最多 20 段，`hi ≤ 10^prefix_length - 1`）
- 按 `(country, priority)` 升序匹配，首条命中返回仓库；全部未命中归"未知仓"
- **tied 配置**：把多条规则的 `priority` 填相同值即触发同优先级均分；tied 定义基于命中该具体订单的最低 priority 批次，跨 operator 通用

### 6.2 关键索引策略

**部分索引**（Partial Index）：
- `uq_task_run_active_dedupe`：仅对活跃任务去重，历史任务不占索引空间
- `ix_task_run_pending_priority`：Worker 调度查询加速
- `ix_task_run_lease`：Reaper 扫描过期任务加速
- `ix_suggestion_item_urgent`：仅索引紧急条目

**JSONB 字段**：`country_breakdown`、`warehouse_breakdown`、`t_purchase`、`velocity_snapshot`、`sale_days_snapshot`、`global_config_snapshot`、`allocation_snapshot`、`payload`。其中 `global_config_snapshot` 会保留 `restock_regions` 等配置快照。当前仅整体读取，不查 JSONB 内部字段，无需 GIN 索引。

### 6.3 迁移管理

- 工具：Alembic（命名规范配置在 `db/base.py` 的 NAMING_CONVENTION）
- 位置：`backend/alembic/versions/`
- 命名：`YYYYMMDD_HHMM_description.py`
- 执行：`alembic upgrade head`（容器启动时由 deploy 脚本自动执行）

---

## 7. 部署架构

### 7.1 Docker Compose 拓扑

```
┌──────────┐
│  Caddy   │ :443  ← HTTPS terminator，Let's Encrypt 自动证书
└────┬─────┘
     │
     ├─────▶ /api/*, /docs, /healthz, /readyz ─▶ ┌──────────┐
     │                                            │ backend  │ :8000
     └─────▶ 其他静态资源 ─▶ ┌────────────┐      │ FastAPI  │
                             │  frontend  │      └─────┬────┘
                             │   nginx    │            │
                             └────────────┘            │
                                                       ▼
                                                 ┌──────────┐
                                                 │    db    │ :5432
                                                 │ Postgres │
                                                 └──────────┘
                                                       ▲
                                                       │
                                            ┌──────────┴──────────┐
                                            │                     │
                                       ┌────┴────┐          ┌─────┴──────┐
                                       │ worker  │          │ scheduler  │
                                       │ 同 FastAPI 镜像   │  同 FastAPI  │
                                       └─────────┘          └────────────┘
```

**资源限制**：
- db: 1GB
- backend: 512MB
- worker: 512MB
- scheduler: 512MB
- frontend (nginx): 256MB
- caddy: 128MB

### 7.2 进程分离策略

后端镜像同一份，通过环境变量决定启用哪些组件：

```env
# backend 实例：只服务 HTTP
PROCESS_ENABLE_WORKER=false
PROCESS_ENABLE_REAPER=false
PROCESS_ENABLE_SCHEDULER=false

# worker 实例：只跑任务
PROCESS_ENABLE_WORKER=true
PROCESS_ENABLE_REAPER=true
PROCESS_ENABLE_SCHEDULER=false

# scheduler 实例：只调度
PROCESS_ENABLE_WORKER=false
PROCESS_ENABLE_REAPER=false
PROCESS_ENABLE_SCHEDULER=true
```

这样可以水平扩展 Worker，Scheduler 保持单例避免重复触发。

### 7.3 部署脚本（deploy/scripts/）

| 脚本 | 用途 |
|---|---|
| `deploy.sh` | 完整部署：验证 env → 备份 → 迁移 → 拉新镜像 → 滚动更新 → smoke check → 失败自动回滚 |
| `migrate.sh` | 仅执行数据库迁移 |
| `pg_backup.sh` | PostgreSQL 备份 |
| `restore_db.sh` | 从备份恢复 |
| `rollback.sh` | 回滚到上一个成功版本 |
| `validate_env.sh` | 验证环境变量完整性 |
| `smoke_check.sh` | 部署后健康检查（/healthz, /readyz） |

### 7.4 健康检查

- **`GET /healthz`**：存活探针，仅返回 `{"status":"ok"}`
- **`GET /readyz`**：就绪探针，检查：
  1. 数据库连通性（`SELECT 1`）
  2. Worker 运行中（或已禁用）
  3. Reaper 运行中（或已禁用）
  4. Scheduler 运行中（或已禁用）

---

## 8. 关键架构决策（ADR 摘要）

### ADR-1：全栈 async

- **决策**：FastAPI + SQLAlchemy async + httpx + asyncio
- **驱动**：系统是 I/O 密集（数据库查询 + 赛狐 HTTP 调用 + 批量文件 I/O），无 CPU bound 任务
- **代价**：开发者需理解 async/await，不能混用同步 I/O

### ADR-2：自研 TaskRun 替代 Celery

- **决策**：`task_run` 表 + 自定义 worker/scheduler/reaper
- **驱动**：
  - 无需 Redis/RabbitMQ broker，减少依赖
  - TaskRun 直接作为领域对象（可查询状态、进度、dedupe、优先级）
  - 进度追踪与任务执行同库同事务，前端轮询简单
- **代价**：放弃 Celery 生态（Flower 监控、重试策略库等）
- **适用范围**：单机或少量机器，超大规模（每秒百 task 以上）才需要真正的分布式队列

### ADR-3：数据库咨询锁而非应用层锁

- **决策**：`pg_advisory_xact_lock` 保证引擎单次运行
- **驱动**：
  - 事务级锁自动释放，无泄漏风险
  - 跨进程生效（同一数据库连接池即可）
  - 非阻塞性（其他查询不受影响）
- **代价**：仅限同一 PostgreSQL 实例

### ADR-4：前端本地分页

- **决策**：数据页一次拉全量（`page_size=5000`），前端做筛选和分页
- **驱动**：
  - 内部用户 1-5 人，数据量有限（订单 < 5000 条）
  - 筛选即时响应无需往返 API
  - 跨页选择实现简单
- **代价**：
  - 数据量增长后会有性能瓶颈
  - 初次加载慢
- **未来演进**：若数据量超过数万条，切换为 server-side 分页 + 虚拟滚动

### ADR-5：PageSectionCard 作为所有页面的统一容器

- **决策**：所有列表页强制使用 `PageSectionCard`（`#title` + `#actions` slot）
- **驱动**：视觉一致性、减少重复 header 代码
- **例外**：
  - `SuggestionDetailView`（详情页 header 复杂，保留原始 `el-card`）
  - `GlobalConfigView` 已迁移

### ADR-6：去重基于已推送建议而非赛狐在途

- **决策**：`load_in_transit` 从 `suggestion_item` 汇总已推送条目，而非查赛狐在途
- **驱动**：
  - 赛狐在途数据有同步延迟（需要下次 sync 才写入本地）
  - 已推送建议单立即可查，0 延迟去重
- **约束**：只考虑近 90 天的已推送建议（避免累积过多历史数据）

---

## 9. 扩展和演进指南

### 9.1 新增一个数据页面

1. **后端**：在 `app/api/data.py` 添加端点（模式参考现有的 `list_orders`）
2. **前端 API**：在 `src/api/data.ts` 添加 TypeScript 接口 + 调用函数
3. **前端页面**：
   - 在 `src/views/data/` 新建 `DataXxxView.vue`
   - 使用 `PageSectionCard` + `#actions` slot 放筛选
   - 用"加载全量 + filteredRows + pagedRows" 模式
   - 用 `formatShortTime`、`formatUpdateTime`、`warehouseTypeLabel` 等共享工具；其中数据页列表里的“同步时间”以及出库记录里的“更新时间/同步时间”统一使用 `formatUpdateTime` 输出 `YYYY-MM-DD HH:mm`
4. **路由**：在 `src/router/index.ts` 添加路由
5. **导航**：在 `src/config/navigation.ts` 添加菜单项

### 9.2 新增一个后台任务

1. 在 `app/tasks/jobs/` 或 `app/sync/` 新建 `xxx_job.py`
2. 用 `@register(JOB_NAME)` 装饰器注册
3. 函数签名：`async def xxx_job(ctx: JobContext) -> None`
4. 在开始/结束调用 `mark_sync_running/success/failed`（如果是 sync 类）
5. 在 `app/tasks/scheduler.py` 的 `_register_jobs` 中添加触发规则
6. 手动触发：调用 `enqueue_task(db, job_name=JOB_NAME, trigger_source="manual")`

### 9.3 新增一个引擎 Step

**不推荐**。当前 6 步流水线已经覆盖所有计算需求，新增 step 会破坏既有快照字段的语义。更推荐的做法：
- **修改现有 step**：在已有 step 内增加逻辑
- **新增独立 job**：例如"补货提醒推送"作为独立 task，读取 `suggestion_item` 后发送通知

### 9.4 新增一个赛狐 API 端点

1. 在 `app/saihu/endpoints/` 新建 `xxx.py`
2. 模式参考 `inventory.py`：
   ```python
   async def list_xxx(page_size: int = 100, ...) -> AsyncIterator[dict]:
       client = get_saihu_client()
       page_no = 1
       while True:
           result = await client.post(ENDPOINT, body)
           for row in result["data"]["rows"]:
               yield row
           if 达到末页: return
           page_no += 1
   ```
3. 如需特殊 QPS，在 `rate_limit.py` 的 `_ENDPOINT_RATE_OVERRIDES` 添加
4. 消费方：sync job 调用此 iterator + 批量 UPSERT

### 9.5 架构约束（Don'ts）

- **不要**在 API 层直接写 SQL，走 ORM 或业务函数
- **不要**在引擎 step 中调用外部 API，step 应是纯 DB/计算
- **不要**在 sync job 中做业务计算，sync 只做"抓取 → 落库"
- **不要**绕过 TaskRun 直接在请求线程中跑长任务
- **不要**在 suggestion_item 已 pushed 后修改其 country_breakdown（已推送是不可变快照）
- **不要**在前端 store 中保存业务数据（仅 auth/sidebar/task），业务数据局部在 view 中

---

## 10. 测试策略

### 10.1 后端

| 层级 | 框架 | 覆盖范围 |
|---|---|---|
| 单元测试 | pytest + pytest-asyncio | 引擎各 step、zipcode_matcher、时区转换、签名生成等纯函数 |
| 集成测试 | pytest + TEST_DATABASE_URL | 健康检查端点（需真实数据库，默认 skip） |

**运行**：`cd backend && pytest`

**关键测试文件**：
- `tests/unit/test_engine_step1.py` ~ `test_engine_step6.py`
- `tests/unit/test_zipcode_matcher.py`
- `tests/unit/test_sign.py`（赛狐签名生成）

### 10.2 前端

| 层级 | 框架 | 覆盖范围 |
|---|---|---|
| 单元测试 | Vitest | API 客户端、工具函数、路由守卫、Pinia store |

**运行**：`cd frontend && npm run test`

---

## 11. 开发工作流

### 11.1 本地启动

```bash
# 1. 数据库
docker compose -f deploy/docker-compose.local.yml up -d

# 2. 后端
cd backend
python -m venv .venv
source .venv/bin/activate  # 或 .venv/Scripts/activate (Windows)
pip install -e ".[dev]"
cp .env.example .env  # 编辑 SAIHU_CLIENT_ID 等
alembic upgrade head
uvicorn app.main:app --reload

# 3. 前端
cd frontend
npm install
npm run dev
```

### 11.2 质量检查

```bash
# 后端
cd backend
ruff check .
black --check .
mypy app
pytest

# 前端
cd frontend
npm run lint
npm run type-check
npm run test
npm run build
```

### 11.3 提交规范

- 小而频繁的提交
- 提交信息使用 conventional commits：`feat:` / `fix:` / `refactor:` / `docs:` / `test:` / `chore:`
- PR 前运行完整的 lint + test + build

---

## 12. 架构治理

### 12.1 一致性维护

- **CLAUDE.md**（项目根）：记录技术栈和最近变更，AI 助手和新成员优先阅读
- **docs/superpowers/specs/**：保留每个重要设计的 spec 文档
- **docs/superpowers/plans/**：保留每次实施计划
- **本文档**：架构层级的真理源（Source of Truth）

### 12.2 架构变更流程

1. 先用 `superpowers:brainstorming` skill 讨论设计
2. 写 spec 到 `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
3. 用户审阅通过
4. 用 `superpowers:writing-plans` 生成可执行计划
5. 用 `superpowers:subagent-driven-development` 执行
6. 每步通过校验后才算验收
7. 更新本架构蓝图（如涉及架构变更）

---

## 附录 A：关键文件速查

| 功能 | 文件 |
|---|---|
| 引擎编排 | `backend/app/engine/runner.py` |
| 任务队列 | `backend/app/tasks/queue.py` |
| Worker 循环 | `backend/app/tasks/worker.py` |
| 调度器 | `backend/app/tasks/scheduler.py` |
| 赛狐客户端 | `backend/app/saihu/client.py` |
| Token 管理 | `backend/app/saihu/token.py` |
| 异常定义 | `backend/app/core/exceptions.py` |
| 时区处理 | `backend/app/core/timezone.py` |
| 路由入口 | `frontend/src/router/index.ts` |
| 主布局 | `frontend/src/components/AppLayout.vue` |
| 设计令牌 | `frontend/src/styles/tokens.scss` |
| 统一页面容器 | `frontend/src/components/PageSectionCard.vue` |

## 附录 B：环境变量速查

**后端** (`backend/.env`)：
```
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
SAIHU_BASE_URL=https://openapi.sellfox.com
SAIHU_CLIENT_ID, SAIHU_CLIENT_SECRET
LOGIN_PASSWORD, JWT_SECRET, JWT_EXPIRES_HOURS=24
PROCESS_ENABLE_WORKER=true
PROCESS_ENABLE_REAPER=true
PROCESS_ENABLE_SCHEDULER=true
WORKER_LEASE_MINUTES=2
WORKER_HEARTBEAT_SECONDS=30
REAPER_INTERVAL_SECONDS=60
```

**前端** (`frontend/.env`)：
```
VITE_API_PROXY_TARGET=http://localhost:8000
```

---

**本架构蓝图应随架构演进同步更新。** 若发现文档与代码实际行为不符，以代码为准并回填文档。
