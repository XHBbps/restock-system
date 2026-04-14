# 部署指南

> 配套文档：[架构蓝图](Project_Architecture_Blueprint.md) · [运维手册](runbook.md)

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

- `deploy/data/postgres/` — 数据库文件
- `deploy/data/caddy/` — Caddy 配置和证书
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

复制 `deploy/.env.example` 为 `deploy/.env`，至少填写：

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
