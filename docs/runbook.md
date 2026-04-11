# 运维 Runbook

> 配套文档：[部署指南](deployment.md) · [架构蓝图](Project_Architecture_Blueprint.md)

---

## 1. 常用命令

### 1.1 容器状态

```bash
docker compose -f deploy/docker-compose.yml ps
```

**预期**：6 个服务全部 `running` + `healthy`（db / backend / worker / scheduler / frontend / caddy）。

### 1.2 日志查看

```bash
# 单个服务实时日志
docker compose -f deploy/docker-compose.yml logs -f <service>

# 三个后端派生服务
docker compose logs -f backend
docker compose logs -f worker
docker compose logs -f scheduler

# 反代访问日志
tail -f deploy/data/caddy/access.log

# 过滤错误
docker compose logs backend | grep -iE "error|exception|traceback"
```

### 1.3 进入容器

```bash
docker compose -f deploy/docker-compose.yml exec backend bash
docker compose -f deploy/docker-compose.yml exec db psql -U postgres -d replenish
```

---

## 2. 健康检查

| 端点 | 作用 | 失败含义 |
|---|---|---|
| `GET /healthz` | 进程存活探针 | 进程崩溃或未启动 |
| `GET /readyz` | 按角色检查依赖状态 | 依赖不可用（见下） |

### 2.1 `/readyz` 检查内容

根据当前进程的 `PROCESS_ENABLE_*` 配置，检查以下组件：

| 检查项 | 何时检查 | 失败排查 |
|---|---|---|
| **database** | 所有角色 | PostgreSQL 连通性（`SELECT 1`） |
| **worker** | `PROCESS_ENABLE_WORKER=true` 时 | Worker 循环是否在运行 |
| **reaper** | `PROCESS_ENABLE_REAPER=true` 时 | Reaper 循环是否在运行 |
| **scheduler** | `PROCESS_ENABLE_SCHEDULER=true` 时 | APScheduler 实例是否存活 |

### 2.2 快速诊断流程

```
/healthz 正常但 /readyz 失败
  │
  ├─▶ 检查返回 body 的 checks 字段
  │     "database": "failed" ─▶ 看第 3.1 节
  │     "worker": "not_running" ─▶ 看第 3.2 节
  │     "scheduler": "not_running" ─▶ 看第 3.3 节
  │
  └─▶ 查对应服务日志
```

---

## 3. 故障排查

### 3.1 数据库不可用

**症状**：`/readyz` 返回 `database: failed`；backend / worker / scheduler 任一服务启动失败或频繁重启。

**排查**：

1. **PostgreSQL 是否存活**
   ```bash
   docker compose -f deploy/docker-compose.yml ps db
   docker compose -f deploy/docker-compose.yml logs db | tail -50
   ```

2. **连接配置是否正确**
   ```bash
   # 在 backend 容器内验证
   docker compose exec backend python -c "
   import asyncio
   from app.db.session import async_session_factory
   from sqlalchemy import text
   async def check():
       async with async_session_factory() as s:
           print((await s.execute(text('SELECT 1'))).scalar())
   asyncio.run(check())
   "
   ```

3. **迁移是否执行完成**
   ```bash
   docker compose exec backend alembic current
   docker compose exec backend alembic upgrade head
   ```

4. **连接池是否耗尽**
   - 默认 `DB_POOL_SIZE=10, DB_MAX_OVERFLOW=5`（每个服务独立计算）
   - 三个后端服务合计最多 45 连接，加上 db 预留
   - 日志中搜索 `QueuePool limit` 或 `TimeoutError`
   - 扩容：修改 `.env` 的 `DB_POOL_SIZE` 后重启

### 3.2 Worker 异常

**症状**：`/readyz` 在 worker 服务上返回 `worker: not_running`；任务在 `task_run` 表积压（`status='pending'` 数量持续增长）。

**排查**：

1. **容器状态**
   ```bash
   docker compose -f deploy/docker-compose.yml ps worker
   docker compose -f deploy/docker-compose.yml logs worker | tail -100
   ```

2. **查询 pending 任务堆积**
   ```sql
   SELECT job_name, status, COUNT(*) 
   FROM task_run 
   WHERE created_at > now() - interval '1 hour'
   GROUP BY job_name, status
   ORDER BY status;
   ```

3. **查最近的 running 任务是否超时**
   ```sql
   SELECT id, job_name, started_at, lease_expires_at, heartbeat_at
   FROM task_run
   WHERE status = 'running'
   ORDER BY started_at DESC
   LIMIT 20;
   ```

4. **Reaper 是否正常回收**：如果 `lease_expires_at < now()` 的 running 任务没被清理，说明 Reaper 也异常
   - Reaper 在 worker 和 scheduler 两个容器冗余运行，任一容器存活即可回收僵尸任务
   - 检查 `docker compose logs worker scheduler | grep reaper`

5. **手动重启**
   ```bash
   docker compose -f deploy/docker-compose.yml restart worker
   ```

6. **强制中断 running 任务**（当前无 cooperative cancel 机制）
   - 系统当前不支持对 `status='running'` 的任务通过 API 发起中断（`cancel_task` 端点仅对 `pending` 生效）
   - 若需立即终止某个长时间运行的任务，fallback 方案：
     ```bash
     docker compose -f deploy/docker-compose.yml restart worker
     ```
   - Worker 重启后：被中断的任务会停留在 `running` 状态，最多 `WORKER_LEASE_MINUTES` 分钟后被 reaper 标记为 `failed`（默认 2 分钟）
   - 注意：该操作会中断 **所有** 当前在 worker 容器执行的任务，不是针对单个任务的精确 cancel

### 3.3 Scheduler 异常

**症状**：定时任务不触发；`sync_state` 表的 `last_run_at` 长时间未更新。

**排查**：

1. **容器状态**
   ```bash
   docker compose -f deploy/docker-compose.yml logs scheduler | tail -100
   ```

2. **Scheduler 状态 API**
   ```bash
   # 需要有效 JWT
   curl -H "Authorization: Bearer <token>" \
     https://your-domain.com/api/sync/scheduler
   ```
   - `scheduler_enabled=false`：被用户或配置关闭
   - `running=false`：进程异常

3. **全局配置检查**
   ```sql
   SELECT scheduler_enabled, sync_interval_minutes, calc_enabled, calc_cron 
   FROM global_config WHERE id = 1;
   ```

4. **cron 表达式**：如果 `calc_cron` 是自定义，验证格式
   - 支持 5 字段（分 时 日 月 周）和 APScheduler 扩展语法
   - 保存时已做校验，非法表达式会被拦截

5. **时区**：定时任务使用 `Asia/Shanghai`
   - 03:30 `sync_warehouse`、02:00 `daily_archive`
   - 默认 08:00 `calc_engine`

### 3.4 JWT 密钥管理（首次生成 / 轮换 / 泄漏应急）

**适用范围**：`JWT_SECRET` 和 `LOGIN_PASSWORD` 两个关键密钥的生命周期管理。

#### 3.4.1 首次生成（部署前必做）

生产环境 `validate_settings` 会在启动时拦截 placeholder 密钥 `please_change_me`，必须先生成真实值：

```bash
# 生成 32 字节随机 JWT 密钥（Base64 编码，约 44 字符）
openssl rand -base64 32
# 示例输出：Wx3kLm9pQ2fT8nR6vS4aBcDeFgHiJkLmNoPqRsTuVw=

# 生成登录密码（建议 16 字符以上，混合大小写+数字+特殊字符）
openssl rand -base64 16
```

把生成的值写入 `deploy/.env`（不是 `.env.example`）：

```
JWT_SECRET=Wx3kLm9pQ2fT8nR6vS4aBcDeFgHiJkLmNoPqRsTuVw=
LOGIN_PASSWORD=你生成的密码
```

**双层防御**：
- `backend/app/config.py:82-86` — 启动时 `validate_settings` 校验 `JWT_SECRET != "please_change_me"` 且 `LOGIN_PASSWORD != "please_change_me"`
- `deploy/scripts/validate_env.sh` — 部署脚本二次校验（`deploy.sh` 会先调用）

两层都通过后才能启动。

#### 3.4.2 定期轮换（建议每 90 天）

**JWT_SECRET 轮换步骤**：

```bash
# 1. 生成新密钥
NEW_SECRET=$(openssl rand -base64 32)

# 2. 备份当前 .env
cp deploy/.env deploy/.env.bak.$(date +%Y%m%d)

# 3. 写入新密钥（保留其他变量）
sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$NEW_SECRET|" deploy/.env

# 4. 重启 backend + worker + scheduler（一起重启,确保所有进程加载新密钥）
docker compose -f deploy/docker-compose.yml restart backend worker scheduler

# 5. 验证 /readyz 返回 ok
curl https://your-domain.com/readyz
```

**影响**：所有已发放的 JWT token 立即失效，所有活跃用户必须重新登录。由于本项目是单用户 1-5 人内部工具，影响面极小（只需通知用户重新登录一次）。

**LOGIN_PASSWORD 轮换步骤**：

```bash
# 1. 生成新密码
NEW_PASSWORD=$(openssl rand -base64 16)

# 2. 更新 .env
sed -i "s|^LOGIN_PASSWORD=.*|LOGIN_PASSWORD=$NEW_PASSWORD|" deploy/.env

# 3. 重启 backend（必须重启以触发 main.py lifespan 的密码 seed 逻辑）
docker compose -f deploy/docker-compose.yml restart backend

# 4. 通知用户新密码
```

**注**：`global_config.login_password_hash` 会在 backend 启动时由 `main.py` 通过 bcrypt 重新 hash 并持久化到 DB。

#### 3.4.3 密钥泄漏应急处理

**症状**：可疑登录事件 / 已知密钥被外泄 / git 历史误 commit 密钥。

**处理步骤**（按紧急度排序）：

1. **立即轮换 `JWT_SECRET`**（按 3.4.2 流程）—— 使所有已发 JWT 立即失效
2. **立即轮换 `LOGIN_PASSWORD`**（按 3.4.2 流程）
3. **检查 `login_attempt` 表**，确认是否有异常登录尝试：
   ```sql
   SELECT * FROM login_attempt
   WHERE updated_at > now() - interval '24 hours'
   ORDER BY updated_at DESC;
   ```
4. **检查 backend 日志**中的 `auth_login_success` 和 `auth_login_failed` 事件：
   ```bash
   docker compose -f deploy/docker-compose.yml logs backend | grep auth_login
   ```
5. **如果密钥误 commit 到 git**：
   - `git rm` 从追踪移除 `.env` 文件
   - 使用 `git filter-repo` 或 `BFG Repo-Cleaner` 清除历史（高风险操作，先备份仓库）
   - 强制推送（需所有协作者重新 clone）
6. **审计其他可能被泄漏的敏感信息**：`SAIHU_CLIENT_SECRET` / 数据库密码等，按需一并轮换

#### 3.4.4 常见问题

- **Q：轮换后旧 token 怎么办？**
  - A：立即失效。用户重新登录即可。
- **Q：可以零停机轮换 JWT_SECRET 吗？**
  - A：本项目不支持（会引入密钥表等复杂度，超出 1-5 用户场景的必要性）。重启 3 个容器约 5-10 秒，可接受。
- **Q：密钥长度有最小要求吗？**
  - A：`validate_settings` 当前只拦截 placeholder，不校验长度。建议始终使用 `openssl rand -base64 32`（32 字节 / 256 位）或更长。

### 3.5 赛狐 API 调用异常

**症状**：同步任务失败或长时间卡住；`api_call_log` 表中大量 `saihu_code != 0` 记录。

**排查**：

1. **前端接口监控页**：`/settings/api-monitor` 查看近 24 小时接口统计和失败 Top
2. **典型错误码**：
   - `40001` — Token 过期：正常情况下客户端会自动刷新，持续失败说明 client_id/secret 配置错误
   - `40019` — 限流：应该被重试吃掉，持续失败说明 QPS 配置超过赛狐实际上限
   - 网络错误（timeout / connection refused）— 检查服务器网络和赛狐域名解析
3. **强制刷新 token**：重启 backend / worker 服务即可清空内存 token 缓存

### 3.6 后端启动失败

**排查顺序**：

1. **环境变量完整性**
   ```bash
   docker compose -f deploy/docker-compose.yml logs backend | grep -i "config"
   ```
   必填项：`DATABASE_URL` / `SAIHU_CLIENT_ID` / `SAIHU_CLIENT_SECRET` / `LOGIN_PASSWORD` / `JWT_SECRET`

2. **敏感值是否仍为示例值**
   - `JWT_SECRET` 不能是 `"change-me"` 之类
   - `LOGIN_PASSWORD` 不能为空

3. **数据库连接可达**（见 3.1）

4. **迁移冲突**
   ```bash
   docker compose exec backend alembic history
   docker compose exec backend alembic current
   ```

### 3.7 数据库恢复后应用异常

**排查**：

1. 重新执行迁移
   ```bash
   bash deploy/scripts/migrate.sh
   ```

2. 确认备份与当前代码版本兼容
   - 查看备份元数据（文件名通常含时间戳）
   - 对照 `alembic history` 确认兼容性

3. 不兼容时：回退应用版本到备份当时
   ```bash
   git checkout <old-tag>
   bash deploy/scripts/deploy.sh
   ```

### 3.8 发布后页面 502/503

**排查链路**：

```
用户请求 (502/503)
  │
  ├─▶ Caddy 日志 (deploy/data/caddy/access.log)
  │     检查是否有 upstream connection refused
  │
  ├─▶ backend 容器是否 healthy
  │     docker compose ps backend
  │     docker compose logs backend | tail -50
  │
  ├─▶ /readyz 是否通过
  │     curl http://backend:8000/readyz  (在 docker 网络内)
  │     或 docker compose exec caddy wget -O- http://backend:8000/readyz
  │
  └─▶ Caddy 配置是否正确反代
       查看 deploy/Caddyfile
```

### 3.9 补货引擎卡住或异常

**症状**：点击"生成补货建议"后任务长时间 running；或任务 failed 但无明确原因。

**排查**：

1. **查 task_run 记录**
   ```sql
   SELECT id, status, current_step, step_detail, error_msg, started_at
   FROM task_run WHERE job_name = 'calc_engine'
   ORDER BY id DESC LIMIT 5;
   ```

2. **常见卡点**：
   - Step 1 (velocity) — 订单数据量大时可能慢
   - Step 5 (warehouse_split) — 邮编规则或国家仓库映射缺失时会卡
   - 持久化 — 并发 advisory lock 争用（正常情况下 `pg_advisory_xact_lock` 会阻塞等待）

3. **Advisory lock 持有情况**
   ```sql
   SELECT pid, locktype, objid, granted 
   FROM pg_locks 
   WHERE locktype = 'advisory' AND objid = 7429001;
   ```

---

## 4. 监控端点速查

| 端点 | 用途 |
|---|---|
| `/healthz` | 进程存活 |
| `/readyz` | 依赖就绪（按角色检查） |
| `/api/sync/scheduler` | 调度器状态和配置 |
| `/api/monitor/api-calls` | 赛狐 API 调用统计（24h） |
| `/api/monitor/api-calls/recent` | 最近调用明细（可过滤失败） |

---

## 5. 回滚原则

| 变更类型 | 回滚方式 |
|---|---|
| **应用代码** | 切换到上一个 git tag，重新运行 `deploy.sh`（自带回滚脚本） |
| **数据库迁移** | 不默认执行 `alembic downgrade`，优先"恢复备份 + 回退应用版本" |
| **配置变更** | 修改 `deploy/.env` 后重启对应服务 |
| **高风险变更** | 先在开发环境验证，生产走完整 deploy.sh（含备份） |

**禁止**：
- 生产环境直接手动 SQL 修改数据（影响快照、审计）
- 跳过备份执行迁移
- 在 worker 运行时手动修改 `task_run` 表状态（除非已确认 worker 已停）

---

## 6. 备份与恢复

### 6.1 自动备份

- `deploy.sh` 每次发布前自动备份
- 备份位置：`deploy/data/backups/replenish_<timestamp>.sql.gz`
- 保留策略：手动管理（建议 cron 清理 30 天前备份）

### 6.2 手动备份

```bash
bash deploy/scripts/pg_backup.sh
```

### 6.3 恢复

```bash
bash deploy/scripts/restore_db.sh deploy/data/backups/replenish_20260411_120000.sql.gz
```

**警告**：恢复会**覆盖**当前数据库，请先停止相关服务：

```bash
docker compose -f deploy/docker-compose.yml stop backend worker scheduler
bash deploy/scripts/restore_db.sh <backup-file>
docker compose -f deploy/docker-compose.yml start backend worker scheduler
```

---

## 7. 应急联系

- 赛狐 API 文档：`docs/saihu_api/`
- 架构参考：`docs/Project_Architecture_Blueprint.md`
- 项目进度：`docs/PROGRESS.md`
- 部署脚本源码：`deploy/scripts/`
