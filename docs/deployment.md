# 部署指南

> 配套文档：[架构蓝图](Project_Architecture_Blueprint.md) · [运维手册](runbook.md)

---

## 0. 首次部署（Day-0）

> 仅在全新服务器上执行一次。后续更新走 `deploy.sh`。

### 前提条件

- Ubuntu 22.04+ / Debian 12+ 云服务器（2C4G 起步）
- 已配置 SSH 登录
- 已将域名 DNS 解析到服务器 IP（Caddy 自动签发 TLS 证书需要）

### 步骤

```bash
# 1. 登录服务器，clone 仓库
ssh user@your-server
git clone https://github.com/XHBbps/restock-system.git
cd restock-system

# 2. 运行初始化脚本（检查 Docker、建目录、生成 .env、装 cron）
bash deploy/scripts/init_server.sh

# 3. 编辑 .env 填入实际配置
vim deploy/.env
# 必填：DB_PASSWORD, JWT_SECRET, LOGIN_PASSWORD, SAIHU_CLIENT_ID, SAIHU_CLIENT_SECRET, APP_DOMAIN

# 4. 首次部署
bash deploy/scripts/deploy.sh

# 5. 验证（Caddy TLS 证书签发可能需要 10-30 秒）
sleep 30
curl -sf https://your-domain.com/healthz
```

### 部署后检查清单

```
[ ] curl /healthz 返回 {"status":"ok"}
[ ] curl /readyz 返回 {"status":"ok"}
[ ] 浏览器打开 https://your-domain.com 可见登录页
[ ] 使用默认密码登录成功
[ ] 全局参数页可正常加载
[ ] deploy/data/backup/ 下次日 03:00 后有备份文件
```

---

## 0.5 本地全栈容器验证

> 用于本机验证镜像、迁移、反向代理和前后端联通；**不替代**云服务器正式发布流程。

### 目标

- 在本机用 Docker Compose 跑完整 6 服务
- 验证后端镜像、Alembic 迁移、Caddy 本地反代与前端静态资源
- 保持生产部署文件 `deploy/docker-compose.yml` 不混入本地端口和 HTTP 配置

### 步骤

```bash
# 1. 复制本地环境变量样例
cp deploy/.env.dev.example deploy/.env.dev

# 2. 启动本地 PostgreSQL（宿主机端口 5433）
docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml up -d db

# 3. 执行数据库迁移
docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml run --rm backend alembic upgrade head

# 4. 启动完整服务栈
docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml up -d

# 5. 验证
curl -sf http://localhost:8088/healthz
curl -sf http://localhost:8088/readyz
```

### 约定

- 本地入口统一为 `http://localhost:8088`
- 本地 Caddy 使用 `deploy/Caddyfile.dev`，不申请 TLS 证书
- 本地 dev 容器名固定为 `restock-dev-db`、`restock-dev-backend`、`restock-dev-worker`、`restock-dev-scheduler`、`restock-dev-frontend`、`restock-dev-caddy`
- 本地数据库卷使用 `deploy/data/pg-dev/`，不与生产卷 `deploy/data/pg/` 共用
- 前端容器健康检查使用 `http://127.0.0.1:8080/`，避免 Alpine `wget` 走 IPv6 `localhost` 导致误判不健康

---

## 1. 目标架构

**单机 Docker Compose 部署**，包含 6 个服务：

```
┌──────────┐
│  Caddy   │ :443  ← HTTPS terminator（Let's Encrypt 自动证书）
└────┬─────┘
     │
     ├─▶ /api/*, /docs, /healthz, /readyz ─▶ ┌──────────┐
     │                                        │ backend  │ :8000 (API only)
     └─▶ 其他请求 ─▶ ┌────────────┐           └────┬─────┘
                     │  frontend  │                │
                     │   nginx    │                │
                     └────────────┘                ▼
                                             ┌──────────┐
                                             │    db    │ :5432
                                             │ Postgres │
                                             └────┬─────┘
                                                  ▲
                                     ┌────────────┼────────────┐
                                     │                         │
                                ┌────┴────┐              ┌─────┴──────┐
                                │ worker  │              │ scheduler  │
                                │ (任务+  │              │ (定时入队) │
                                │  reaper)│              │            │
                                └─────────┘              └────────────┘
```

### 服务角色分离

后端镜像 **同一份**，通过环境变量区分角色：

| 服务 | `PROCESS_ENABLE_WORKER` | `PROCESS_ENABLE_REAPER` | `PROCESS_ENABLE_SCHEDULER` |
|---|---|---|---|
| `backend`（仅 API） | `false` | `false` | `false` |
| `worker`（任务执行 + 僵尸回收） | `true` | `true` | `false` |
| `scheduler`（定时入队） | `false` | `false` | `true` |

Scheduler 保持单例避免重复触发，Worker 可水平扩展。

### 资源限制

定义在 `deploy/docker-compose.yml` 的 `deploy.resources.limits.memory`：

| 服务 | 内存上限 |
|---|---|
| db (PostgreSQL 16) | 1G |
| backend | 512M |
| worker | 512M |
| scheduler | 512M |
| frontend (Nginx) | 256M |
| caddy | 128M |

### 数据目录

- `deploy/data/pg/` — 生产数据库文件
- `deploy/data/pg-dev/` — 本地 dev 全栈数据库文件
- `deploy/data/caddy/` — Caddy 配置和证书
- `deploy/data/caddy-dev/` — 本地 dev Caddy 日志与状态
- `deploy/data/caddy/access.log` — 访问日志

---

## 2. 前置条件

| 项目 | 要求 |
|---|---|
| 操作系统 | Linux (Ubuntu 22.04+ 推荐) |
| Docker Engine | 24.0+ |
| Docker Compose | v2.20+ |
| 代码位置 | 固定目录（例如 `/opt/restock`） |
| 域名 | 已解析到服务器 IP |
| 防火墙 | 开放 `80` / `443` |
| SSL | Caddy 自动申请 Let's Encrypt 证书 |

---

## 3. 环境变量

生产环境复制 `deploy/.env.example` 为 `deploy/.env`，至少填写：

| 变量 | 说明 | 示例 |
|---|---|---|
| `APP_DOMAIN` | 对外域名（Caddy 用） | `restock.example.com` |
| `APP_BASE_URL` | 应用基础 URL | `https://restock.example.com` |
| `APP_DOCS_ENABLED` | 是否开放 `/docs`（生产建议 `false`） | `false` |
| `DB_PASSWORD` | PostgreSQL 密码（强密码） | — |
| `SAIHU_CLIENT_ID` | 赛狐应用 ID | — |
| `SAIHU_CLIENT_SECRET` | 赛狐应用密钥 | — |
| `LOGIN_PASSWORD` | 登录密码（首次启动会自动 hash） | — |
| `JWT_SECRET` | JWT 签名密钥（建议 64 字节随机） | — |

本地 dev 全栈验证复制 `deploy/.env.dev.example` 为 `deploy/.env.dev`；字段名与生产保持一致，但可使用本地占位值。

### 配置维护入口总表

| 类别 | 维护位置 | 作用范围 | 被谁加载 | 说明 |
|---|---|---|---|---|
| 生产部署变量 | `deploy/.env`（由 `deploy/.env.example` 复制） | 云服务器 / 正式发布 | `deploy/docker-compose.yml`、`deploy/scripts/*.sh`、`deploy/Caddyfile` | 生产环境唯一权威入口，域名、密码、赛狐凭证都在这里维护 |
| 本地容器变量 | `deploy/.env.dev`（由 `deploy/.env.dev.example` 复制） | 本机 Docker Compose 全栈 | `deploy/docker-compose.dev.yml`、`deploy/Caddyfile.dev` | 本地容器启动入口；不要和生产 `.env` 混用 |
| 本地后端原生变量 | `backend/.env`（由 `backend/.env.example` 复制） | 本机原生 FastAPI 调试 | `backend/app/config.py` | 仅原生开发使用；不直接驱动 Docker Compose |
| 前端本地变量 | `frontend/.env`（可选，默认参考 `frontend/.env.example`） | 本机 `vite dev server` | `frontend/vite.config.ts` | 当前主要用于 `VITE_API_PROXY_TARGET` |
| 生产服务编排 | `deploy/docker-compose.yml` | 生产容器、资源限制、对外端口 | `docker compose` | 定义 `80/443` 暴露、服务角色、volume、资源限制 |
| 本地服务编排 | `deploy/docker-compose.dev.yml` | 本地容器、端口、容器名 | `docker compose` | 定义 `5433/8088` 暴露、本地固定容器名 `restock-dev-*` |
| 生产反向代理 | `deploy/Caddyfile` | 生产域名、HTTPS、反向代理规则 | `caddy` 容器 | 与 `APP_DOMAIN` 联动，负责 `/api/*`、`/docs*`、`/healthz`、`/readyz` |
| 本地反向代理 | `deploy/Caddyfile.dev` | 本机 HTTP 入口 | `caddy` 容器 | 本地仅监听 `:8088`，不申请 TLS |
| 运行时变量校验 | `deploy/scripts/validate_env.sh`、`backend/app/config.py` | 启动前 / 启动时 | 部署脚本、后端进程 | 防止生产环境继续使用示例占位值 |

### 变量维护矩阵

| 变量 | 本地容器维护位置 | 生产维护位置 | 原生开发维护位置 | 主要消费位置 | 说明 |
|---|---|---|---|---|---|
| `APP_DOMAIN` | — | `deploy/.env` | — | `deploy/Caddyfile`、`deploy/scripts/validate_env.sh` | 仅生产使用；决定 Caddy 域名和 TLS 证书 |
| `APP_BASE_URL` | `deploy/.env.dev` | `deploy/.env` | 可选 `backend/.env` | `deploy/docker-compose*.yml`、`deploy/scripts/smoke_check.sh` | 本地通常为 `http://localhost:8088`，生产为 `https://<domain>` |
| `APP_DOCS_ENABLED` | `deploy/.env.dev` | `deploy/.env` | `backend/.env` | `deploy/docker-compose*.yml`、`backend/app/config.py` | 控制 `/docs` 是否开放；生产默认建议关闭 |
| `DB_PASSWORD` | `deploy/.env.dev` | `deploy/.env` | — | `deploy/docker-compose*.yml` | Compose 内部 PostgreSQL 密码；修改前需确认数据卷兼容性 |
| `DATABASE_URL` | — | — | `backend/.env` | `backend/app/config.py` | 仅原生后端开发使用；容器内由 Compose 拼装生成 |
| `SAIHU_CLIENT_ID` | `deploy/.env.dev` | `deploy/.env` | `backend/.env` | `deploy/docker-compose*.yml`、`backend/app/saihu/token.py` | 赛狐 access_token 申请参数 |
| `SAIHU_CLIENT_SECRET` | `deploy/.env.dev` | `deploy/.env` | `backend/.env` | `deploy/docker-compose*.yml`、`backend/app/saihu/token.py` | 赛狐 access_token 申请密钥 |
| `LOGIN_PASSWORD` | `deploy/.env.dev` | `deploy/.env` | `backend/.env` | `deploy/docker-compose*.yml`、`backend/app/config.py` | 首次登录使用的明文密码；启动后会写入 hash |
| `JWT_SECRET` | `deploy/.env.dev` | `deploy/.env` | `backend/.env` | `deploy/docker-compose*.yml`、`backend/app/config.py` | JWT 签名密钥 |
| `WORKER_POLL_INTERVAL_SECONDS` 等任务参数 | 可选写入 `deploy/.env.dev` | 可选写入 `deploy/.env` | `backend/.env` | `backend/app/config.py`、worker/scheduler 进程 | 队列轮询、租约、心跳、重试等运行参数 |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | 可选写入 `deploy/.env.dev` | 可选写入 `deploy/.env` | `backend/.env` | `deploy/docker-compose*.yml`、`backend/app/config.py` | worker / scheduler 常按较小池配置运行 |
| `VITE_API_PROXY_TARGET` | `frontend/.env` | — | `frontend/.env` | `frontend/vite.config.ts` | 本地前端开发代理目标，默认 `http://localhost:8000` |

### IP、端口与域名矩阵

| 场景 | 服务 / 入口 | 主机监听 | 容器 / 进程端口 | 配置位置 | 备注 |
|---|---|---|---|---|---|
| 本地原生开发 | FastAPI | `localhost:8000` | `8000` | 启动命令、`backend/app/config.py` | 前端 dev 代理默认指向这里 |
| 本地原生开发 | Vite dev server | `0.0.0.0:5173` | `5173` | `frontend/vite.config.ts` | 局域网可访问前端开发页 |
| 本地原生开发 | 前端 API 代理 | `localhost:8000` | 后端 `8000` | `frontend/.env.example`、`frontend/vite.config.ts` | `/api/*` 自动反代到后端 |
| 本地容器全栈 | PostgreSQL | `0.0.0.0:5433` | `db:5432` | `deploy/docker-compose.dev.yml` | 宿主机调试口，避免占用本机 `5432` |
| 本地容器全栈 | Caddy 入口 | `0.0.0.0:8088` | `caddy:8088` | `deploy/docker-compose.dev.yml`、`deploy/Caddyfile.dev` | 本地统一入口 `http://localhost:8088` |
| 本地容器全栈 | Backend 内网 | Docker internal 网络 | `backend:8000` | `deploy/docker-compose.dev.yml`、`deploy/Caddyfile.dev` | 不直接暴露宿主机 |
| 本地容器全栈 | Frontend 内网 | Docker internal 网络 | `frontend:8080` | `deploy/docker-compose.dev.yml`、`deploy/Caddyfile.dev` | 由 Caddy 反代 |
| 生产部署 | Caddy HTTP | `0.0.0.0:80` | `caddy:80` | `deploy/docker-compose.yml` | 用于 ACME 校验和 HTTP → HTTPS |
| 生产部署 | Caddy HTTPS | `0.0.0.0:443` | `caddy:443` | `deploy/docker-compose.yml` | 正式对外入口 |
| 生产部署 | Backend 内网 | Docker internal 网络 | `backend:8000` | `deploy/docker-compose.yml`、`deploy/Caddyfile` | 仅内部访问 |
| 生产部署 | Frontend 内网 | Docker internal 网络 | `frontend:8080` | `deploy/docker-compose.yml`、`deploy/Caddyfile` | 仅内部访问 |
| 生产部署 | PostgreSQL 内网 | Docker internal 网络 | `db:5432` | `deploy/docker-compose.yml` | 生产不直接暴露宿主机 |

### IP 来源与信任边界

| 场景 | 配置位置 | 当前规则 | 作用 |
|---|---|---|---|
| Caddy → Backend 转发真实来源 IP | `deploy/Caddyfile`、`deploy/Caddyfile.dev` | 设置 `X-Real-IP`、`X-Forwarded-For`、`X-Forwarded-Proto` | 让后端日志、限流、登录审计拿到来源地址 |
| 健康检查访问限制 | `deploy/Caddyfile` | 仅允许 `127.0.0.1`、`10.0.0.0/8`、`172.16.0.0/12`、`192.168.0.0/16` 访问 `/healthz`、`/readyz` | 限制生产健康端点暴露范围 |
| 后端信任代理网段 | `backend/app/api/auth.py`、`backend/app/core/rate_limit.py` | 信任 `127.0.0.1/32`、`10.0.0.0/8`、`172.16.0.0/12`、`192.168.0.0/16` | 只有来自这些代理源时才信任转发 IP |

### 变更落点速查

| 你要改什么 | 至少要改的地方 | 说明 |
|---|---|---|
| 本地容器赛狐凭证 / 登录密码 / JWT | `deploy/.env.dev` | 改完后重建 `backend` / `worker` / `scheduler` |
| 生产赛狐凭证 / 登录密码 / JWT / 域名 | `deploy/.env` | 改完后走 `deploy.sh` 或重启相关服务 |
| 本地容器入口端口 `8088` / `5433` | `deploy/docker-compose.dev.yml`，必要时同步 `deploy/Caddyfile.dev` | 端口改动后文档与检查脚本也应同步 |
| 生产入口端口 `80/443` | `deploy/docker-compose.yml` | 变更后需确认防火墙与证书流程 |
| 本地前端代理目标 | `frontend/.env` 或 `frontend/.env.example`、`frontend/vite.config.ts` | 仅影响 `npm run dev` |
| 生产域名路由 / 健康检查限制 | `deploy/Caddyfile` | 与 `APP_DOMAIN`、trusted proxy 配置一起看 |

### 可选进阶配置

| 变量 | 说明 | 默认 |
|---|---|---|
| `WORKER_POLL_INTERVAL_SECONDS` | Worker 轮询间隔 | `2` |
| `WORKER_LEASE_MINUTES` | 任务租约时长 | `2` |
| `WORKER_HEARTBEAT_SECONDS` | 心跳间隔（约束：`heartbeat × 2 < lease × 60`） | `30` |
| `REAPER_INTERVAL_SECONDS` | Reaper 扫描间隔 | `60` |
| `DB_POOL_SIZE` | 每个服务的数据库连接池大小 | `10` |
| `DB_MAX_OVERFLOW` | 连接池可溢出上限 | `5` |
| `PUSH_AUTO_RETRY_TIMES` | 推送采购单重试次数 | `3` |
| `SAIHU_RATE_LIMIT_QPS` | 默认单接口 QPS | `1` |

---

## 4. 发布流程

### 4.1 推荐：一键发布

```bash
cd /opt/restock
bash deploy/scripts/deploy.sh
```

脚本会依次执行：

1. **校验环境变量** — `deploy/scripts/validate_env.sh` 检查必填项，并拦截 `.env.example` 中的示例占位值（包括 `LOGIN_PASSWORD=your_initial_login_password`）
2. **数据库备份** — `deploy/scripts/pg_backup.sh` 生成 `deploy/data/backups/<timestamp>.sql.gz`
3. **拉取/构建镜像** — `docker compose build backend frontend`
4. **执行迁移** — `docker compose run --rm backend alembic upgrade head`
5. **滚动更新服务** — `docker compose up -d db backend worker scheduler frontend caddy`
6. **冒烟检查** — `deploy/scripts/smoke_check.sh` 访问 `/healthz` 和 `/readyz`
7. **失败自动回滚** — 任何步骤失败触发 `deploy/scripts/rollback.sh`，仅恢复上一版应用；若迁移已执行，数据库必须通过最近一次备份手动恢复

**经验**：凡是移除旧数据库字段兼容层的发布，必须坚持“先执行 `alembic upgrade head`，再启动 backend / worker / scheduler”，否则运行时会直接暴露 schema 漂移问题。

### 4.2 手动命令（细粒度操作）

| 场景 | 命令 |
|---|---|
| 仅执行数据库迁移 | `bash deploy/scripts/migrate.sh` |
| 仅备份数据库 | `bash deploy/scripts/pg_backup.sh` |
| 从备份恢复 | `bash deploy/scripts/restore_db.sh deploy/data/backups/replenish_20260411_120000.sql.gz` |
| 回滚到上一版本 | `bash deploy/scripts/rollback.sh <previous-git-sha>` |
| 查看所有服务状态 | `docker compose -f deploy/docker-compose.yml ps` |
| 查看单个服务日志 | `docker compose -f deploy/docker-compose.yml logs -f <service>` |
| 重启单个服务 | `docker compose -f deploy/docker-compose.yml restart <service>` |
| 启动本地 dev 全栈 | `docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml up -d` |
| 停止本地 dev 全栈 | `docker compose --env-file deploy/.env.dev -f deploy/docker-compose.dev.yml down` |

---

## 5. 发布后检查

### 5.1 容器状态

```bash
docker compose -f deploy/docker-compose.yml ps
```

**预期**：6 个服务（db、backend、worker、scheduler、frontend、caddy）全部 `running` + `healthy`。

### 5.2 健康检查

```bash
curl https://your-domain.com/healthz
# 预期: {"status":"ok"}

curl https://your-domain.com/readyz
# 预期: {"status":"ok","checks":{"database":"ok","worker":"running","reaper":"running","scheduler":"running"}}
```

**注意**：`/readyz` 会根据当前进程角色返回不同的 checks 字段。例如 `backend` 服务只检查 database，`worker` 服务检查 database + worker + reaper。

### 5.3 功能验证

1. **访问前端**：`https://your-domain.com` → 登录 → 主界面可见
2. **数据同步**：进入"数据同步"页，触发一次手动同步，验证任务状态
3. **补货计算**：触发一次引擎，观察 TaskProgress 组件进度
4. **日志检查**：
   ```bash
   docker compose logs backend | grep -i error
   docker compose logs worker | grep -i error
   docker compose logs scheduler | grep -i error
   docker compose logs caddy | grep -i error
   ```

---

## 6. 升级流程

```bash
cd /opt/restock
git fetch origin
git checkout main  # 或指定 tag
git pull

# 推荐：一键发布（包含备份）
bash deploy/scripts/deploy.sh
```

**关键原则**：
- 升级前必做数据库备份（`deploy.sh` 已包含）
- 迁移失败后**不自动 downgrade**；标准回滚路径是"恢复最近备份 + 回退应用版本"
- 灰度能力：通过 scheduler 的 `scheduler_enabled` 开关临时停止定时任务

---

## 7. 常见问题

详见 [运维手册](runbook.md)。
