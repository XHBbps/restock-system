# Restock System

跨境电商海外仓补货管理系统。从赛狐（Sellfox）同步店铺、商品、订单、库存数据，通过规则引擎自动计算各国补货建议，并推送采购单回赛狐。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy 2.0 (async) / Alembic |
| 前端 | Vue 3 / TypeScript 5 / Element Plus / Vite |
| 数据库 | PostgreSQL 16 (asyncpg) |
| 部署 | Docker Compose / Caddy / Nginx |

## 项目结构

```
restock_system/
├── backend/          # FastAPI 后端
│   ├── app/
│   │   ├── api/      # REST 端点（auth, config, data, suggestion, sync, monitor）
│   │   ├── engine/   # 补货计算引擎（6 步流水线）
│   │   ├── sync/     # 赛狐数据同步（店铺/仓库/商品/订单/库存/出库）
│   │   ├── pushback/ # 采购单推送
│   │   ├── saihu/    # 赛狐 API 客户端
│   │   ├── models/   # SQLAlchemy ORM 模型
│   │   ├── schemas/  # Pydantic DTO
│   │   ├── tasks/    # 后台任务队列 + 调度器
│   │   ├── core/     # 异常/日志/中间件/安全
│   │   └── db/       # 数据库连接
│   ├── alembic/      # 数据库迁移
│   └── tests/        # pytest 测试
├── frontend/         # Vue 3 前端
│   └── src/
│       ├── views/    # 页面组件
│       ├── components/
│       ├── api/      # API 客户端
│       ├── stores/   # Pinia 状态
│       ├── utils/    # 工具函数
│       └── styles/   # SCSS 设计系统
├── deploy/           # Docker Compose + 部署脚本
├── docs/             # 文档
└── specs/            # 需求规格
```

## 核心功能

### 补货计算引擎（6 步流水线）

1. **Step 1 — Velocity**：基于近 30 天订单计算各 SKU 各国的日均销售速率
2. **Step 2 — Sale Days**：结合海外库存 + 在途数量，计算当前库存可销天数
3. **Step 3 — Country Qty**：`补货量 = 目标天数 × velocity − 当前库存`，按国家计算
4. **Step 4 — Total**：汇总各国补货量，扣减国内中心仓库存
5. **Step 5 — Warehouse Split**：根据邮编规则将各国补货量分配到具体仓库
6. **Step 6 — Timing**：计算建议采购日和发货日

### 数据同步

从赛狐 API 增量同步：店铺、仓库、在线商品、订单列表、订单详情、库存快照、出库记录。

### 采购推送

将补货建议推送到赛狐生成采购单，支持自动重试。

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- PostgreSQL 16
- Docker & Docker Compose（部署用）

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

cp .env.example .env          # 编辑数据库连接和赛狐密钥
alembic upgrade head          # 初始化数据库

uvicorn app.main:app --reload # http://localhost:8000/docs
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
cp .env.example .env          # 配置域名、密钥等
bash scripts/deploy.sh        # 包含备份、迁移、健康检查
```

## 环境变量

### 后端（`backend/.env`）

| 变量 | 说明 | 示例 |
|---|---|---|
| `DATABASE_URL` | PostgreSQL 连接串 | `postgresql+asyncpg://user:pass@localhost:5432/restock` |
| `SAIHU_BASE_URL` | 赛狐 API 地址 | `https://openapi.sellfox.com` |
| `SAIHU_CLIENT_ID` | 赛狐应用 ID | — |
| `SAIHU_CLIENT_SECRET` | 赛狐应用密钥 | — |
| `LOGIN_PASSWORD` | 登录密码（明文，首次启动自动 hash） | — |
| `JWT_SECRET` | JWT 签名密钥 | — |

### 前端（`frontend/.env`）

| 变量 | 说明 | 默认 |
|---|---|---|
| `VITE_API_PROXY_TARGET` | 后端代理地址 | `http://localhost:8000` |

## 常用命令

```bash
# 后端
cd backend
pytest                        # 运行测试
ruff check .                  # 代码检查
alembic upgrade head          # 数据库迁移

# 前端
cd frontend
npm run dev                   # 开发服务器
npm run build                 # 生产构建
npx vue-tsc --noEmit          # 类型检查

# 部署
docker compose -f deploy/docker-compose.yml ps     # 容器状态
docker compose -f deploy/docker-compose.yml logs -f backend  # 后端日志
bash deploy/scripts/pg_backup.sh                    # 数据库备份
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

- `GET /healthz` — 存活探针（轻量级）
- `GET /readyz` — 就绪探针（含数据库和后台服务检查）
