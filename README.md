<div align="center">
  <img src="frontend/public/favicon.svg" alt="Restock System" width="72" height="72" />

  <h1>Restock System</h1>

  <p>
    <strong>跨境电商海外仓补货管理系统</strong>
  </p>

  <p>
    赛狐只读同步 · 6 步补货计算 · 建议编辑 · Excel 导出 · 不可变快照
  </p>
</div>

---

Restock System 面向 1-5 人小团队，帮助业务人员从赛狐（Sellfox）同步订单、商品、库存和出库数据，按规则引擎生成采购 / 补货建议，并通过 Excel 导出与快照版本化完成交付。

> [!NOTE]
> 当前主链路为“赛狐只读同步 → 补货建议计算 → 建议编辑 → Excel 导出 + Snapshot 版本化”。系统不回写赛狐；生产环境通过 Docker Compose + Caddy + TLS 对公网开放。

## 功能特性

- **赛狐只读同步**：同步店铺、仓库、商品、订单、库存、出库记录，支持限流、重试、去重与任务进度追踪。
- **6 步补货引擎**：计算加权销量、可售天数、国家补货量、SKU 级采购量、仓库分配、紧急标记与补货日期。
- **采购 / 补货拆分**：采购建议按 SKU 聚合，补货建议按国家和仓库拆分，支持独立导出与独立快照版本。
- **建议编辑与校验**：支持编辑采购量、国家补货量和仓库分配，并按业务规则重新校验汇总关系。
- **Excel 导出 + 快照追溯**：导出时冻结 `suggestion_snapshot` / `suggestion_snapshot_item`，历史结果可重复下载。
- **后台任务队列**：基于 PostgreSQL 的 TaskRun 队列，提供去重、租约、心跳、僵尸回收和进度回写。
- **安全与权限**：JWT 登录、RBAC 权限矩阵、生产环境默认关闭 OpenAPI 文档，API 错误统一 JSON 化。

## 技术栈

| 层级 | 技术 |
|---|---|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy 2.0 async / Alembic / Pydantic v2 |
| 前端 | Vue 3 / TypeScript 5 / Vite 6 / Pinia / Vue Router / Element Plus / ECharts |
| 调度 | APScheduler + 自研 TaskRun 队列（Worker / Reaper / Scheduler） |
| 数据库 | PostgreSQL 16（asyncpg） |
| 外部集成 | 赛狐 API（httpx + aiolimiter + tenacity） |
| 部署 | Docker Compose + Caddy + Nginx |
| 测试与质量 | pytest / ruff / black / mypy / Vitest / ESLint / vue-tsc |

## 架构概览

```text
Frontend (Vue SPA)
  │ HTTP + JWT
  ▼
Backend (FastAPI)
  ├─ api/        REST 端点与权限校验
  ├─ engine/     6 步补货计算引擎
  ├─ sync/       赛狐数据同步
  ├─ services/   Excel 导出与业务服务
  ├─ tasks/      TaskRun 队列、Worker、Reaper、Scheduler
  ├─ saihu/      赛狐 HTTP 客户端、限流、重试、Token 管理
  └─ models/     SQLAlchemy ORM
  │
  ▼
PostgreSQL 16
```

生产环境采用单机 Docker Compose，包含 `backend`、`worker`、`scheduler`、`frontend`、`db`、`caddy` 六个服务。后端镜像通过进程角色环境变量拆分 API、任务执行和定时入队，避免请求线程执行长任务。

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 20 LTS（CI 等价环境）
- PostgreSQL 16
- Docker 24+ 与 Docker Compose v2.20+

### 1. 启动本地数据库

```bash
cp deploy/.env.dev.example deploy/.env.dev
docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml up -d db
```

本地 PostgreSQL 默认暴露在宿主机 `5433`，不会占用常见的 `5432`。

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

后端默认访问地址：`http://localhost:8000`。

> [!IMPORTANT]
> `.env` 至少需要配置数据库连接、`LOGIN_PASSWORD`、`JWT_SECRET` 和赛狐凭证。生产环境 `JWT_SECRET` 必须为高强度随机值，且 `APP_DOCS_ENABLED` 默认应保持 `false`。

### 3. 启动前端

```bash
cd frontend
npm ci
npm run dev
```

前端默认访问地址：`http://localhost:5173`，开发服务器会代理 `/api/*` 到后端。

### 4. 本地全栈容器验证

```bash
cp deploy/.env.dev.example deploy/.env.dev
docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml up -d db
docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml run --rm backend alembic upgrade head
docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml up -d
```

完整本地入口：`http://localhost:8088`。

## 常用命令

### 后端

```bash
cd backend
pytest
ruff check .
mypy app
alembic upgrade head
```

### 前端

```bash
cd frontend
npm run dev
npm run build
npm run test
npm run lint
```

### 统一检查

```bash
powershell scripts/check.ps1    # Windows
bash scripts/check.sh           # Linux / macOS
```

## 项目结构

```text
restock_system/
├── backend/              # FastAPI 后端
├── frontend/             # Vue 3 + Vite 前端
├── deploy/               # Docker Compose、Caddy、部署脚本
├── docs/                 # 架构、进度、部署、运维、入门文档
├── scripts/              # 统一检查脚本
├── .github/              # CI/CD workflows
├── AGENTS.md             # 仓库协作规则
└── CLAUDE.md             # 精简技术栈与协作摘要
```

## 核心业务流

1. **同步数据**：通过赛狐 API 只读同步业务数据到本地 PostgreSQL。
2. **生成建议**：业务人员选择需求截止日期，后端通过 TaskRun 队列异步运行补货引擎。
3. **编辑校验**：在前端调整采购量、国家补货量和仓库分配，后端统一校验。
4. **导出快照**：选择待导出条目，生成采购 / 补货 Excel，并冻结不可变快照。
5. **历史追溯**：按建议单、快照版本和导出日志追踪历史交付结果。

## 部署概览

生产部署使用 Docker Compose + Caddy：

- Caddy 负责 TLS 终止、反向代理和访问日志。
- Frontend 使用 Nginx 托管静态资源。
- Backend、Worker、Scheduler 使用同一后端镜像按角色拆分。
- PostgreSQL 数据、Caddy 证书、导出文件和备份文件挂载到 `deploy/data/`。

首次部署与发布流程详见 [`docs/deployment.md`](docs/deployment.md)，故障排查详见 [`docs/runbook.md`](docs/runbook.md)。

## 文档入口

- [`docs/PROGRESS.md`](docs/PROGRESS.md)：已交付能力与近期重大变更
- [`docs/Project_Architecture_Blueprint.md`](docs/Project_Architecture_Blueprint.md)：架构蓝图与关键设计决策
- [`docs/onboarding.md`](docs/onboarding.md)：本地开发、常用命令与协作约定
- [`docs/deployment.md`](docs/deployment.md)：生产部署与本地全栈容器验证
- [`docs/runbook.md`](docs/runbook.md)：运维检查、告警与故障处理
- [`AGENTS.md`](AGENTS.md)：长期协作规则与文档同步协议
