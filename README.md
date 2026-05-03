<div align="center">
  <img src="frontend/public/favicon.svg" alt="Restock System" width="72" height="72" />

  <h1>Restock System</h1>

  <p><strong>跨境电商海外仓补货管理系统</strong></p>

  <p>赛狐只读同步 · 6 步补货计算 · 建议编辑 · Excel 导出 · 不可变快照</p>
</div>

---

Restock System 面向 1-5 人小团队，用于把赛狐（Sellfox）业务数据同步到本地系统，按补货规则生成采购 / 补货建议，并以 Excel 文件和不可变快照完成交付与追溯。

> [!NOTE]
> 当前主链路是“赛狐只读同步 → 补货建议计算 → 建议编辑 → Excel 导出 + Snapshot 版本化”。系统不回写赛狐；生产环境通过 Docker Compose + Caddy + TLS 对公网开放。

## 功能特性

- **赛狐只读同步**：同步店铺、仓库、商品、订单、库存和出库记录，支持限流、重试、去重和任务进度追踪。
- **自动调度与手动触发**：APScheduler 定时入队，TaskRun 队列执行长任务；前端提供手动同步、任务状态和同步日志视图。
- **6 步补货引擎**：计算加权销量、可售天数、国家补货量、SKU 级采购量、仓库分配、紧急标记和补货日期。
- **采购 / 补货拆分**：采购建议按 SKU 聚合，补货建议按国家和仓库拆分，支持独立导出与独立快照版本。
- **建议编辑与业务校验**：支持调整采购量、国家补货量、仓库分配，并由后端统一校验汇总关系。
- **Excel 导出 + 快照追溯**：导出时冻结 `suggestion_snapshot` / `suggestion_snapshot_item`，历史结果可重复下载。
- **后台运营控制台**：覆盖信息总览、数据同步、采补发起、历史记录、全局参数、权限配置、监控和排障入口。
- **安全与权限**：JWT 登录、RBAC 权限矩阵、生产环境默认关闭 OpenAPI 文档，API 错误统一 JSON 化。

## 技术栈

| 层级 | 技术 |
|---|---|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy 2.0 async / Alembic / Pydantic v2 |
| 前端 | Vue 3.5 / TypeScript 5.7 / Vite 6 / Pinia 2 / Vue Router 4 / Element Plus 2.13 / ECharts 6 |
| 调度 | APScheduler + 自研 TaskRun 队列（Worker / Reaper / Scheduler） |
| 数据库 | PostgreSQL 16（asyncpg） |
| 外部集成 | 赛狐 API（httpx + aiolimiter + tenacity） |
| 部署 | Docker Compose + Caddy + Nginx |
| 测试与质量 | pytest / ruff / black / mypy / Vitest 4 / ESLint / vue-tsc |

## 架构概览

```text
Browser
  │
  ▼
Frontend SPA (Vue + Vite, Nginx in production)
  │ HTTP + JWT
  ▼
Backend API (FastAPI)
  ├─ api/        REST 端点、鉴权和权限校验
  ├─ sync/       赛狐只读同步
  ├─ engine/     6 步补货计算引擎
  ├─ services/   Excel 导出与业务服务
  ├─ tasks/      TaskRun 队列、Worker、Reaper、Scheduler
  ├─ saihu/      赛狐 HTTP 客户端、限流、重试、Token 管理
  └─ models/     SQLAlchemy ORM
  │
  ▼
PostgreSQL 16
```

生产环境采用单机 Docker Compose，包含 `caddy`、`frontend`、`backend`、`worker`、`scheduler`、`db` 六个服务。`backend`、`worker`、`scheduler` 使用同一后端镜像，通过进程角色环境变量拆分 API、任务执行和定时入队，避免请求线程执行长任务。

## 快速开始

### 环境要求

| 依赖 | 最低版本 | 推荐版本 |
|---|---|---|
| Python | 3.11 | 3.12 |
| Node.js | 18 | 20 LTS（CI 等价校验容器） |
| PostgreSQL | 16 | 16 |
| Docker | 24.0 | 最新 |
| Docker Compose | v2.20 | 最新 |

### 1. 启动本地数据库

```bash
cp deploy/.env.dev.example deploy/.env.dev
docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml up -d db
```

本地 PostgreSQL 默认暴露在宿主机 `5433`，避免占用常见的 `5432`。

### 2. 启动后端

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

后端默认地址是 `http://localhost:8000`。

> [!IMPORTANT]
> `backend/.env` 至少需要配置数据库连接、`LOGIN_PASSWORD`、`JWT_SECRET` 和赛狐凭证。生产环境 `JWT_SECRET` 必须使用高强度随机值，且 `APP_DOCS_ENABLED` 应保持 `false`。

### 3. 启动前端

```bash
cd frontend
npm ci
npm run dev
```

前端默认地址是 `http://localhost:5173`，开发服务器会代理 `/api/*` 到后端。

### 4. 首次业务流程

1. 打开 `http://localhost:5173`，使用 `backend/.env` 中的 `LOGIN_PASSWORD` 登录。
2. 进入“数据同步”，触发店铺、商品、库存、订单等同步任务。
3. 进入“商品”，从商品同步结果初始化 SKU 配置。
4. 进入“采补发起”，选择需求截止日期并生成补货建议。
5. 等待 TaskRun 任务完成后，查看和编辑采购 / 补货建议。
6. 勾选待导出条目，生成采购 / 补货 Excel 快照。

## 本地全栈容器验证

当需要验证镜像构建、数据库迁移、Caddy 反代和前后端联通时，使用本地全栈 Compose：

```bash
cp deploy/.env.dev.example deploy/.env.dev
docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml up -d db
docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml run --rm backend alembic upgrade head
docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml up -d
```

本地全栈入口是 `http://localhost:8088`。本地容器使用 `deploy/Caddyfile.dev` 和独立数据目录，不与生产配置混用。

## 常用命令

### 后端

```bash
cd backend
pytest
ruff check .
black .
mypy app
alembic upgrade head
```

### 前端

```bash
cd frontend
npm run dev
npm run build
npm run test
npm run test:coverage
npm run lint
```

### CI 等价校验

```bash
powershell scripts/check.ps1    # Windows：后端 pytest + ruff，前端 Docker Node 20 校验
bash scripts/check.sh           # Linux / macOS
```

仅验证前端在 CI 等价环境中的构建和测试时：

```bash
powershell scripts/frontend-check.ps1
bash scripts/frontend-check.sh
```

前端校验脚本固定使用 Docker `node:20-alpine` 执行 `npm ci && npm run build && npm run test:coverage`，避免本机 Node 版本差异影响结果。

## 项目结构

```text
restock_system/
├── backend/              # FastAPI 后端
│   ├── app/api/          # REST 端点
│   ├── app/engine/       # 补货计算引擎
│   ├── app/sync/         # 赛狐数据同步
│   ├── app/tasks/        # 任务队列、worker、scheduler
│   ├── app/services/     # Excel 导出与业务服务
│   └── tests/            # pytest 测试
├── frontend/             # Vue 3 + Vite 前端
│   └── src/
│       ├── views/        # 页面组件
│       ├── components/   # 复用组件
│       ├── api/          # API 客户端
│       ├── stores/       # Pinia 状态
│       └── utils/        # 共享工具
├── deploy/               # Docker Compose、Caddy、部署脚本
├── docs/                 # 架构、进度、部署、运维、入门文档
├── scripts/              # 统一检查脚本
├── .github/              # CI/CD workflows
├── AGENTS.md             # 仓库协作规则
└── CLAUDE.md             # 精简技术栈与协作摘要
```

## 核心业务流

```text
赛狐只读同步
  → 补货建议计算（6 步引擎）
  → 建议编辑与后端校验
  → 采购 / 补货 Excel 导出
  → 不可变快照版本化
  → 历史追溯与重复下载
```

补货引擎只基于数据库和配置计算，不直接调用外部 API；同步任务只负责“抓取 → 落库”，不做业务计算。长任务全部通过 TaskRun 队列执行，并由 worker 心跳、租约和 reaper 机制保护状态一致性。

## 部署概览

生产部署使用 Docker Compose + Caddy：

- Caddy 负责 TLS 终止、反向代理和访问日志。
- Frontend 使用 Nginx 托管静态资源。
- Backend、Worker、Scheduler 使用同一后端镜像按角色拆分。
- PostgreSQL 数据、Caddy 证书、导出文件和备份文件挂载到 `deploy/data/`。
- GitHub Actions 可发布 GHCR 镜像并通过 `Deploy` workflow 手动部署指定分支、tag 或 commit。

首次部署与发布流程详见 [`docs/deployment.md`](docs/deployment.md)，故障排查详见 [`docs/runbook.md`](docs/runbook.md)。

## 文档入口

- [`docs/PROGRESS.md`](docs/PROGRESS.md)：已交付能力与近期重大变更
- [`docs/user-guide.md`](docs/user-guide.md)：业务用户使用说明书
- [`docs/Project_Architecture_Blueprint.md`](docs/Project_Architecture_Blueprint.md)：架构蓝图与关键设计决策
- [`docs/onboarding.md`](docs/onboarding.md)：本地开发、常用命令与协作约定
- [`docs/deployment.md`](docs/deployment.md)：生产部署与本地全栈容器验证
- [`docs/runbook.md`](docs/runbook.md)：运维检查、告警与故障处理
- [`AGENTS.md`](AGENTS.md)：长期协作规则与文档同步协议
