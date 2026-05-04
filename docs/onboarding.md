# 新成员入门指南

> 配套文档：[架构蓝图](Project_Architecture_Blueprint.md) · [部署指南](deployment.md) · [运维手册](runbook.md)

---

## 1. 项目概览

**Restock System** 是一套跨境电商海外仓补货管理系统，从赛狐（Sellfox）同步业务数据，通过规则引擎计算各国采购/补货建议，最终以 Excel 导出 + 不可变快照版本化交付给业务人员（Plan A 后已取代旧赛狐写入链路）。

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
├── scripts/          # 统一检查脚本（check.ps1 / check.sh）
└── .github/          # CI/CD workflows
```

---

## 3. 环境要求

| 依赖 | 最低版本 | 推荐版本 |
|---|---|---|
| Python | 3.11 | 3.12 |
| Node.js | 18 | 20 LTS（CI 等价校验容器） |
| PostgreSQL | 16 | 16 |
| Docker | 24.0 | 最新 |
| Docker Compose | v2.20 | 最新 |

---

## 4. 本地开发启动

> 前端分为两条运行通道：
> - **本机开发通道**：继续使用本机 Node 跑 `npm run dev`，便于日常改页面
> - **CI 等价校验通道**：统一走 `scripts/frontend-check.*`，固定使用 Docker `node:20-alpine`
>
> 如果本机 Node 不是 20，也不需要强制切换；但请不要再用本机 Node 的 `build/test:coverage` 结果判断 CI 是否能通过。

### 4.1 方式 A：原生开发（推荐日常调试）

```bash
cp deploy/.env.dev.example deploy/.env.dev
docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml up -d db
```

> `docker-compose.dev.yml` 是唯一保留的本地容器入口。日常原生开发只启动其中的 `db` 服务（宿主机端口 5433），业务服务在本地原生运行便于调试。

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

> 日常开发默认只要求 `npm run dev` 可用；若需要构建、覆盖率测试或 CI 等价验证，请使用第 4.6 节的容器化校验入口。

### 4.4 首次使用流程

1. 打开 http://localhost:5173 → 登录（用 `.env` 中的 `LOGIN_PASSWORD`）
2. 进入"数据同步"页 → 触发同步（店铺 / 商品 / 库存 / 订单）
3. 进入"商品"页 → 点击"从商品同步初始化"创建 sku_config
4. 进入"补货发起"页 → 点击"生成补货建议"
5. 等待引擎完成（TaskProgress 会自动轮询）
6. 查看并编辑生成的建议单，按需导出采购 / 补货 Excel 快照

### 4.5 方式 B：本地全栈容器验证

当需要验证“镜像构建 → 数据库迁移 → Caddy 反代 → 前后端联通”的完整容器链路时，使用全栈 Compose：

```bash
# 1. 准备本地环境变量
cp deploy/.env.dev.example deploy/.env.dev

# 2. 启动数据库
docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml up -d db

# 3. 执行迁移
docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml run --rm backend alembic upgrade head

# 4. 启动全栈
docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml up -d

# 5. 访问
# 前端: http://localhost:8088
# docs: http://localhost:8088/docs
```

补充说明：

- `deploy/.env.dev` 默认提供 `PIP_INDEX_URL=https://pypi.org/simple`；若本机访问官方源较慢，可自行覆盖 `PIP_INDEX_URL`，并按需补充 `PIP_TRUSTED_HOST`
- 全栈 Compose 使用独立项目名 `restock-dev`，不会影响生产 `deploy/docker-compose.yml`
- PostgreSQL 对宿主机暴露 `5433`，避免占用本地原生开发常用的 `5432`
- 容器名固定为 `restock-dev-*`，因此 `docker ps` 不会再出现 Compose 自动追加的 `-1`
- 停止环境：`docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml down`

### 4.6 前端 CI 等价校验

当需要验证“前端在 GitHub CI / Node 20 环境下是否可通过”时，不要直接依赖本机 Node，请使用仓库内置脚本：

**Windows**：
```powershell
.\scripts\frontend-check.ps1
```

**Linux/macOS**：
```bash
bash scripts/frontend-check.sh
```

说明：

- 脚本固定使用 Docker `node:20-alpine`
- 容器内执行 `npm ci && npm run build && npm run test:coverage`
- 依赖安装写入 Docker volume，不污染宿主机 `frontend/node_modules`
- 若 Docker 不可用，脚本会直接失败并提示，而不是回退到不稳定的本机环境

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

# 开发服务器（本机开发通道）
npm run dev

# 类型检查（本机可直接执行）
npx vue-tsc --noEmit
# 或
npm run type-check

# 代码检查（本机可直接执行）
npm run lint
npm run lint:fix

# 格式化
npm run format

# 测试（仅本机快速调试；不作为 CI 等价口径）
npm run test

# 生产构建（仅本机快速调试；不作为 CI 等价口径）
npm run build
```

前端 **CI 等价校验** 统一使用：

```bash
# Windows
.\scripts\frontend-check.ps1

# Linux/macOS
bash scripts/frontend-check.sh
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

当前统一检查口径为：

- 后端：继续使用宿主机 Python 原生执行
- 前端：自动切换为 Docker Node 20 容器执行 `build + test:coverage`

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
| `JWT_SECRET` | JWT 签名密钥（至少 32 字节，建议 64 字节随机值） | — |
| `JWT_EXPIRES_HOURS` | Token 有效期 | `24` |
| `PROCESS_ENABLE_WORKER` | 本进程是否跑 worker | `true`（本地） |
| `PROCESS_ENABLE_REAPER` | 本进程是否跑 reaper | `true`（本地） |
| `PROCESS_ENABLE_SCHEDULER` | 本进程是否跑 scheduler | `true`（本地） |

本地开发推荐 3 个 `PROCESS_ENABLE_*` 都设为 `true`，单进程调试方便。

### 6.2 前端（`frontend/.env`）

| 变量 | 说明 | 默认 |
|---|---|---|
| `VITE_API_PROXY_TARGET` | 后端地址 | `http://localhost:8000` |

### 6.3 部署冒烟检查（`deploy/.env`）

| 变量 | 说明 | 默认 |
|---|---|---|
| `SMOKE_BASE_URL` | 覆盖 `deploy/scripts/smoke_check.sh` 的检查入口 | `APP_BASE_URL` |
| `SMOKE_RESOLVE_LOCAL` | 生产发布时是否将 `APP_DOMAIN` 解析到 `127.0.0.1` 后检查 | `true` |

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

1. 先讨论设计，明确范围、取舍和验收口径
2. 如需落盘设计材料，使用当前任务明确指定的位置
3. 用户审阅通过
4. 生成实施计划
5. 按计划执行
6. 每步通过校验后才算验收
7. 若涉及架构变化，同步更新 `Project_Architecture_Blueprint.md`

### 7.4 前端共享工具（必读）

新建列表页时**必须**复用以下工具，避免重复代码：

| 工具 | 用途 |
|---|---|
| `@/components/PageSectionCard` | 统一页面容器（`title` + `#actions` slot） |
| `@/components/MobileRecordList` | 移动端卡片列表外壳，桌面表格与手机卡片共用同一份数据源 |
| `@/components/TablePaginationBar` | 统一分页条 |
| `@/components/SkuCard` | 商品展示 |
| `@/components/StatusTag` | 状态标签 |
| `@/components/TaskProgress` | 长任务进度展示 |
| `@/composables/useResponsive` | 统一判断手机 / 平板视口，优先用于页面级响应式切换 |
| `@/utils/format` | `formatShortTime` / `formatDateTime` / `formatUpdateTime` / `formatDetailTime` / `clampPage`；其中 `formatUpdateTime` 统一输出 `YYYY-MM-DD HH:mm`，用于数据页“同步时间”和出库记录“更新时间/同步时间” |
| `@/utils/warehouse` | `warehouseTypeLabel` / `warehouseTypeTag` |
| `@/utils/countries` | `COUNTRY_OPTIONS` 内置国家兜底与 `getCountryLabel()` 展示映射；新建国家下拉优先调用 `GET /api/config/country-options`，接口不可用时再降级到内置选项 |
| `@/utils/status` | 状态元数据映射 |
| `@/utils/tableSort` | 本地排序工具 |
| `@/utils/monitoring` | 监控名称映射（接口/资源中文化）、分位点工具、任务反馈文案 |
| `@/utils/storage` | localStorage 安全读取；JSON 损坏或结构异常时自动清理脏数据并回退默认值 |

页面与导航配置约定：

- `@/config/appPages` 是主页面路由/导航真理源，统一维护 `path`、`title`、`permission`、`icon`、懒加载组件
- `@/router/index.ts` 与 `@/config/navigation.ts` 都应从 `appPages` 派生，避免再手写第二份菜单/路由定义
- 登录页、403/404、建议详情、legacy redirect 等特殊路由仍放在 `router/index.ts` 单独维护

**数据页模式**（高增长列表默认遵循）：

```typescript
// 1. 仅保存当前页
const rows = ref<T[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)

// 2. 筛选、排序、分页参数统一下推到后端
async function reload() {
  const resp = await listData({
    page: page.value,
    page_size: pageSize.value,
    ...filters,
    ...sortState.value,
  })
  rows.value = resp.items
  total.value = resp.total
}
```

- 订单、历史记录、商品、库存、出库记录等可能持续增长的页面必须使用服务端分页 / 筛选。
- 库存页如需保留“按仓库展开”交互，优先复用 `/api/data/inventory/warehouse-groups` 的仓库分组分页接口。
- 店铺、仓库等低增长基础数据页可以保留轻量分页，但不要再为大数据页新增 `page_size=5000` 的前端本地筛选模式。
- 需要兼顾手机端时，优先保留桌面端 `el-table`，再用 `MobileRecordList` 叠加卡片视图；不要为同一接口再做一套移动专用 API。

基础配置页面：

| 页面 | 路由 | 权限 | 说明 |
|---|---|---|---|
| 全局参数 | `/settings/global` | `config:view` / `config:edit` | 补货参数、EU 合并、生成开关 |
| 邮编规则 | `/settings/zipcode` | `config:view` / `config:edit` | 国家 + 邮编前缀到仓库分配规则 |
| 映射规则 | `/settings/sku-mapping-rules` | `config:view` / `config:edit` | 商品 SKU 与库存包裹 SKU 的组装规则 |

映射规则导入模板固定为一行一个组件，列名必须为：`商品SKU`、`库存SKU`、`组件数量`、`启用`、`备注`。同一商品 SKU 的多行组成同一条规则；`启用` 支持 `是/否`、`true/false`、`1/0`；导入整批校验，任一行存在空 SKU、非法数量、重复库存 SKU 或库存 SKU 已归属其他规则时，本批次不写入。

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
