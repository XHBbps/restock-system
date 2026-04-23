# 灾备审查 Findings — 2026-04-23

> Tabletop 演练：6 个失败场景。审查范围见 Task 10 of `docs/superpowers/plans/2026-04-23-post-audit-round-2.md`。
> 研究 + 发现文档，不含代码修改。

---

## 执行摘要

| 级别 | 数量 |
|---|---|
| Critical | 2 |
| Important | 4 |
| Minor | 3 |
| Ack（已覆盖，无需操作） | 9 |

**核心发现**：DB 灾难恢复路径整体可用（备份脚本 gzip -t 完整性验证 + find -mtime 30 天本地清理 + backup_cron_setup.sh 已入 init_server.sh），但存在两个 Critical 盲点：`restore_db.sh` 在 DROP/CREATE 前没有自动 dump 当前数据库做双保险；生产 `.env` 丢失无 secrets 管理文档（Vault/1Password 仅列在 P3 backlog，未落地）。Worker 假死保护机制健壮，Caddy TLS 和赛狐断线均无告警覆盖。

---

## 场景 A：数据库灾难恢复

### A-1 [Critical] restore_db.sh 无"restore 前自动 dump"双保险

**文件**：`deploy/scripts/restore_db.sh`

脚本在执行 `DROP DATABASE IF EXISTS replenish` + `CREATE DATABASE replenish` 之前，不会对现有数据库做任何 dump。一旦操作者传错备份文件路径，或备份文件本身已损坏（gzip 流中断），当前线上数据将不可恢复。

`pg_backup.sh` 的 gzip -t 验证是在生成时做的，但 `restore_db.sh` 对传入的 `$BACKUP_FILE` 不做任何完整性预检。

**风险**：运维手滑 / 文件路径错误 → 当前生产数据库被 DROP 且无法恢复。

**建议修复**：
1. 在 DROP 前执行 `pg_backup.sh` 或内联 `pg_dump | gzip > safety_<timestamp>.sql.gz`。
2. restore 入口对 `$BACKUP_FILE` 做 `gzip -t` 预检，失败立即 exit 1。

---

### A-2 [Ack] pg_backup.sh 备份完整性验证已覆盖

`pg_backup.sh` 有两层验证：
1. `stat -c%s` 字节数 < 1024 时删除并 exit 1。
2. `gzip -t` 失败时删除并 exit 1。

没有 sha256 文件，但 gzip -t 已验证流完整性，对本规模项目足够。

---

### A-3 [Ack] 30 天本地备份保留策略已落地（find -mtime +30 -delete 在脚本中）

`pg_backup.sh` 末尾有 `find "$BACKUP_DIR" -name "replenish_*.sql.gz" -mtime +30 -delete`，不是只有 runbook 建议，cron 脚本每次运行都会自动清理。

---

### A-4 [Ack] 每日 03:00 备份 cron 已通过 init_server.sh 落地

`deploy/scripts/backup_cron_setup.sh` 写入 `0 3 * * *`；`init_server.sh` 第 4 步调用它，首次初始化时自动注册。runbook §6.1 说"建议 cron 清理"描述不准确（已落地），但无影响。

---

### A-5 [Important] restore_db.sh 对传入备份文件无 gzip -t 预检

**文件**：`deploy/scripts/restore_db.sh`

脚本仅检查文件是否存在（`-f`），直接 `gzip -dc "$BACKUP_FILE" | psql`。若文件损坏（截断），psql 会在 DROP/CREATE 后收到不完整 SQL 流，导致数据库结构混乱，而脚本不会 exit 1（gzip 报错进入管道，取决于 `set -o pipefail` 是否捕获 gzip 的 non-zero）。

**注意**：脚本头部有 `set -euo pipefail`，因此管道左端 gzip 失败会中止执行，但此时 DROP/CREATE 已完成，数据库为空。

**建议**：在 `gzip -dc` 管道前先做 `gzip -t "$BACKUP_FILE" || exit 1`。

---

### A-6 [Ack] end-to-end 恢复路径可跑

`restore_db.sh` 步骤：启动 db 容器 → terminate 连接 → DROP/CREATE → `gzip -dc | psql`。在干净 postgres 容器上可执行，前提是 `deploy/.env` 和 `docker-compose.yml` 在位。流程完整，无遗漏步骤。

---

### A-7 [Minor] OSS 远端备份为可选项（OSS_BUCKET 未设置则跳过）

`pg_backup.sh` 的 OSS 上传段以 `[[ -n "$OSS_BUCKET" ]]` 守卫，部署文档未明确要求配置。若主机磁盘和备份目录同时丢失（数据卷损坏），本地 30 天备份全灭，无异地副本。对 1-5 用户内部工具风险可接受，但值得在 runbook 中显式说明"无 OSS 时异地备份缺失"。

---

## 场景 B：应用回滚

### B-1 [Ack] rollback.sh 不含 alembic downgrade，符合 AGENTS.md §11 前向修复原则

`rollback.sh` 明确注释："database schema is not downgraded automatically"，打印 SOP 提示后直接重建镜像 + 重启服务。与 AGENTS.md 禁止 `alembic downgrade` 的要求一致。

---

### B-2 [Ack] deploy.sh 回滚目标 image tag 取自 git SHA，逻辑清晰

```bash
PREV_SHA="$(cd "$REPO_DIR" && git rev-parse HEAD)"
IMAGE_TAG="${IMAGE_TAG:-sha-$PREV_SHA}"
```

`deploy.sh` 在部署开始前捕获当前 HEAD SHA，失败时通过 `trap rollback_on_failure EXIT` 自动调用 `rollback.sh "$PREV_SHA"`，精确回滚到部署前的镜像 tag。

---

### B-3 [Ack] smoke_check 失败自动触发回滚

`deploy.sh` 在 `rollback.sh` 调用后不清除 EXIT trap，`smoke_check.sh` 失败时 `set -euo pipefail` 会令脚本以非零退出，trap 捕获并调用回滚。

---

### B-4 [Important] rollback.sh 执行 docker compose build（本地 rebuild）而非 pull 旧镜像

**文件**：`deploy/scripts/rollback.sh` L35

```bash
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build backend frontend
```

在 `git checkout <prev-sha>` 后执行本地 build，而非 `docker pull ghcr.io/.../restock-backend:sha-<prev-sha>`。本地 build 依赖于源码完整可用且 Dockerfile 可重复构建，可能比直接 pull 预构建镜像耗时更长（数分钟），延长 MTTR。此外，若 rollback 在 CI/CD 构建过的旧镜像之前，本地 build 结果与 CI 产物可能存在细微差异（构建时 pip/npm 依赖解析差异）。

**建议**：回滚时优先 `docker compose pull`（拉取 ghcr.io 中已推送的 sha-tag 镜像），仅在 pull 失败时 fallback 到本地 build。

---

### B-5 [Minor] runbook §5 回滚 SOP 描述 restore_db.sh 备份目录路径与实际不符

runbook §5.1 L3 写：
```bash
ls -t deploy/data/backups/*.sql.gz | head -3
```
但 `pg_backup.sh` 的默认 `BACKUP_DIR` 是 `$DEPLOY_DIR/data/backup`（无 s），init_server.sh 也创建 `deploy/data/backup`（无 s）。路径不一致会导致手动回滚时找不到文件。

---

## 场景 C：Worker 假死 / 僵尸任务

### C-1 [Ack] Reaper 租约扫描机制覆盖 OOM kill 场景

- `WORKER_LEASE_MINUTES` 默认 2（120 秒）
- `WORKER_HEARTBEAT_SECONDS` 默认 30 秒
- 不变式检查：`worker.py` start() 验证 `heartbeat_seconds * 2 < lease_seconds`（30*2=60 < 120，通过）
- Reaper 每 60 秒扫一次 `lease_expires_at < now()`，最长等待：lease 过期（120s）+ 一个 reaper 周期（60s）= **最多 180 秒**后僵尸任务被标 failed

---

### C-2 [Ack] Reaper 在 worker 和 scheduler 双容器冗余运行

`docker-compose.yml` 中 worker 和 scheduler 均设 `PROCESS_ENABLE_REAPER: true`，注释说明"任一容器存活即可回收僵尸任务"，通过 PostgreSQL 行锁 + 幂等 UPDATE 保证并发安全。

---

### C-3 [Ack] calc_engine 写一半 suggestion 被 kill 不会 double-insert

`runner.py` 中整个 `run_engine` 在同一个 `async_session_factory() as db` 上下文内，持有 `pg_advisory_xact_lock(ENGINE_RUN_ADVISORY_LOCK_KEY=7429001)`。事务未 commit 时 worker 被 kill，事务自动回滚，数据库保持干净状态。advisory lock 同时保证同一时刻不会有两个 calc_engine 并发写入。

---

### C-4 [Ack] purge_stuck_generating 覆盖 snapshot 卡死场景

`retention.py` `purge_stuck_generating` 把 `generation_status='generating'` 超过 1 小时的 snapshot 标 failed，由每日 04:00 cron 触发。

---

### C-5 [Important] task_run 永久 running（非 calc_engine）和 suggestion 永久 draft 未被 retention 覆盖

**task_run running 状态**：reaper 只靠 `lease_expires_at`，不扫 `status='running' AND heartbeat_at < now() - N*interval`。如果某 worker 以某种方式持续刷 heartbeat 但任务逻辑卡死（e.g., 网络 hang 在 Saihu 调用，timeout=30s 已超但 asyncio 未正确 cancel），租约会被持续续期，reaper 永远不会回收。实际上 `saihu_request_timeout_seconds=30` 应让 httpx 抛 TimeoutError，但这是一个理论窗口。

**suggestion 永久 draft**：`_archive_active` 在生成新建议单时会把旧 draft 归档，但如果 calc_engine 在 `_archive_active` 之后、`_persist_suggestion` 提交之前 crash，旧 suggestion 已被 archive，新 suggestion 事务回滚，结果是"无 draft 建议单"——这不是 double draft，但可能让用户困惑（无最新建议单）。无 retention 覆盖。

**建议**：retention_purge 增加"已完成任务但 heartbeat_at 超过 N 分钟还是 running 的强制回收"以覆盖 heartbeat 刷新但任务逻辑卡死的边界场景。

---

## 场景 D：配置丢失 / Secrets Rotate

### D-1 [Critical] 生产 .env 丢失无 secrets 管理文档，恢复路径未定义

**文件**：`docs/runbook.md`，`docs/deployment.md`（未引用 vault/secret manager）

runbook §3.5 详细描述了 JWT/LOGIN_PASSWORD 轮换 SOP，但**假设 `.env` 文件仍在**。若生产服务器整体丢失或 `.env` 被误删，当前文档无任何关于"secrets 存在哪里/如何恢复"的指引。

`docs/superpowers/specs/2026-04-17-optimization-backlog.md` 将 "Vault / AWS Secrets Manager 接入" 列为 P3-5（低优先级），尚未落地。

**风险**：ops 人员无法独立从零恢复密钥，MTTR 取决于密钥持有人是否可联系。

**建议**：在 runbook §6（备份与恢复）或 §3.5 下补充"secrets 存在哪里"的一行指引（即使只是"存于 1Password vault X / 团队负责人保管"），以及恢复步骤（复制到 `.env` → 运行 `validate_env.sh` 验证 → `deploy.sh`）。

---

### D-2 [Ack] JWT_SECRET rotate 导致所有已发 JWT 立即失效已在 runbook 中明确说明

runbook §3.4.2："所有已发放的 JWT token 立即失效，所有活跃用户必须重新登录。由于本项目是单用户 1-5 人内部工具，影响面极小。" 对于当前规模，这是可接受的 tradeoff，无需 graceful rotation。

---

### D-3 [Ack] validate_env.sh 双重防护 placeholder 密钥

`validate_env.sh` 拦截 `JWT_SECRET`、`LOGIN_PASSWORD` 的占位值，并检查 JWT_SECRET 长度 ≥32 字节；`config.py:validate_settings` 在 production 环境再做一层检查。两层防线确保占位密钥无法进入生产。

---

### D-4 [Ack] LOGIN_PASSWORD rotate 后用户需重新登录，后端 lifespan 自动重 hash

runbook §3.4.2 说明：重启 backend 后 `main.py` lifespan 通过 bcrypt 重新 hash 并持久化到 `global_config.login_password_hash`，用户下次登录时使用新密码即可。

---

## 场景 E：Saihu API 中断

### E-1 [Ack] retry 配置：SAIHU_MAX_RETRIES=3，指数退避 1-10s

`client.py` 使用 tenacity `wait_exponential(multiplier=1, min=1, max=10)`，最多重试 3 次，覆盖 `SaihuRateLimited` 和 `SaihuNetworkError`。额外：40001 token 失效在 tenacity 预算外还给一次完整重试机会。

---

### E-2 [Ack] 任务 fail 后不自动重入队，符合审计基线

`worker.py` 注释明确："异常：失败 + error_msg；不会自动重新入队"。reaper 也只 fail 不 re-enqueue。task_run 表的失败记录由 retention purge 在 90 天后清理，不会无限堆积。

---

### E-3 [Important] 赛狐 API 连续失败无主动告警

当前监控端点：`/api/monitor/api-calls`（前端页面 + REST API，查看近 24h 调用统计）。这是拉取式监控，无主动推送告警（无邮件/webhook/PagerDuty）。

若赛狐宕机 2 天，系统仅在有人主动访问监控页时才能发现。`api_call_log` 表会积累大量 `error_type='network'` 记录，但没有触发告警的机制。

对 1-5 人内部工具影响可接受，但值得在 runbook 中补充"赛狐 API 持续失败的手动排查 checklist"（目前 §3.5 仅列排查路径，无频率 / 持续失败判定阈值）。

---

### E-4 [Ack] task_run 不会因 Saihu 宕机无限堆积

sync 任务失败后标 failed，不会重入队，scheduler 按 cron 周期重新触发（每小时）。若 Saihu 持续宕机，task_run 会有失败记录，但每小时最多新增 1 条（per sync job），90 天 retention 清理，不存在堆积问题。

---

## 场景 F：Caddy / HTTPS 证书

### F-1 [Important] 断网超 30 天导致 Let's Encrypt 证书到期无监控 / 告警

Caddy 2 自动 LE 证书 renew，通常在到期前 30 天续期。若生产服务器断网或 LE 接口不可达超过 30 天，证书将过期。

当前无任何证书有效期监控（无 Prometheus 指标导出，无外部 uptime 检查，无 Caddy 证书到期日志告警）。

Caddyfile 中无 `ca` 备用 CA 配置，无 self-signed fallback。证书过期后用户将收到浏览器安全警告，应用无法正常使用。

**建议**：在 runbook §7（应急联系）补充：每月人工检查证书有效期（`openssl s_client -connect $APP_DOMAIN:443 | openssl x509 -noout -dates`），或配置外部 uptime 监控工具（UptimeRobot 免费层即可）。

---

### F-2 [Minor] Caddyfile 无备用 CA / self-signed fallback

`deploy/Caddyfile` 使用 `{$APP_DOMAIN}` 站点块，Caddy 默认 LE ACME。无 `ca` 指令覆盖备用 CA（如 ZeroSSL），无 `tls internal` fallback。若 LE ACME 端点不可达（仅限中国大陆网络抖动时），证书可能无法 renew。

对内部工具可接受，但值得在 runbook 中说明"如何手动上传自签证书作临时 fallback"。

---

## 场景覆盖矩阵

| 场景 | 脚本/代码覆盖 | Runbook 覆盖 | 主要缺口 |
|---|---|---|---|
| A. DB 数据卷丢失 | pg_backup.sh + restore_db.sh | §6 | restore 前无自动 dump 双保险；restore 入口无 gzip -t 预检 |
| B. 应用回滚 | rollback.sh + deploy.sh trap | §5 回滚 SOP | rollback 做本地 build 而非 pull 旧镜像；backup 路径名有 typo |
| C. Worker 假死 | reaper + 双容器冗余 + advisory lock | §3.2 | heartbeat 刷新但逻辑卡死的 task_run 无单独清理路径 |
| D. 配置丢失 | validate_env.sh + config.py 双层 | §3.5 | 生产 .env 丢失无 secrets 存储位置文档 |
| E. Saihu API 中断 | tenacity retry + api_call_log | §3.5 | 无主动告警，依赖人工轮询 |
| F. Caddy 证书 | Caddy 自动 LE | 无 | 无证书有效期监控，无 fallback CA |

---

## 附录：关键默认配置速查

| 参数 | 默认值 | 来源 |
|---|---|---|
| `WORKER_LEASE_MINUTES` | 2（120s） | `app/config.py:53` |
| `WORKER_HEARTBEAT_SECONDS` | 30s | `app/config.py:54` |
| `REAPER_INTERVAL_SECONDS` | 60s | `app/config.py:55` |
| `SAIHU_MAX_RETRIES` | 3 | `app/config.py:38` |
| `SAIHU_REQUEST_TIMEOUT_SECONDS` | 30s | `app/config.py:37` |
| `RETENTION_TASK_RUN_DAYS` | 90 天 | `app/config.py:71` |
| `RETENTION_STUCK_GENERATING_HOURS` | 1 小时 | `app/config.py:75` |
| 备份本地保留 | 30 天 | `pg_backup.sh:58` |
| 日常备份 cron | 每日 03:00 | `backup_cron_setup.sh:12` |
| `ENGINE_RUN_ADVISORY_LOCK_KEY` | 7429001 | `app/core/locks.py:12` |
