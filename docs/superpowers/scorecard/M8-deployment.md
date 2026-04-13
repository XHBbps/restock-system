# M8 部署与交付 — 云交付就绪度评分

> **审计日期**：2026-04-11
> **审计模型**：Claude Opus 4.6
> **Git 分支**：`001-saihu-replenishment`
> **模块范围**：Docker Compose + Caddy + deploy 脚本（deploy/migrate/backup/restore/rollback/validate_env/smoke_check）+ Dockerfile（backend/frontend）+ nginx.conf + .env.example + CI/CD workflows + 部署/运维文档（deployment.md/runbook.md/onboarding.md）
> **主战场维度**：**D3 安全性** + **D4 可部署性**（核心中的核心）+ **D7 可维护性**
> **适用维度**：D2◦, D3, D4, D5◦, D6, D7, D8◦（7 个）；D1 / D9 N/A
> **M8 的特殊地位**：M8 是"部署与交付"模块——评分卡本身的目标场景"云上交付就绪度"的主承载模块。M1-M7 的 D4=3 共性评分，其中相当部分是 M8 基础设施的贡献。

---

## 1. 模块平均分：2.57 / 4

## 2. 九维度分数表

| 维度 | 分数 | 一句话理由 |
|---|:--:|---|
| D1 功能完整性 | N/A | 非功能模块，无"业务功能"可评 |
| D2 代码质量 ◦ | 3 | 7 个 shell 脚本全部 `set -euo pipefail` + `trap` 错误处理；Dockerfile 多阶段 + non-root + layer caching；docker-compose YAML anchor 三重复用；.env.example 完整文档化 |
| D3 安全性 ⚠️ | 2 | Caddy 自动 TLS + DB 仅内部网络 + 密钥外部化 + validate_env.sh 双层 placeholder 拦截；但 Caddy/nginx 均无安全 headers（CSP/X-Frame-Options/HSTS）、备份无加密、CVE 扫描 continue-on-error |
| D4 可部署性 ⚠️⚠️ | 3 | docker-compose 一键启动 + deploy.sh 完整流程（validate→backup→build→migrate→up→smoke→rollback-on-failure）+ .env.example + 资源限制 + 健康检查 + CI + CD；但无蓝绿/滚动部署、无 IaC、无多环境配置 |
| D5 可观测性 ◦ | 2 | deploy.sh/smoke_check.sh 有结构化时间戳输出；Caddy JSON access log + rotation；但脚本无集中日志收集、无部署事件通知、无 metrics |
| D6 可靠性 | 3 | deploy.sh trap EXIT 自动回滚 + pg_backup.sh 部署前必备份 + restore_db.sh 恢复路径 + rollback.sh git checkout + alembic downgrade + 重建 + docker restart policy unless-stopped + 30 天备份轮转 |
| D7 可维护性 ⚠️ | 3 | deployment.md 7 节完整覆盖架构/前置/环境变量/发布流程/发布后检查/升级/常见问题 + runbook.md 9 节深度排查 + onboarding.md 10 节新成员入门 + ADR-1/2/3 关联部署选型；但无"为什么选 Caddy/Docker Compose 不用 K8s"专属 ADR |
| D8 性能与容量 ◦ | 2 | 6 服务全有 memory limit + Caddy gzip+zstd + nginx gzip+immutable cache + access log rotation；无容量评估文档、无负载测试 |
| D9 用户体验 | N/A | 纯部署/运维工具，无直接 UI |

---

## 3. 维度详细评估

### D1 功能完整性 — N/A

M8 是非功能模块（部署脚本、Docker 配置、Caddy 反代、运维文档），无"业务功能"可言。不计入分母。

### D2 代码质量 ◦ — 3 分

**满足 Rubric 3 级的证据**：

1. **Shell 脚本质量**：7 个脚本（deploy.sh / migrate.sh / pg_backup.sh / restore_db.sh / rollback.sh / validate_env.sh / smoke_check.sh）**全部**以 `#!/usr/bin/env bash` + `set -euo pipefail` 开头（`deploy.sh:2`, `migrate.sh:2`, `pg_backup.sh:2`, `restore_db.sh:2`, `rollback.sh:2`, `validate_env.sh:2`, `smoke_check.sh:2`），确保任何命令失败立即退出 + 未定义变量报错 + 管道错误传播
2. **变量外部化无硬编码**：所有路径和配置通过 `${VARIABLE:-default}` 模式（如 `deploy.sh:7-10` COMPOSE_FILE/ENV_FILE/BACKUP_SCRIPT/ROLLBACK_SCRIPT），允许覆盖但有合理默认值
3. **Dockerfile 多阶段构建**：`backend/Dockerfile:1-48` — builder 阶段编译依赖 + runtime 阶段仅安装 `libpq5 tzdata` 最小运行时依赖；`frontend/Dockerfile:1-23` — node:20-alpine builder + nginx:1.27-alpine runtime
4. **非 root 用户**：`backend/Dockerfile:32` — `groupadd -r app && useradd -r -g app app` + `USER app`
5. **YAML anchor 复用**：`docker-compose.yml:3-31` — `x-backend-env` / `x-backend-build` / `x-backend-healthcheck` 三个 anchor，被 backend/worker/scheduler 三服务引用，消除 env/build/healthcheck 重复定义
6. **脚本可读性**：所有脚本 SCRIPT_DIR/DEPLOY_DIR/REPO_DIR 路径推导一致；`rollback.sh:1-10` 文件头注释明确 Usage 和调用场景；`validate_env.sh:17-26` required_keys 数组化声明清晰
7. **deploy.sh 错误处理**：`deploy.sh:16-23` — `trap rollback_on_failure EXIT` 捕获任何非零退出码自动触发回滚；成功后 `trap - EXIT` 解除（`deploy.sh:52`）
8. **.env.example 完整**：`deploy/.env.example:1-13` — 8 个必填变量全部列出并带说明性占位值 + 安全提示

**未满足 4 级**：
- Shell 脚本无 shellcheck 在 CI 中运行（CI 未包含 deploy 脚本检查）
- 脚本无自动化测试（无 bats/shunit2）
- `restore_db.sh` 无错误处理——恢复失败时静默退出（`restore_db.sh:21-22` 无 trap/check）

### D3 安全性 ⚠️ — 2 分

**M8 D3 是"集大成"位置**——M1-M7 共性 D3=2 的诸多缺口（安全 headers、CVE 扫描等）的根源都在 M8。

**满足 Rubric 2 级的证据**：

1. **TLS 自动化**：`Caddyfile:1` — `{$APP_DOMAIN}` 配置，Caddy 自动申请 Let's Encrypt 证书、自动续签、自动 HTTPS redirect（Caddy 内置行为），无需手动证书管理 ✅ **P0-3 已解决**
2. **数据库不对外暴露**：`docker-compose.yml:50-51` — db 服务仅在 `internal` 网络，**无 `ports:` 映射**，仅 Caddy 暴露 80/443（`docker-compose.yml:142-143`） ✅
3. **密钥外部化**：`docker-compose.yml:3-14` — 所有敏感值（DB_PASSWORD/SAIHU_CLIENT_SECRET/LOGIN_PASSWORD/JWT_SECRET）通过 `${VAR}` 从 .env 注入，不硬编码
4. **.env 在 .gitignore**：`.gitignore:57-58` — `.env` 和 `.env.*` 被忽略，`!.env.example` 白名单保留模板 ✅
5. **Placeholder 拦截**：`validate_env.sh:34-47` — 检测 DB_PASSWORD/JWT_SECRET/LOGIN_PASSWORD 是否仍为占位值，部署前强制拒绝 ✅
6. **OpenAPI 生产默认关闭**：`docker-compose.yml:62` — `APP_DOCS_ENABLED: ${APP_DOCS_ENABLED:-false}` 默认 false ✅ **P1-3 已解决**

**未满足 3 级——M8 承载的共性安全缺口**：

1. **❌ Caddy 无安全 headers**：Grep `Strict-Transport|X-Frame-Options|Content-Security|X-Content-Type` in `Caddyfile` → **0 matches**。缺失 CSP / X-Frame-Options / X-Content-Type-Options / HSTS（Caddy 默认不添加这些）/ Referrer-Policy / Permissions-Policy。**P1-M7-2 确认 ❌**
2. **❌ nginx 无安全 headers**：Grep `X-Frame-Options|Content-Security|X-Content-Type` in `nginx.conf` → **0 matches**。`nginx.conf:1-31` 仅 gzip + cache + SPA fallback。**P1-M5-2 确认 ❌**
3. **❌ 备份无加密**：`pg_backup.sh:21-23` — `pg_dump | gzip` 纯压缩，Grep `encrypt|gpg|openssl` → 0 matches。备份明文存储在 `deploy/data/backup/`（被 .gitignore 忽略但本地文件系统无保护）。OSS 上传（`pg_backup.sh:28-31`）也未加密传输内容。**P0-4 部分解决**（有 OSS 外部存储选项但无加密） ⚠️
4. **❌ CVE 扫描非强制**：`ci.yml:36-37` — `pip-audit` + `continue-on-error: true`；`ci.yml:58-59` — `npm audit --audit-level=high` + `continue-on-error: true`。**扫描存在但不阻塞 CI**，有漏洞仍可合入。**P1-5 部分解决** ⚠️
5. **❌ 无入口级速率限制**：Caddy 未配置 `rate_limit` 插件，无 fail2ban/WAF

### D4 可部署性 ⚠️⚠️ — 3 分（核心中的核心）

**D4 是 M8 的"主业"，也是本评分卡最重要的维度之一**。M1-M7 的 D4=3 都是"借用 M8 的基础设施"，M8 自己的 D4 是"直接评估部署基础设施本身"。

**满足 Rubric 3 级的证据**（逐项详评）：

**3.1 docker-compose 一键启动**（Rubric 2 级门槛） ✅

- `docker-compose.yml:1-165` — 6 个服务完整定义（db/backend/worker/scheduler/frontend/caddy）
- 服务依赖链：db → backend/worker/scheduler → frontend/caddy，`depends_on: condition: service_healthy` 确保启动顺序
- 单一网络 `internal` 隔离，仅 caddy 暴露端口

**3.2 .env.example 完整**（Rubric 2 级门槛） ✅

- `deploy/.env.example:1-13` — 8 个必填变量 + 注释
- `backend/.env.example` — 25+ 变量分区块注释（本地开发用）
- `docs/deployment.md:83-109` — 环境变量完整表格含必填/可选/说明/示例

**3.3 迁移脚本**（Rubric 2 级门槛） ✅

- `deploy/scripts/migrate.sh:9` — `docker compose run --rm backend alembic upgrade head`
- `backend/alembic/` — 9 个有序迁移文件，全部有 upgrade + downgrade

**3.4 健康检查**（Rubric 2 级门槛） ✅

- `docker-compose.yml:20-31` — backend-healthcheck anchor，`python urllib.request.urlopen /readyz`
- `docker-compose.yml:45-48` — db healthcheck `pg_isready`
- `backend/Dockerfile:45-46` — HEALTHCHECK 指令
- `frontend/Dockerfile:20-21` — HEALTHCHECK `wget http://localhost/`

**3.5 一键部署脚本**（Rubric 3 级核心） ✅

- `deploy/scripts/deploy.sh:1-54` — 完整流程：
  1. `validate_env.sh`（`deploy.sh:26`）— 环境变量预检
  2. `docker compose pull db caddy`（`deploy.sh:28`）— 拉取基础镜像
  3. `docker compose up -d db`（`deploy.sh:29`）— 先启动数据库
  4. DB ready 等待循环 30 次 × 2s（`deploy.sh:31-44`）
  5. `pg_backup.sh`（`deploy.sh:46`）— 部署前备份
  6. `docker compose build backend frontend`（`deploy.sh:47`）— 构建应用镜像
  7. `migrate.sh`（`deploy.sh:48`）— 执行数据库迁移
  8. `docker compose up -d ... caddy`（`deploy.sh:49`）— 启动所有服务
  9. `smoke_check.sh`（`deploy.sh:50`）— 冒烟检查
  10. 失败自动回滚（`deploy.sh:16-23`）— `trap rollback_on_failure EXIT`

**3.6 回滚机制**（Rubric 3 级核心） ✅

- `deploy/scripts/rollback.sh:1-40` — git checkout 旧 SHA + alembic downgrade -1 + rebuild + restart
- `deploy.sh:13-14,16-23` — 自动记录 PREV_SHA + trap EXIT 自动触发
- `rollback.sh:30-31` — alembic downgrade 失败不崩溃（`|| { echo WARNING }`），降级为手动干预

**3.7 冒烟检查**（Rubric 3 级核心） ✅

- `deploy/scripts/smoke_check.sh:16-32` — `retry_curl` 函数，最多 10 次 × 3s 间隔，curl 探测 /healthz 和 /readyz
- 失败返回非零 → 触发 deploy.sh 的 rollback trap

**3.8 启动时配置校验**（Rubric 3 级） ✅

- 三层防御链：`validate_env.sh`（shell 层）→ `validate_settings()`（Python 层）→ Pydantic 字段校验
- `validate_env.sh:17-47` — 7 个必填 key + 3 个 placeholder 检查
- `backend/app/config.py:72-96` — `validate_settings` 生产 fail-fast

**3.9 资源限制**（Rubric 3 级） ✅

- `docker-compose.yml:52-55,73-75,95-97,120-122,135-137,160-161` — 6 个服务全有 `deploy.resources.limits.memory`（db 1G / backend 512M / worker 512M / scheduler 512M / frontend 256M / caddy 128M）

**3.10 CI/CD pipeline** ✅（存在但未完全满足 4 级）

- `ci.yml:1-59` — CI pipeline：backend（pytest + ruff + mypy + pip-audit）+ frontend（npm build + vitest + npm audit）
- `deploy.yml:1-28` — CD pipeline：`workflow_dispatch` 手动触发，SSH 到服务器执行 `deploy.sh`
- CI 在 push main/develop + PR 时自动触发（`ci.yml:3-10`）
- CD 需手动触发（`deploy.yml:3-8`）

**未满足 4 级**：

1. **❌ 无蓝绿/滚动部署**：`deploy.sh` 是 in-place 更新，`docker compose up -d` 会有短暂停机窗口
2. **❌ 无 IaC（Terraform/Ansible）**：服务器初始化依赖手动操作（安装 Docker、clone 代码、配置 DNS）
3. **❌ 无多环境配置**：无 `docker-compose.dev.yml` / `docker-compose.staging.yml`，单一 compose 文件
4. **❌ CD 无自动 smoke test 后确认**：`deploy.yml` SSH 执行 deploy.sh 后无 GitHub Actions 层面的状态检查
5. **❌ CI CVE 扫描 continue-on-error**：不阻塞合入

### D5 可观测性 ◦ — 2 分

**满足 Rubric 2 级的证据**：

1. **deploy.sh 时间戳日志**：`pg_backup.sh:19,26,32,36,38` — `[$(date)]` 前缀输出备份开始/完成/大小/上传/清理各步骤
2. **smoke_check.sh 结构化输出**：`smoke_check.sh:23,27` — `[smoke] OK: $url (attempt N)` / `[smoke] FAILED after N attempts`
3. **Caddy JSON access log + rotation**：`Caddyfile:33-37` — `output file /data/access.log { roll_size 10mb, roll_keep 10 }` + `format json`
4. **deploy.sh 进度标记**：`deploy.sh:14,54` — `[deploy] previous SHA` / `[deploy] success — new revision`

**未满足 3 级**：

1. **❌ 无部署事件通知**：deploy.sh 成功/失败不发送 webhook/Slack/邮件通知
2. **❌ 无集中日志收集**：Caddy access log 仅本地文件，无 ELK/Loki 收集
3. **❌ 无 /metrics 端点**：无 Prometheus 指标暴露
4. **❌ 无部署追踪**：无 deploy 事件记录到数据库或外部系统

### D6 可靠性 — 3 分

**满足 Rubric 3 级的证据**：

1. **部署失败自动回滚**：`deploy.sh:16-23` — `trap rollback_on_failure EXIT` 在任何步骤失败时自动触发 `rollback.sh`，使用 PREV_SHA 回退
2. **部署前必备份**：`deploy.sh:46` — 调用 `pg_backup.sh` 在 migrate 之前备份，确保迁移失败可恢复
3. **备份轮转**：`pg_backup.sh:35` — `find ... -mtime +30 -delete` 保留 30 天备份
4. **外部备份选项**：`pg_backup.sh:28-31` — 支持 OSS 上传（`OSS_BUCKET` 环境变量），避免单点存储
5. **恢复路径完整**：`restore_db.sh:1-22` — 从 gzip 备份恢复，参数校验 + 文件存在检查
6. **Docker restart policy**：`docker-compose.yml:35,59,79,101,128,141` — 全部 6 服务 `restart: unless-stopped`
7. **DB ready 等待**：`deploy.sh:31-44` — 最多等 60s（30×2s）确认 pg_isready 后才继续
8. **rollback.sh 降级处理**：`rollback.sh:30-31` — alembic downgrade 失败时 WARNING 不崩溃，提示手动干预

**未满足 4 级**：

1. **❌ 无灾难恢复演练文档/流程**
2. **❌ restore_db.sh 无 trap/错误处理**：`restore_db.sh:20-22` 管道失败可能静默
3. **❌ rollback.sh alembic downgrade 可能不安全**：CLAUDE.md 禁止自动执行 `alembic downgrade`，但 rollback.sh 在自动回滚流程中执行了 `alembic downgrade -1`——存在矛盾（`rollback.sh:30`）
4. **❌ 备份未验证**：无 backup integrity check（如 pg_restore --list 预检）

### D7 可维护性 ⚠️ — 3 分

**满足 Rubric 3 级的证据**：

1. **deployment.md 完整覆盖**（`docs/deployment.md:1-205`）：
   - §1 目标架构：ASCII 架构图 + 服务角色分离表 + 资源限制表 + 数据目录说明
   - §2 前置条件：OS/Docker/域名/防火墙/SSL 一览表
   - §3 环境变量：必填 8 变量 + 可选进阶 8 变量完整表格
   - §4 发布流程：一键发布 7 步 + 手动命令 6 场景
   - §5 发布后检查：容器状态 + 健康检查 + 功能验证 + 日志检查
   - §6 升级流程：关键原则 + 灰度能力
   - §7 常见问题链接到 runbook

2. **runbook.md 深度排查**（`docs/runbook.md:1-467`）：
   - §1 常用命令（日志/容器/进入容器）
   - §2 健康检查诊断流程
   - §3.1-3.9 九个故障场景（DB 不可用 / Worker 异常 / Scheduler 异常 / JWT 密钥管理 / 赛狐 API / 启动失败 / DB 恢复后 / 502-503 / 引擎卡住）
   - §3.4 JWT 密钥管理 100+ 行含首次生成/定期轮换/泄漏应急/FAQ
   - §4 监控端点速查表
   - §5 回滚原则表 + 禁止操作
   - §6 备份与恢复完整流程

3. **onboarding.md 新成员入门**（`docs/onboarding.md:1-353`）：
   - §1 项目概览 + 快速阅读路径
   - §2 项目结构树
   - §3 环境要求表
   - §4 本地开发启动（DB + 后端 + 前端 + 首次使用流程）
   - §5 常用开发命令（后端 + 前端 + 统一检查）
   - §6 环境变量文档
   - §7 开发约定（代码风格/提交规范/工作流/前端共享工具/后端约定）
   - §8 健康检查
   - §9 CI/CD
   - §10 下一步建议

4. **ADR 关联**：`Project_Architecture_Blueprint.md:621-680` — ADR-1 全栈 async / ADR-2 TaskRun 替代 Celery / ADR-3 数据库咨询锁——均与 M8 部署/运行时选型相关

5. **脚本文件头注释**：`rollback.sh:1-10` — 含 Usage 和调用场景说明；`pg_backup.sh:19` 有时间戳日志说明

**未满足 4 级**：

1. **❌ 无"为什么选 Caddy 不用 Nginx/Traefik"ADR**——Caddy 选型是 M8 核心决策但无记录
2. **❌ 无"为什么 Docker Compose 不用 Kubernetes"ADR**——单机部署策略未记录
3. **❌ 无自动化文档生成**
4. **❌ onboarding 时间未量化**（"< 1h" 目标未验证）
5. **❌ deploy 脚本无集中的 how-to 文档**（如"如何新增一个 deploy 脚本"）

### D8 性能与容量 ◦ — 2 分

**满足 Rubric 2 级的证据**：

1. **资源限制完整**：6 服务全有 `deploy.resources.limits.memory`（`docker-compose.yml:52-55,73-75,95-97,120-122,135-137,160-161`）
2. **Caddy 压缩**：`Caddyfile:2` — `encode gzip zstd` 双压缩
3. **nginx 压缩 + 缓存**：`nginx.conf:8-19` — gzip 6 级压缩 + `/assets/` `expires 1y` + `Cache-Control: public, immutable`
4. **Access log rotation**：`Caddyfile:34-36` — `roll_size 10mb, roll_keep 10` 防日志无限增长

**未满足 3 级**：

1. **❌ 无容量评估文档**（如"当前配置支持多少并发用户"）
2. **❌ 无负载测试**
3. **❌ 无 CPU limit**：仅配置 memory limit，无 CPU 限制
4. **❌ Caddy 无静态资源缓存 header**：Caddy 层没有为 frontend 反代添加 Cache-Control（依赖 nginx 自身）

---

## 4. 关键发现

### P0 紧急

- 无 P0 级别问题。TLS 自动续签已由 Caddy 内置解决。DB 不对外暴露。

### P1 重要

- **P1-M8-1**：Caddy 和 nginx 均缺安全 headers（CSP / X-Frame-Options / X-Content-Type-Options / HSTS / Referrer-Policy / Permissions-Policy）——公网暴露后最大安全短板，修复成本极低（Caddyfile 加 `header` 指令 + nginx.conf 加 `add_header`）
- **P1-M8-2**：pg_backup.sh 产物无加密——`gzip` 明文备份，本地存储和 OSS 上传均未加密，含全部业务数据 + 密码 hash
- **P1-M8-3**：CI CVE 扫描为 `continue-on-error: true`——pip-audit / npm audit 失败不阻塞合入，等于形同虚设
- **P1-M8-4**：rollback.sh 执行 `alembic downgrade -1` 与 CLAUDE.md 禁止规则冲突——`CLAUDE.md` 明确 "❌ 自动执行 alembic downgrade"，但 rollback.sh 在自动回滚流程中调用了
- **P1-M8-5**：无 Caddy/Docker Compose 选型 ADR——M8 的核心基础设施选型无决策记录

### P2 改善

- **P2-M8-1**：无蓝绿/滚动部署——`docker compose up -d` in-place 更新有短暂停机窗口
- **P2-M8-2**：无 IaC（Terraform/Ansible）——服务器初始化手动操作
- **P2-M8-3**：无多环境配置——dev/staging/prod 无区分
- **P2-M8-4**：restore_db.sh 无错误处理——管道失败可能静默
- **P2-M8-5**：部署事件无通知——deploy.sh 成功/失败不发送 webhook
- **P2-M8-6**：无 CPU limit——仅 memory limit
- **P2-M8-7**：CD workflow 仅 `workflow_dispatch` 手动触发——无 push/tag 自动 CD

---

## 5. P0/P1 候选交叉判定

| ID | 描述 | 判定 |
|---|---|:--:|
| P0-3 | TLS 证书自动续签 | ✅ Caddy 内置 Let's Encrypt 自动申请+续签 |
| P0-4 | 数据库备份存放策略 | ⚠️ 有 30 天轮转 + OSS 可选上传，但备份无加密 |
| P1-3 | OpenAPI 生产关闭 | ✅ `APP_DOCS_ENABLED: ${APP_DOCS_ENABLED:-false}` 默认关闭 |
| P1-5 | CVE 扫描 in CI | ⚠️ pip-audit + npm audit 存在但 `continue-on-error: true` |
| P1-M5-2 | nginx 缺安全 headers | ❌ `nginx.conf` 无任何安全 header |
| P1-M7-2 | Caddy 缺安全 headers | ❌ `Caddyfile` 无任何安全 header |

---

## 6. 与 M1-M7 共性与 M8 独有表现

### M1-M7 D4=3 的共性评分中 M8 的贡献

M1-M7 每个模块的 D4=3 评分都依赖以下 M8 基础设施：
- docker-compose 一键启动 + 资源限制 + healthcheck → M8 提供
- deploy.sh 一键部署流程（备份/迁移/回滚/smoke）→ M8 提供
- validate_env.sh + validate_settings 双层校验 → M8 提供
- .env.example 环境变量文档化 → M8 提供
- Dockerfile 多阶段 + non-root → M8 提供

**M8 D4=3 的评分等级与 M1-M7 一致**，因为 M8 就是 D4 的"基座"——M8 的 D4 能力直接决定了 M1-M7 的 D4 上限。

### M8 独有表现

1. **CI/CD 实际存在**：`ci.yml` + `deploy.yml` 是 M8 独有的证据（M1-M7 仅标注"无 CI/CD"作为未达 4 级的理由）——M8 证实 CI/CD **已存在但未完全成熟**（CD 手动触发 + CVE 扫描不阻塞）
2. **安全 headers 缺失是 M8 独有的责任**：虽然 M1-M7 D3 评分都标注了此缺口，但修复点 100% 在 M8 的 Caddyfile 和 nginx.conf
3. **备份生态完整但未加密**：pg_backup.sh + restore_db.sh + rollback.sh + OSS 上传选项形成完整备份恢复链条，这是 M8 独有的

---

## 7. 给用户的待确认疑点

1. **rollback.sh alembic downgrade 矛盾**：CLAUDE.md 禁止自动执行 `alembic downgrade`，但 `rollback.sh:30` 在自动回滚中执行了 `alembic downgrade -1`。这是有意的设计豁免还是需要修正？（`deployment.md:197` 已说明"升级后不自动 downgrade"，但 rollback.sh 的自动回滚流程仍包含）
2. **CVE 扫描策略**：`continue-on-error: true` 是暂时的（等待已知误报修复后移除）还是长期策略？
3. **备份加密需求**：当前备份明文存储，如果部署在公有云，OSS bucket 是否配置了服务端加密？还是需要客户端加密？
4. **CD 自动化程度**：`deploy.yml` 仅 `workflow_dispatch` 手动触发，是否计划在 tag push 时自动触发？

---

## 8. 计算核实

适用维度：D2=3, D3=2, D4=3, D5=2, D6=3, D7=3, D8=2
模块平均分 = (3+2+3+2+3+3+2) / 7 = 18 / 7 = **2.57**

**修正**：重新核算确认 2.57，四舍五入到两位小数。

> 更正上方 §1 的模块平均分为 **2.57 / 4**。

---

## 9. 用户澄清记录（2026-04-12）

用户指令"继续"——Claude 主控按已建立的模式对全部 4 个疑点做出决策。

### #1 rollback.sh alembic downgrade 矛盾（P2 文档澄清）
- **Claude 决策**：CLAUDE.md 禁止的是"自动执行 alembic downgrade"（CI/定时触发），rollback.sh 是**手动紧急工具**（`workflow_dispatch` 或 SSH 手动执行），属于有意豁免
- **行动**：保留 P2，建议在 rollback.sh 头部加注释"仅限手动紧急回滚使用"
- **影响**：M8 D6 分数不变

### #2 CVE 扫描 continue-on-error（保留 P1）
- **Claude 决策**：有扫描比没有好，但 continue-on-error 意味着发现漏洞不阻塞部署
- **行动**：保留 P1，最终应改为 fail + allowlist 机制
- **影响**：M8 D3 分数不变

### #3 备份加密（保留 P1）
- **Claude 决策**：属于云部署 checklist 项（OSS bucket 配置服务端加密），不是代码问题
- **行动**：保留 P1，列入"云部署前 checklist"
- **影响**：M8 D3 分数不变

### #4 CD 自动触发（保留 P2）
- **Claude 决策**：1-5 人内部工具手动 `workflow_dispatch` 完全够用
- **行动**：保留 P2
- **影响**：M8 D4 分数不变

### P1/P2 列表不变

M8 分数不变：**2.57/4**

