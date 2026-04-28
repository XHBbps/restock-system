# 服务器操作总入口

> 本文是生产服务器交互与运维操作的总入口，适用于 SSH 登录、GitHub Actions 发布、服务器手工操作、配置维护、备份恢复和凭证轮换。
>
> 敏感明文不写入可提交文档。需要交接具体连接信息、token、key、password 时，使用本地忽略文件 `docs/server-operations.secrets.local`，并以生产服务器 `deploy/.env`、GitHub Actions Secrets、密码管理器中的值为准。

---

## 1. 服务器入口信息

| 项目 | 当前口径 | 维护位置 |
|---|---|---|
| 系统用途 | 跨境电商海外仓补货管理生产环境 | 本文、`docs/deployment.md` |
| 生产代码路径 | `/opt/restock`（若实际不同，以 GitHub Actions `DEPLOY_PATH` 为准） | GitHub Actions Secrets、服务器实际目录 |
| 对外域名 | 由 `APP_DOMAIN` 决定 | 生产 `deploy/.env` |
| 应用基础 URL | 由 `APP_BASE_URL` 决定 | 生产 `deploy/.env` |
| Compose 文件 | `deploy/docker-compose.yml` | 仓库 |
| 生产环境变量 | `deploy/.env` | 服务器本地，不提交 |
| 生产数据库目录 | `deploy/data/pg/` | 服务器本地，不提交 |
| Caddy 数据与访问日志 | `deploy/data/caddy/`、`deploy/data/caddy/access.log` | 服务器本地，不提交 |
| 数据库备份目录 | `deploy/data/backups/` | 服务器本地，不提交 |
| 部署脚本目录 | `deploy/scripts/` | 仓库 |

服务器敏感信息索引见本机文件 `docs/server-operations.secrets.local`。该文件只用于本机交接和运维，不允许提交。

---

## 2. 常用命令

### 2.1 SSH 与目录

```bash
ssh <DEPLOY_USER>@<DEPLOY_HOST>
cd /opt/restock
git status --short
```

若生产路径不是 `/opt/restock`，以 GitHub Actions Secret `DEPLOY_PATH` 或服务器实际目录为准。

### 2.2 容器状态与日志

```bash
docker compose -f deploy/docker-compose.yml ps
docker compose -f deploy/docker-compose.yml logs -f backend
docker compose -f deploy/docker-compose.yml logs -f worker
docker compose -f deploy/docker-compose.yml logs -f scheduler
docker compose -f deploy/docker-compose.yml logs -f caddy
tail -f deploy/data/caddy/access.log
```

### 2.3 健康检查

生产 Caddy 默认对公网隐藏 `/healthz` 和 `/readyz`，从公网访问返回 `404` 属于预期。服务器本机检查使用：

```bash
curl --resolve <APP_DOMAIN>:443:127.0.0.1 https://<APP_DOMAIN>/healthz
curl --resolve <APP_DOMAIN>:443:127.0.0.1 https://<APP_DOMAIN>/readyz
```

或直接执行脚本：

```bash
bash deploy/scripts/smoke_check.sh
```

### 2.4 数据库与迁移

```bash
docker compose -f deploy/docker-compose.yml exec db psql -U postgres -d replenish
docker compose -f deploy/docker-compose.yml exec backend alembic current
bash deploy/scripts/migrate.sh
```

---

## 3. GitHub Actions Deploy 流程

### 3.1 触发入口

在 GitHub Actions 页面手动触发 `Deploy` workflow，`ref` 可填写：

| `ref` 类型 | 示例 | 说明 |
|---|---|---|
| 分支 | `main` / `master` | 部署目标分支最新提交 |
| tag | `v2026.04.28` | 部署指定版本标签 |
| 完整 commit SHA | `0123456789abcdef...` | 精确部署某个提交 |
| 短 commit SHA | `0123456` | workflow 会解析为完整 SHA |

### 3.2 门禁与镜像口径

Deploy workflow 会先把 `ref` 解析为完整 `RESOLVED_SHA`，再等待目标 commit 的以下 checks 全部通过：

| Required check | 作用 |
|---|---|
| `backend` | 后端测试与质量检查 |
| `frontend` | 前端类型检查、测试或构建检查 |
| `docker-build` | 镜像构建检查 |
| `publish` | GHCR 镜像发布 |

门禁通过后，发布使用 `IMAGE_TAG=sha-<commit>`。生产发布以该 immutable tag 为准，不依赖 `latest`。

### 3.3 SSH 部署动作

门禁通过后，workflow 通过 `DEPLOY_HOST`、`DEPLOY_USER`、`DEPLOY_SSH_KEY` 登录服务器，进入 `DEPLOY_PATH`，切换到目标 ref，导出 `IMAGE_TAG=sha-<commit>`，再执行：

```bash
bash deploy/scripts/deploy.sh
```

`deploy.sh` 会按顺序执行环境变量校验、数据库备份、镜像拉取、迁移、服务更新、冒烟检查。失败时会自动调用 `rollback.sh` 回退应用版本；若数据库迁移已经执行，数据库仍需按恢复 SOP 手工处理。

---

## 4. 手工服务器操作 SOP

### 4.1 首次初始化

仅全新服务器执行一次：

```bash
ssh <DEPLOY_USER>@<DEPLOY_HOST>
git clone https://github.com/XHBbps/restock-system.git /opt/restock
cd /opt/restock
bash deploy/scripts/init_server.sh
vim deploy/.env
bash deploy/scripts/deploy.sh
bash deploy/scripts/smoke_check.sh
```

`deploy/.env` 至少需要配置 `APP_DOMAIN`、`APP_BASE_URL`、`GHCR_OWNER`、`DB_PASSWORD`、`JWT_SECRET`、`LOGIN_PASSWORD`、`SAIHU_CLIENT_ID`、`SAIHU_CLIENT_SECRET`。

### 4.2 常规发布

优先使用 GitHub Actions `Deploy` workflow。需要服务器手工发布时：

```bash
cd /opt/restock
git fetch origin
git checkout main
git pull --ff-only
bash deploy/scripts/deploy.sh
```

发布后检查：

```bash
docker compose -f deploy/docker-compose.yml ps
bash deploy/scripts/smoke_check.sh
docker compose -f deploy/docker-compose.yml logs --since 10m backend worker scheduler
```

### 4.3 单服务重启

```bash
docker compose -f deploy/docker-compose.yml restart backend
docker compose -f deploy/docker-compose.yml restart worker
docker compose -f deploy/docker-compose.yml restart scheduler
docker compose -f deploy/docker-compose.yml restart caddy
```

重启 `worker` 会中断当前正在 worker 容器内执行的任务；任务会等待 reaper 按租约回收。生产操作前先确认影响。

### 4.4 数据库迁移

```bash
cd /opt/restock
bash deploy/scripts/pg_backup.sh
bash deploy/scripts/migrate.sh
docker compose -f deploy/docker-compose.yml exec backend alembic current
```

带迁移的发布必须先完成 migration，再启动依赖新 schema 的 backend / worker / scheduler。

### 4.5 备份

```bash
cd /opt/restock
bash deploy/scripts/pg_backup.sh
ls -lh deploy/data/backups/ | tail
```

发布脚本会自动备份；手工备份用于高风险变更、恢复前兜底或演练。

### 4.6 恢复

恢复会覆盖当前数据库，必须先停止写入服务：

```bash
cd /opt/restock
docker compose -f deploy/docker-compose.yml stop backend worker scheduler
bash deploy/scripts/restore_db.sh deploy/data/backups/replenish_<timestamp>.sql.gz
docker compose -f deploy/docker-compose.yml start backend worker scheduler
bash deploy/scripts/smoke_check.sh
```

从 2026-04-23 起，`restore_db.sh` 会在 DROP 前自动 dump 当前 DB 到同目录 `pre-restore-<timestamp>.sql.gz`，用于恢复失败后的兜底回退。

### 4.7 回滚

应用代码回滚：

```bash
cd /opt/restock
bash deploy/scripts/rollback.sh <previous-git-sha>
bash deploy/scripts/smoke_check.sh
```

若本次发布已经执行数据库迁移，标准路径是“恢复最近备份 + 回退应用版本”，不默认执行 `alembic downgrade`。

---

## 5. 配置与凭证索引

### 5.1 GitHub Actions Secrets

| 名称 | 用途 | 维护位置 | 轮换影响 |
|---|---|---|---|
| `DEPLOY_HOST` | SSH 目标主机 | GitHub Actions Secrets | 影响所有自动部署 |
| `DEPLOY_USER` | SSH 登录用户 | GitHub Actions Secrets | 影响所有自动部署 |
| `DEPLOY_SSH_KEY` | SSH 私钥 | GitHub Actions Secrets、密码管理器 | 旧 key 失效后自动部署无法登录 |
| `DEPLOY_PATH` | 服务器仓库根目录 | GitHub Actions Secrets | 路径错误会导致部署失败 |
| `DEPLOY_NOTIFY_WEBHOOK` | 发布通知 webhook | GitHub Actions Secrets | 仅影响通知 |

### 5.2 生产 `deploy/.env`

| 名称 | 用途 | 维护位置 | 轮换影响 |
|---|---|---|---|
| `APP_DOMAIN` | Caddy 对外域名和 TLS | 服务器 `deploy/.env` | 域名、证书和健康检查入口变化 |
| `APP_BASE_URL` | 应用基础 URL | 服务器 `deploy/.env` | 影响回调、冒烟检查和前后端地址口径 |
| `GHCR_OWNER` | GHCR 镜像命名空间 | 服务器 `deploy/.env` | 镜像拉取来源变化 |
| `DB_PASSWORD` | PostgreSQL 密码 | 服务器 `deploy/.env`、密码管理器 | 修改需确认数据卷与连接配置兼容 |
| `JWT_SECRET` | JWT 签名密钥 | 服务器 `deploy/.env`、密码管理器 | 旧 token 立即失效，用户需重新登录 |
| `LOGIN_PASSWORD` | 初始/重置登录密码 | 服务器 `deploy/.env`、密码管理器 | 用户下次登录使用新密码，backend 启动后重新 hash |
| `SAIHU_CLIENT_ID` | 赛狐应用 ID | 服务器 `deploy/.env`、赛狐后台 | 影响赛狐 token 获取 |
| `SAIHU_CLIENT_SECRET` | 赛狐应用密钥 | 服务器 `deploy/.env`、赛狐后台、密码管理器 | 旧凭证失效后同步任务失败 |
| `APP_DOCS_ENABLED` | 是否开放 OpenAPI 文档 | 服务器 `deploy/.env` | 生产建议保持 `false` |
| `SMOKE_BASE_URL` | 冒烟检查 URL 覆盖 | 服务器 `deploy/.env` | 影响发布后检查 |
| `SMOKE_RESOLVE_LOCAL` | 是否本机解析健康检查域名 | 服务器 `deploy/.env` | 影响 `smoke_check.sh` 检查路径 |

### 5.3 本地交接文件

| 文件 | 提交状态 | 用途 |
|---|---|---|
| `docs/server-operations.md` | 可提交 | 结构化 SOP 和索引 |
| `docs/server-operations.secrets.local` | 不提交 | 本机保存连接信息和敏感明文索引 |

---

## 6. 凭证轮换 SOP

### 6.1 SSH 部署 key

1. 在维护者本机生成新 key。
2. 把新公钥加入服务器目标用户的 `~/.ssh/authorized_keys`。
3. 更新 GitHub Actions Secret `DEPLOY_SSH_KEY`。
4. 手动触发一次 `Deploy` workflow 验证。
5. 验证成功后，从服务器移除旧公钥。
6. 更新 `docs/server-operations.secrets.local` 的确认日期。

### 6.2 JWT 与登录密码

按 `docs/runbook.md` 的“JWT 密钥管理”执行。简要口径：

```bash
openssl rand -base64 32
openssl rand -base64 16
vim deploy/.env
docker compose -f deploy/docker-compose.yml restart backend worker scheduler
bash deploy/scripts/smoke_check.sh
```

轮换 `JWT_SECRET` 会让所有已登录用户重新登录；轮换 `LOGIN_PASSWORD` 后需要通知 1-5 名使用者。

### 6.3 赛狐凭证

1. 在赛狐后台生成或获取新凭证。
2. 更新服务器 `deploy/.env` 的 `SAIHU_CLIENT_ID` 和 `SAIHU_CLIENT_SECRET`。
3. 重启 `backend`、`worker`、`scheduler`，清空内存 token 缓存。
4. 手工触发一次轻量同步或查看接口监控，确认 `40001` 不再持续出现。
5. 更新本地交接文件确认日期。

### 6.4 数据库密码

数据库密码变更会影响 PostgreSQL 容器、后端连接和现有数据卷。执行前必须先形成单独变更步骤，至少包括备份、停服务、修改 DB 密码、更新 `deploy/.env`、重启服务、冒烟检查。

---

## 7. 风险操作边界

以下操作属于高风险，执行前需要明确确认目标环境、备份和回退路径：

| 操作 | 风险 | 最低前置条件 |
|---|---|---|
| 恢复数据库 | 覆盖当前生产数据 | 已停止 backend / worker / scheduler，已确认备份文件 |
| 停止 worker | 中断正在执行的任务 | 已查看任务状态，接受等待 reaper 回收 |
| 停止 scheduler | 定时同步和定时计算不再入队 | 已确认停用窗口和恢复时间 |
| 修改 `deploy/.env` | 可能导致服务无法启动或用户重新登录 | 已备份旧 `.env`，已确认变量名和值来源 |
| 强制回滚 | 可能与已执行 migration 不兼容 | 已判断是否需要先 restore DB |
| 直接 SQL 修改生产数据 | 破坏快照、审计和业务口径 | 原则禁止；必须有单独方案和备份 |
| 修改 `task_run` 状态 | 破坏 worker 状态机 | 原则禁止；必须先停 worker 并说明原因 |

---

## 8. 例行巡检

### 8.1 每次发布后

```bash
docker compose -f deploy/docker-compose.yml ps
bash deploy/scripts/smoke_check.sh
docker compose -f deploy/docker-compose.yml logs --since 10m backend worker scheduler | grep -iE "error|exception|traceback"
tail -100 deploy/data/caddy/access.log
```

### 8.2 每周

| 检查项 | 命令 / 入口 |
|---|---|
| 容器健康 | `docker compose -f deploy/docker-compose.yml ps` |
| 备份是否持续生成 | `ls -lh deploy/data/backups/ | tail` |
| Caddy 访问异常 | `tail -500 deploy/data/caddy/access.log` |
| 赛狐失败调用 | 前端 `/settings/api-monitor` |
| 任务积压 | 查询 `task_run` 的 `pending` / `running` |

### 8.3 每季度

- 演练一次数据库恢复到临时环境。
- 复核 GitHub Actions Secrets 是否仍为当前部署 key。
- 复核 `JWT_SECRET`、`LOGIN_PASSWORD`、`SAIHU_CLIENT_SECRET` 是否需要轮换。
- 更新 `docs/server-operations.secrets.local` 的最近确认日期。

---

## 9. 相关文档

| 文档 / 目录 | 用途 |
|---|---|
| `docs/deployment.md` | 部署流程、环境变量、发布后检查细节 |
| `docs/runbook.md` | 故障排查、回滚、备份恢复、JWT 管理 |
| `docs/Project_Architecture_Blueprint.md` | 架构分层、任务队列、部署结构 |
| `deploy/scripts/` | 初始化、部署、备份、恢复、回滚、冒烟检查脚本 |
| `.github/workflows/deploy.yml` | GitHub Actions Deploy workflow |
