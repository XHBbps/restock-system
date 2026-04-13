# 新成员入门指南

> 配套文档：[架构蓝图](Project_Architecture_Blueprint.md) · [部署指南](deployment.md) · [运维手册](runbook.md)

---

## 1. 项目概览

**Restock System** 是一套跨境电商海外仓补货管理系统，从赛狐（Sellfox）同步业务数据，通过规则引擎计算各国补货建议，并推送采购单回赛狐。

### 快速阅读路径

1. **本文件** — 本地开发环境和常用命令
2. **[Project_Architecture_Blueprint.md](Project_Architecture_Blueprint.md)** — 分层架构、组件职责、关键决策、扩展指南
3. **[PROGRESS.md](PROGRESS.md)** — 已交付能力和近期变更
4. **[deployment.md](deployment.md)** — 生产部署流程
5. **[runbook.md](runbook.md)** — 运维故障排查

### 技术栈速览

| 层级 | 技术 |
|---|---|
| 前端 | Vue 3.5 / TypeScript 5.7 / Pinia 2 / Element Plus 2.9 / Vite 6 / ECharts 6 |
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy 2.0 async / Pydantic 2 / APScheduler / httpx / structlog |
| 数据库 | PostgreSQL 16 (asyncpg 驱动) / Alembic 迁移 |
| 部署 | Docker Compose / Caddy / Nginx |

---

## 2. 项目结构

```
restock_system/
├── backend/          # FastAPI 后端
│   ├── app/
│   │   ├── api/      # REST 端点
│   │   ├── engine/   # 补货计算引擎（6 步流水线）
│   │   ├── sync/     # 赛狐数据同步
│   │   ├── pushback/ # 采购单回写
│   │   ├── saihu/    # 赛狐 HTTP 客户端
│   │   ├── models/   # SQLAlchemy ORM
│   │   ├── schemas/  # Pydantic DTO
│   │   ├── tasks/    # 任务队列 + 调度器 + worker + reaper
│   │   ├── core/     # 异常/日志/中间件/安全
│   │   └── db/       # 数据库连接
│   ├── alembic/      # 数据库迁移
│   └── tests/        # pytest 测试
├── frontend/         # Vue 3 前端
│   └── src/
│       ├── views/    # 页面组件
│       ├── components/  # 复用组件
│       ├── api/      # API 客户端
│       ├── stores/   # Pinia 状态
│       ├── utils/    # 工具函数
│       ├── router/   # 路由 + 鉴权守卫
│       ├── styles/   # SCSS 设计系统
│       └── config/   # 导航配置
├── deploy/           # Docker Compose + 部署脚本
├── docs/             # 文档（本文件所在位置）
├── specs/            # 需求和契约
├── scripts/          # 统一检查脚本（check.ps1 / check.sh）
└── .github/          # CI/CD workflows
```

---

## 3. 环境要求

| 依赖 | 最低版本 | 推荐版本 |
|---|---|---|
| Python | 3.11 | 3.12 |
| Node.js | 18 | 20 LTS |
| PostgreSQL | 16 | 16 |
| Docker | 24.0 | 最新 |
| Docker Compose | v2.20 | 最新 |

---

## 4. 本地开发启动

### 4.1 启动本地数据库

```bash
docker compose -f deploy/docker-compose.local.yml up -d
```

> `docker-compose.local.yml` 只启动 PostgreSQL（5432 端口），不启动业务服务。业务服务在本地原生运行便于调试。

### 4.2 后端

```bash
cd backend

# 创建虚拟环境
python -m venv .venv

# 激活
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

# 安装依赖（含 dev 工具）
pip install -e ".[dev]"

# 安装 pre-commit hooks
pre-commit install

# 配置环境变量
cp .env.example .env          # Windows 用 copy .env.example .env
# 编辑 .env，至少填写 SAIHU_CLIENT_ID / SAIHU_CLIENT_SECRET

# 初始化数据库
alembic upgrade head

# 启动（自动 reload）
uvicorn app.main:app --reload
# 访问 http://localhost:8000/docs 查看 API
```

### 4.3 前端

```bash
cd frontend
npm ci                        # 或 npm install
npm run dev
# 访问 http://localhost:5173
```

前端 dev server 会自动代理 `/api/*` 请求到 `http://localhost:8000`（通过 `vite.config.ts` 的 proxy 配置）。

### 4.4 首次使用流程

1. 打开 http://localhost:5173 → 登录（用 `.env` 中的 `LOGIN_PASSWORD`）
2. 进入"数据同步"页 → 触发同步（店铺 / 商品 / 库存 / 订单）
3. 进入"商品"页 → 点击"从商品同步初始化"创建 sku_config
4. 进入"补货发起"页 → 点击"生成补货建议"
5. 等待引擎完成（TaskProgress 会自动轮询）
6. 查看生成的建议单，选择条目推送

---

## 5. 常用开发命令

### 5.1 后端

```bash
cd backend

# 类型检查
mypy app

# 代码检查
ruff check .

# 格式化
black .

# 测试
pytest                        # 全部测试
pytest tests/unit/            # 仅单元测试
pytest -k test_engine         # 按名称过滤
pytest -v --tb=short          # 详细输出

# 数据库迁移
alembic upgrade head          # 应用所有迁移
alembic revision --autogenerate -m "描述"  # 生成新迁移
alembic current               # 查看当前版本
alembic history               # 查看历史
```

### 5.2 前端

```bash
cd frontend

# 开发服务器
npm run dev

# 类型检查
npx vue-tsc --noEmit
# 或
npm run type-check

# 代码检查
npm run lint
npm run lint:fix

# 格式化
npm run format

# 测试
npm run test
npm run test:coverage

# 生产构建
npm run build
```

### 5.3 统一检查（跨前后端）

**Windows**:
```powershell
.\scripts\check.ps1
```

**Linux/macOS**:
```bash
bash scripts/check.sh
```

---

## 6. 关键环境变量

### 6.1 后端（`backend/.env`）

| 变量 | 说明 | 示例 |
|---|---|---|
| `DATABASE_URL` | PostgreSQL 连接串 | `postgresql+asyncpg://user:pass@localhost:5432/restock` |
| `APP_ENV` | 环境名（`development`/`production`） | `development` |
| `APP_DOCS_ENABLED` | 是否开放 `/docs` | `true` |
| `SAIHU_BASE_URL` | 赛狐 API 地址 | `https://openapi.sellfox.com` |
| `SAIHU_CLIENT_ID` | 赛狐应用 ID | — |
| `SAIHU_CLIENT_SECRET` | 赛狐应用密钥 | — |
| `LOGIN_PASSWORD` | 登录密码（首次启动自动 hash） | — |
| `JWT_SECRET` | JWT 签名密钥（64 字节随机） | — |
| `JWT_EXPIRES_HOURS` | Token 有效期 | `24` |
| `PROCESS_ENABLE_WORKER` | 本进程是否跑 worker | `true`（本地） |
| `PROCESS_ENABLE_REAPER` | 本进程是否跑 reaper | `true`（本地） |
| `PROCESS_ENABLE_SCHEDULER` | 本进程是否跑 scheduler | `true`（本地） |

本地开发推荐 3 个 `PROCESS_ENABLE_*` 都设为 `true`，单进程调试方便。

### 6.2 前端（`frontend/.env`）

| 变量 | 说明 | 默认 |
|---|---|---|
| `VITE_API_PROXY_TARGET` | 后端地址 | `http://localhost:8000` |

---

## 7. 开发约定

### 7.1 代码风格

| 层 | 工具 |
|---|---|
| Python | `black`（格式化）+ `ruff`（lint）+ `mypy`（类型） |
| TypeScript/Vue | `prettier` + `eslint` + `vue-tsc` |

**pre-commit hook** 会在 commit 前自动运行检查，安装一次即可：

```bash
cd backend && pre-commit install
```

### 7.2 提交规范

Conventional Commits：

- `feat:` 新功能
- `fix:` Bug 修复
- `refactor:` 重构（不改变功能）
- `docs:` 文档
- `test:` 测试
- `chore:` 杂项（依赖、配置、构建等）

### 7.3 开发工作流

架构级变更 / 新功能：

1. 用 `superpowers:brainstorming` skill 讨论设计
2. 产出 spec 到 `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`
3. 用户审阅通过
4. 用 `superpowers:writing-plans` 生成实施计划到 `docs/superpowers/plans/`
5. 用 `superpowers:subagent-driven-development` 执行
6. 每步通过校验后才算验收
7. 若涉及架构变化，同步更新 `Project_Architecture_Blueprint.md`

### 7.4 前端共享工具（必读）

新建列表页时**必须**复用以下工具，避免重复代码：

| 工具 | 用途 |
|---|---|
| `@/components/PageSectionCard` | 统一页面容器（`title` + `#actions` slot） |
| `@/components/TablePaginationBar` | 统一分页条 |
| `@/components/SkuCard` | 商品展示 |
| `@/components/StatusTag` | 状态标签 |
| `@/components/TaskProgress` | 长任务进度展示 |
| `@/components/sync/OrderDetailFetchAction` | 订单页“详情获取”动作组件，统一封装回溯天数、触发逻辑与任务冲突提示 |
| `@/utils/format` | `formatShortTime` / `formatDateTime` / `formatUpdateTime` / `formatDetailTime` / `clampPage`；其中 `formatUpdateTime` 统一输出 `YYYY-MM-DD HH:mm`，用于数据页“同步时间”和出库记录“更新时间/同步时间” |
| `@/utils/warehouse` | `warehouseTypeLabel` / `warehouseTypeTag` |
| `@/utils/countries` | `COUNTRY_OPTIONS` 国家下拉选项 |
| `@/utils/status` | 状态元数据映射 |
| `@/utils/tableSort` | 本地排序工具 |
| `@/utils/monitoring` | 监控名称映射（接口/资源中文化）、分位点工具、任务反馈文案 |

**数据页模式**（所有列表页必须遵循）：

```typescript
// 1. 一次拉全量
const rows = ref<T[]>([])
async function reload() {
  const resp = await listData({ page: 1, page_size: 5000 })
  rows.value = resp.items
  page.value = 1
}

// 2. 前端筛选
const filteredRows = computed(() => { ... })

// 3. 本地分页
const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredRows.value.slice(start, start + pageSize.value)
})
```

### 7.5 后端开发约定

- **API 层不写 SQL**，走 ORM 或业务函数
- **引擎 step 不调用外部 API**，保持纯 DB + 计算
- **Sync job 不做业务计算**，只做"抓取 → 落库"
- **长任务走 TaskRun 队列**，不在请求线程执行
- **异常用 `BusinessError` 子类**，自动映射为 JSON
- **日志用 `structlog.get_logger`**，request_id 自动绑定

---

## 8. 健康检查

| 端点 | 作用 |
|---|---|
| `GET /healthz` | 进程存活 |
| `GET /readyz` | 数据库 + 后台服务就绪 |

本地开发时，如果 `readyz` 返回 `worker: not_running`，检查 `PROCESS_ENABLE_WORKER=true`。

---

## 9. CI/CD

- **CI**：`.github/workflows/ci.yml` — lint + type check + test
- **CD**：`.github/workflows/deploy.yml` — 自动部署流程

---

## 10. 下一步

- 阅读 [架构蓝图](Project_Architecture_Blueprint.md) 了解完整架构
- 阅读 [项目进度](PROGRESS.md) 了解近期变更
- 跑一遍首次使用流程（本文件第 4.4 节）
- 找一个简单的 bug 或 feature 小切入

欢迎加入！
