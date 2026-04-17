<div align="center">
  <img src="frontend/public/favicon.svg" alt="Restock System" width="72" height="72" />

  <h1>Restock System</h1>

  <p>
    <strong>跨境电商海外仓补货管理系统</strong>
  </p>

  <p>
    从赛狐（Sellfox）同步业务数据 · 6 步规则引擎自动计算补货建议 · 推送采购单回赛狐
  </p>
</div>

---

面向内部小团队（1–5 人）的补货工具：一次拉全量数据、统一前端筛选、后台任务队列异步执行计算与推送。单机 Docker Compose 部署，不对公网直接开放。

> [!NOTE]
> 本仓库属于 **内部工具**，规模约束下刻意放弃了分布式/多租户设计。若你需要对外 SaaS 化，请先阅读 [`docs/Project_Architecture_Blueprint.md`](docs/Project_Architecture_Blueprint.md) 了解当前边界。

## 功能特性

- **6 步补货引擎**：加权销量 → 可售天数 → 各国补货量 → 总采购量 → 仓库分配 → 紧急判定
- **赛狐只读同步**：店铺 / 仓库 / 商品 / 订单 / 库存 / 出库 全链路，限流 + 重试 + 去重
- **采购单推送**：建议单 `draft → partial → pushed → archived` 状态机，支持跨页选择与批量
- **三进程分离**：`backend`（HTTP）· `worker`（任务执行）· `scheduler`（定时入队），互不阻塞
- **TaskRun 队列**：dedupe_key 去重、心跳租约、Reaper 僵尸回收、精确进度回写
- **信息总览快照**：Dashboard 按 SKU+国家统一风险口径，缓存表 + 手动刷新任务
- **可追溯快照**：`velocity_snapshot` / `sale_days_snapshot` / `global_config_snapshot` 随建议单持久化
- **RBAC 权限矩阵**：作业级 + 操作级权限，`require_permission()` 统一收口

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11+ · FastAPI 0.115 · SQLAlchemy 2.0 async · Pydantic 2 · Alembic |
| 前端 | Vue 3.5 · TypeScript 5.7 · Vite 6 · Pinia · Element Plus 2.9 · ECharts 6 |
| 调度 | APScheduler 3.10 + 自研 TaskRun 队列（Worker · Reaper · Scheduler） |
| 数据库 | PostgreSQL 16（asyncpg） |
| 外部集成 | 赛狐 API（httpx + aiolimiter + tenacity） |
| 安全 | PyJWT（HS256，≥ 32 字节）· bcrypt · 速率限制中间件 |
| 日志 | structlog 结构化 + `request_id` 链路追踪 |
| 部署 | Docker Compose · Caddy 反代 · Nginx 前端静态 |
| 测试 | pytest · ruff · mypy · pip-audit · Vitest 4 · ESLint · vue-tsc |
| CI/CD | GitHub Actions（CI 门控 + GHCR 镜像 + SSH 部署） |

## 环境要求

- **Python** 3.11 或更高
- **Node.js** 20 或更高
- **PostgreSQL** 16
- **Docker** 与 Docker Compose

## 快速开始

### 1. 启动数据库

```bash
cp deploy/.env.dev.example deploy/.env.dev
docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml up -d db
```

### 2. 启动后端

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate         # Windows
# source .venv/bin/activate    # macOS / Linux

pip install -e ".[dev]"
cp .env.example .env           # 填入 DATABASE_URL / SAIHU_* / LOGIN_PASSWORD / JWT_SECRET
alembic upgrade head

uvicorn app.main:app --reload  # http://localhost:8000
```

> [!IMPORTANT]
> `JWT_SECRET` 必须 ≥ 32 字节，否则 `PyJWT` 会抛出 `InsecureKeyLengthWarning` 并导致启动失败。生成示例：`python -c "import secrets; print(secrets.token_urlsafe(48))"`。

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev                    # http://localhost:5173
```

> [!TIP]
> 首次登录密码即为 `LOGIN_PASSWORD` 明文，后端启动时自动 hash 入库。

### 4. 本地全栈容器验证（可选）

```bash
docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml up -d
# 访问 http://localhost:8088
```

该链路与生产 Compose 完全解耦，容器名统一为 `restock-dev-*`，数据目录独立。

## 项目结构

```
restock_system/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/                # REST 端点（auth/config/data/metrics/monitor/suggestion/sync/task）
│   │   ├── engine/             # 补货计算引擎（6 步流水线 + runner）
│   │   ├── sync/               # 赛狐同步（shop/warehouse/product/order/inventory/out_records）
│   │   ├── pushback/           # 采购单推送回赛狐
│   │   ├── saihu/              # 赛狐 HTTP 客户端（限流 + 重试）
│   │   ├── tasks/              # TaskRun 队列 + worker + reaper + scheduler
│   │   ├── models/             # SQLAlchemy ORM（30+ 表）
│   │   ├── schemas/            # Pydantic DTO
│   │   ├── core/               # 异常 / 日志 / 中间件 / 安全
│   │   └── db/                 # 数据库连接与会话管理
│   ├── alembic/                # 数据库迁移
│   └── tests/                  # pytest（单元 + 集成）
├── frontend/                   # Vue 3 前端
│   └── src/
│       ├── views/              # 页面（Workspace / Restock / Data / Settings）
│       ├── components/         # 复用组件（PageSectionCard / TablePaginationBar / Dashboard*）
│       ├── api/                # API 客户端
│       ├── stores/             # Pinia（auth / sidebar 等）
│       ├── utils/              # 共享工具（format / warehouse / countries / status / tableSort）
│       ├── router/             # 路由 + 鉴权守卫
│       └── styles/             # SCSS 设计系统（shadcn Zinc 对齐）
├── deploy/                     # 部署配置
│   ├── docker-compose.yml          # 生产编排
│   ├── docker-compose.dev.yml      # 本地全栈编排
│   ├── Caddyfile / Caddyfile.dev   # 反代规则
│   └── scripts/                    # deploy / migrate / pg_backup / restore / rollback
├── docs/                       # 项目文档（事实源 + 蓝图）
├── specs/                      # 需求规格与任务拆解
├── scripts/                    # 统一校验（check.sh / check.ps1）
├── .github/workflows/          # CI（ci.yml）+ 部署（deploy.yml）
├── AGENTS.md                   # 协作规则与代码约定
└── CLAUDE.md                   # Claude Code 精简指令
```

## 核心功能

### 补货计算引擎

`backend/app/engine/runner.py` 编排 6 步流水线，全程在事务内持 `pg_advisory_xact_lock(7429001)` 防并发覆盖：

| 步骤 | 名称 | 说明 |
|---|---|---|
| Step 1 | Velocity | 加权日均销量：7 日 × 0.5 + 14 日 × 0.3 + 30 日 × 0.2 |
| Step 2 | Sale Days | 可售天数 = (海外库存 + 在途) ÷ velocity；库存聚合 |
| Step 3 | Country Qty | 各国补货量 = 目标天数 × velocity − 当前库存 |
| Step 4 | Total | 汇总各国补货量，扣减国内中心仓库存 + 缓冲天数 |
| Step 5 | Warehouse Split | 按邮编规则将各国补货量分配到具体仓库 |
| Step 6 | Timing | 紧急标志：任一有效国家 `sale_days <= lead_time_days` |

引擎写入的 `velocity_snapshot` / `sale_days_snapshot` / `global_config_snapshot` 为 JSONB 快照，可追溯历史判定。

### 数据同步

| 任务 | 触发方式 | 说明 |
|---|---|---|
| `sync_product_listing` / `sync_inventory` / `sync_out_records` | 间隔触发（`sync_interval_minutes`） | 短周期增量同步 |
| `sync_order_list` / `sync_order_detail` | 间隔触发 | 订单详情 2 QPS 保守抓取、瞬时错误自动重试 |
| `sync_warehouse` | 每日 03:30 Asia/Shanghai | 仓库基础信息 |
| `daily_archive` | 每日 02:00 | 库存快照 90 天保留归档 |
| `calc_engine` | cron（默认 08:00） | 自动生成补货建议单 |

### 任务队列

三进程解耦，`task_run` 表作为状态机：

```
backend (HTTP only) ──▶ enqueue_task(dedupe_key)
                              │
                              ▼
scheduler (APScheduler) ──▶ task_run  ◀── worker (2s poll + 30s heartbeat)
                              │                    │
                              └── reaper (60s) ────┘
```

- **dedupe_key** 偏序唯一索引，避免重复入队
- **lease** 2 分钟过期，Reaper 回收僵尸任务
- **SKIPPED** 状态记录被去重的调度尝试，保留审计
- **精确进度**：按条数或 `totalPage` 回写 `current_step / step_detail`

### 建议单管理

- 状态流转：`draft → partial → pushed → archived`（异常回落 `error`）
- **跨页选择**：`selectedIds` 数组跨分页保持，支持全选筛选后的所有条目
- **编辑口径**：`total_qty` 与 `country_breakdown` 脱钩；仓内分量之和必须等于国家补货量；`urgent` 按 SKU 提前期重新判定
- **推送去重**：`push_saihu#<suggestion_id>#<sorted_item_ids>`，防重复采购单
- **历史删除**：`draft / partial / error / archived` 可删，`pushed` 保留追溯

## 环境变量

### 后端（`backend/.env`）

| 变量 | 说明 | 必填 |
|---|---|---|
| `DATABASE_URL` | PostgreSQL 连接串（`postgresql+asyncpg://...`） | 是 |
| `SAIHU_BASE_URL` | 赛狐 API 地址 | 是 |
| `SAIHU_CLIENT_ID` | 赛狐应用 ID | 是 |
| `SAIHU_CLIENT_SECRET` | 赛狐应用密钥 | 是 |
| `LOGIN_PASSWORD` | 登录密码明文（首次启动自动 hash） | 是 |
| `JWT_SECRET` | JWT 签名密钥（≥ 32 字节） | 是 |
| `APP_DOCS_ENABLED` | 是否启用 OpenAPI 文档 | 否（默认 `false`） |
| `PROCESS_ENABLE_WORKER` | 启用 worker 进程 | 否（Compose 控制） |
| `PROCESS_ENABLE_REAPER` | 启用 reaper（worker/scheduler 冗余） | 否（Compose 控制） |
| `PROCESS_ENABLE_SCHEDULER` | 启用 scheduler 进程 | 否（Compose 控制） |

### 前端（`frontend/.env`）

| 变量 | 说明 | 默认 |
|---|---|---|
| `VITE_API_PROXY_TARGET` | 开发模式后端代理 | `http://localhost:8000` |

## 常用命令

```bash
# ── 后端 ──
cd backend
pytest                              # 全部测试
pytest --cov --cov-report=html      # 覆盖率报告
ruff check .                        # lint
mypy app                            # 类型检查
pip-audit                           # 依赖审计
alembic upgrade head                # 迁移到最新

# ── 前端 ──
cd frontend
npm run dev                         # 开发服务器
npm run build                       # 生产构建（含 vue-tsc）
npm run test                        # Vitest
npm run lint                        # ESLint

# ── 统一校验（CI 等价） ──
bash scripts/check.sh               # Linux / macOS
powershell scripts/check.ps1        # Windows

# ── 运维 ──
docker compose -f deploy/docker-compose.yml ps
docker compose -f deploy/docker-compose.yml logs -f backend
bash deploy/scripts/pg_backup.sh    # 备份
bash deploy/scripts/rollback.sh     # 回滚
```

## 生产部署

```bash
cd deploy
cp .env.example .env                # 填入域名 / 密钥 / DB 密码
bash scripts/deploy.sh              # 备份 → 迁移 → 拉镜像 → smoke check → 失败回滚
```

| 服务 | 内存限制 | 说明 |
|---|---|---|
| db | 1 G | PostgreSQL 16 |
| backend / worker / scheduler | 512 M × 3 | 三进程分离 |
| frontend | 256 M | Nginx 非 root 8080 |
| caddy | 128 M | TLS + 反代 |

> [!WARNING]
> 执行迁移前务必确认已暂停 APScheduler（`scheduler_enabled=false`），否则 DELETE 会与并发 UPSERT 抢锁。完整流程与故障排查见 [`docs/runbook.md`](docs/runbook.md)。

## 健康检查

| 端点 | 类型 | 说明 |
|---|---|---|
| `GET /healthz` | 存活探针 | 进程存活即返回 200 |
| `GET /readyz` | 就绪探针 | 按角色检查 DB + worker + reaper + scheduler |
| `GET /api/metrics/prometheus` | 指标端点 | 队列深度 + 进程状态（需 `monitor:view`，Caddy 仅内网放行） |

## CI/CD

- **`ci.yml`**：push / PR / `v*` tag 自动触发 — 后端 `pytest + ruff + mypy + pip-audit`，前端 `build + test + npm audit`，Docker 镜像构建验证，并按 `main`/`master`/tag 推送 GHCR
- **`deploy.yml`**：手动触发或 `v*` tag — CI 门控通过后 SSH 远程执行 `deploy.sh`，按真实 commit SHA 派生 `IMAGE_TAG=sha-<commit>`，并发控制同时仅一个部署

## 文档索引

| 文档 | 说明 |
|---|---|
| [`AGENTS.md`](AGENTS.md) | 仓库协作规则、代码约定、文档同步协议 |
| [`docs/PROGRESS.md`](docs/PROGRESS.md) | 已交付能力与近期变更 |
| [`docs/Project_Architecture_Blueprint.md`](docs/Project_Architecture_Blueprint.md) | 完整架构蓝图（分层 / 组件 / ADR） |
| [`docs/deployment.md`](docs/deployment.md) | 部署流程与环境变量详解 |
| [`docs/runbook.md`](docs/runbook.md) | 运维故障排查手册 |
| [`docs/onboarding.md`](docs/onboarding.md) | 新成员入门指南 |

---

<sub>Internal use only · 面向 1–5 人团队的补货工具</sub>
