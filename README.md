# Restock System

跨境电商海外仓补货管理系统。从赛狐（Sellfox）同步店铺、商品、订单、库存数据，通过 6 步规则引擎自动计算各国补货建议，并推送采购单回赛狐。

面向内部小团队（1–5 人），单机 Docker Compose 部署，不对公网直接开放。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11+ / FastAPI 0.115+ / SQLAlchemy 2.0 async / Pydantic 2 / Alembic |
| 任务调度 | APScheduler 3.10+ / 自研 TaskRun 队列（Worker · Reaper · Scheduler 三进程分离） |
| 外部集成 | 赛狐 API（httpx + aiolimiter 限流 + tenacity 重试） |
| 前端 | Vue 3.5 / TypeScript 5.7 / Vite 6 / Pinia 2 / Element Plus 2.9 / ECharts 6 |
| 数据库 | PostgreSQL 16（asyncpg 驱动） |
| 安全 | PyJWT / bcrypt / 速率限制中间件 / JWT ≥ 32 字节强制 |
| 日志 | structlog 结构化日志 + request_id 链路追踪 |
| 部署 | Docker Compose / Caddy 反代 / Nginx 前端静态服务 |
| 测试 | pytest / ruff / mypy / pip-audit / Vitest 4 / ESLint / vue-tsc |
| CI/CD | GitHub Actions（测试 + lint + 镜像构建 + 手动部署） |

## 项目结构

```
restock_system/
├── backend/                # FastAPI 后端
│   ├── app/
│   │   ├── api/            # REST 端点（auth/config/data/metrics/monitor/suggestion/sync/task）
│   │   ├── engine/         # 补货计算引擎（6 步流水线）
│   │   ├── sync/           # 赛狐数据同步（店铺/仓库/商品/订单/库存/出库）
│   │   ├── pushback/       # 采购单推送回赛狐
│   │   ├── saihu/          # 赛狐 HTTP 客户端（限流 + 重试）
│   │   ├── models/         # SQLAlchemy ORM 模型（30+ 表）
│   │   ├── schemas/        # Pydantic DTO
│   │   ├── tasks/          # TaskRun 队列 + worker + reaper + scheduler
│   │   ├── core/           # 异常 / 日志 / 中间件 / 安全
│   │   └── db/             # 数据库连接 + 会话管理
│   ├── alembic/            # 数据库迁移脚本
│   └── tests/              # pytest 测试
├── frontend/               # Vue 3 前端
│   └── src/
│       ├── views/          # 页面（Workspace/Restock/Data/Settings）
│       ├── components/     # 复用组件（PageSectionCard/TablePaginationBar/DashboardCard）
│       ├── api/            # API 客户端
│       ├── stores/         # Pinia 状态管理
│       ├── utils/          # 工具函数（format/warehouse/countries/status/tableSort）
│       ├── router/         # 路由配置 + 鉴权守卫
│       └── styles/         # SCSS 设计系统
├── deploy/                 # 部署相关
│   ├── docker-compose.yml      # 生产编排（db/backend/worker/scheduler/frontend/caddy）
│   ├── docker-compose.dev.yml  # 本地开发全栈编排（db/backend/worker/scheduler/frontend/caddy）
│   ├── Caddyfile               # 生产反代规则
│   ├── Caddyfile.dev           # 开发反代规则
│   └── scripts/                # deploy.sh / pg_backup.sh / rollback.sh / migrate.sh 等
├── docs/                   # 项目文档
│   ├── PROGRESS.md             # 实时进度与变更记录
│   ├── Project_Architecture_Blueprint.md  # 完整架构蓝图
│   ├── deployment.md           # 部署流程详解
│   ├── runbook.md              # 运维故障排查手册
│   └── onboarding.md           # 新成员入门指南
├── specs/                  # 需求规格与任务拆解
├── scripts/                # 统一校验脚本（check.ps1 / check.sh）
├── .github/workflows/      # CI/CD（ci.yml + deploy.yml）
├── AGENTS.md               # 长期协作规则与代码约定
└── CLAUDE.md               # Claude Code 精简指令
```

## 核心功能

### 补货计算引擎（6 步流水线）

| 步骤 | 名称 | 说明 |
|---|---|---|
| Step 1 | Velocity | 加权日均销量（7 天 × 0.5 + 14 天 × 0.3 + 30 天 × 0.2） |
| Step 2 | Sale Days | 可售天数 = (海外库存 + 在途) ÷ velocity；库存聚合 |
| Step 3 | Country Qty | 各国补货量 = 目标天数 × velocity − 当前库存 |
| Step 4 | Total | 汇总各国补货量，扣减国内中心仓库存 + 缓冲天数 |
| Step 5 | Warehouse Split | 按邮编规则将各国补货量分配到具体仓库 |
| Step 6 | Timing | 紧急标志判定（任一有效国家 `sale_days <= lead_time_days` 即为紧急） |

引擎特性：并发保护（`pg_advisory_xact_lock`）、快照追溯（velocity / sale_days / global_config 快照）、补货区域多选过滤。

### 数据同步

从赛狐 API 增量同步：店铺、仓库、在线商品、订单列表/详情、库存快照（90 天保留）、出库记录。支持手动触发和定时自动同步，订单详情保守限流 2 QPS。

### 补货建议管理

- 状态流转：`draft → partial → pushed → archived`（+ `error`）
- 跨页选择、批量编辑、推送到赛狐生成采购单
- 采购单去重（防止重复推送）、历史记录可删除但推送后保留追溯

### Dashboard 信息总览

- 快照缓存机制 + 自动刷新
- 各国缺货风险分布（紧急 / 临近 / 安全三分类）
- 急需补货 SKU 展示、补货量国家分布图表

### 任务队列系统

三进程分离架构：
- **Backend**：仅处理 HTTP 请求
- **Worker**：执行 TaskRun 任务（同步、计算、推送），支持去重和重试
- **Scheduler**：APScheduler 定时将任务入队，调度器开关持久化到 `global_config`

### 全局配置

补货参数（缓冲天数、目标天数、提前期）、补货区域多选、调度器开关与 cron 表达式实时生效。

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 20+
- PostgreSQL 16
- Docker & Docker Compose

### 本地开发

**1. 启动数据库**

```bash
cp deploy/.env.dev.example deploy/.env.dev
docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml up -d db
```

**2. 后端**

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -e ".[dev]"

cp .env.example .env          # 编辑 DATABASE_URL、SAIHU_CLIENT_*、LOGIN_PASSWORD、JWT_SECRET
alembic upgrade head          # 初始化数据库

uvicorn app.main:app --reload # http://localhost:8000
```

**3. 前端**

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

### 生产部署

```bash
cd deploy
cp .env.example .env          # 配置域名、密钥、数据库密码
bash scripts/deploy.sh        # 自动完整流程：备份 → 迁移 → 构建 → smoke check → 回滚保护
```

容器资源限制：db 1G / backend + worker + scheduler 各 512M / frontend 256M / caddy 128M。

详细部署文档见 [`docs/deployment.md`](docs/deployment.md)。

## 环境变量

### 后端（`backend/.env`）

| 变量 | 说明 | 必填 |
|---|---|---|
| `DATABASE_URL` | PostgreSQL 连接串（`postgresql+asyncpg://...`） | 是 |
| `SAIHU_BASE_URL` | 赛狐 API 地址 | 是 |
| `SAIHU_CLIENT_ID` | 赛狐应用 ID | 是 |
| `SAIHU_CLIENT_SECRET` | 赛狐应用密钥 | 是 |
| `LOGIN_PASSWORD` | 登录密码（明文，首次启动自动 hash） | 是 |
| `JWT_SECRET` | JWT 签名密钥（≥ 32 字节） | 是 |
| `APP_DOCS_ENABLED` | 是否启用 OpenAPI 文档（默认 `false`） | 否 |
| `PROCESS_ENABLE_WORKER` | 启用 worker 进程 | 否（docker-compose 控制） |
| `PROCESS_ENABLE_SCHEDULER` | 启用 scheduler 进程 | 否（docker-compose 控制） |

### 前端（`frontend/.env`）

| 变量 | 说明 | 默认 |
|---|---|---|
| `VITE_API_PROXY_TARGET` | 后端代理地址 | `http://localhost:8000` |

## 常用命令

```bash
# ── 后端 ──
cd backend
pytest                            # 运行测试
pytest --cov --cov-report=html    # 覆盖率报告
ruff check .                      # lint 检查
mypy app                          # 类型检查
pip-audit                         # 依赖安全审计
alembic upgrade head              # 数据库迁移

# ── 前端 ──
cd frontend
npm run dev                       # 开发服务器
npm run build                     # 生产构建（含类型检查）
npm run test                      # 单元测试
npm run test:coverage             # 覆盖率报告
npm run lint                      # ESLint
npx vue-tsc --noEmit              # 类型检查
npm audit --audit-level=high      # 依赖安全审计

# 回到仓库根目录再执行后续命令
cd ..

# ── 统一校验（CI 等价） ──
bash scripts/check.sh             # Linux/macOS
powershell scripts/check.ps1      # Windows

# ── 部署运维 ──
docker compose -f deploy/docker-compose.yml ps          # 容器状态
docker compose -f deploy/docker-compose.yml logs -f backend  # 后端日志
bash deploy/scripts/pg_backup.sh                         # 数据库备份
bash deploy/scripts/restore_db.sh                        # 数据库恢复
bash deploy/scripts/rollback.sh                          # 回滚上一次部署
```

## 页面导航

| 分类 | 页面 | 路径 |
|---|---|---|
| HOME | 信息总览 | `/workspace` |
| RESTOCK | 补货发起 | `/restock/current` |
| | 历史记录 | `/restock/history` |
| DATA | 店铺 / 仓库 / 商品 | `/data/shops` `/data/warehouses` `/data/products` |
| | 订单 / 库存 / 出库记录 | `/data/orders` `/data/inventory` `/data/out-records` |
| SETTINGS | 数据同步 / 同步日志 | `/settings/sync` `/settings/sync-log` |
| | 全局参数 / 邮编规则 | `/settings/global` `/settings/zipcode` |
| | 接口监控 / 性能监控 | `/settings/api-monitor` `/settings/performance` |

## 健康检查

| 端点 | 类型 | 说明 |
|---|---|---|
| `GET /healthz` | 存活探针 | 轻量级，进程存活即返回 |
| `GET /readyz` | 就绪探针 | 含 DB 连接 + worker + reaper + scheduler 状态检查 |

## CI/CD

- **`ci.yml`**：push / PR 自动触发 — 后端 pytest + ruff + mypy + pip-audit，前端 build + test + npm audit，Docker 镜像构建验证
- **`deploy.yml`**：手动触发 — CI 门控通过后 SSH 远程执行 `deploy.sh`，并发控制同时仅一个部署

## 文档索引

| 文档 | 说明 |
|---|---|
| [`AGENTS.md`](AGENTS.md) | 仓库协作规则、代码约定、文档同步协议 |
| [`docs/PROGRESS.md`](docs/PROGRESS.md) | 当前进度与最近变更 |
| [`docs/Project_Architecture_Blueprint.md`](docs/Project_Architecture_Blueprint.md) | 完整架构蓝图 |
| [`docs/deployment.md`](docs/deployment.md) | 部署流程与环境变量详解 |
| [`docs/runbook.md`](docs/runbook.md) | 运维故障排查手册 |
| [`docs/onboarding.md`](docs/onboarding.md) | 新成员入门指南 |

## License

Internal use only.
