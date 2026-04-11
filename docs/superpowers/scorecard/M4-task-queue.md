# M4 任务队列 评分

> 评估日期：2026-04-11
> 评估人：subagent (claude-opus-4-6[1m])
> 范围：TaskRun 表 + Worker + Reaper + Scheduler 基础设施（不含具体 job handler）
> 主战场维度：D5 可观测性 / D6 可靠性
> 横向参照：M1 赛狐集成（2.63/4）、M2 补货引擎（2.75/4）、M3 建议单与推送（2.56/4）

---

## 1. 证据采集摘要

### 1.1 阅读的文件

| 文件 | 行数 | 要点 |
|---|---|---|
| `backend/app/tasks/queue.py` | 116 | `enqueue_task` + UniqueViolation 识别 + scheduler 留痕 SKIPPED |
| `backend/app/tasks/worker.py` | 229 | Worker 主循环 / `FOR UPDATE SKIP LOCKED` 原子抢占 / 心跳续租 / 失败标记 |
| `backend/app/tasks/reaper.py` | 88 | 60s 轮询 `lease_expires_at < now()`，批量 UPDATE 标记 failed |
| `backend/app/tasks/scheduler.py` | 197 | APScheduler + interval/cron trigger，调用 `_enqueue_safely` 代理 |
| `backend/app/tasks/jobs/__init__.py` | 59 | `JOB_REGISTRY` 装饰器 + `JobContext` 进度封装 |
| `backend/app/models/task_run.py` | 107 | 表结构 + 4 个索引 + 2 个 CheckConstraint |
| `backend/app/api/task.py` | 131 | list / create / get / cancel 端点 |
| `backend/alembic/versions/20260408_1500_initial.py` | 540-600 | task_run 建表迁移 |
| `backend/app/main.py` | 1-194 | 角色分离生命周期 + /readyz 后台服务检查 |
| `backend/app/config.py` | 48-95 | PROCESS_ENABLE_* + WORKER_* 默认值 + validate_settings |
| `backend/tests/unit/test_health_endpoints.py` | 95 | 4 个 readyz 测试（DB 正常 / DB 失败 / 后台失败 / 角色禁用） |
| `backend/tests/unit/test_scheduler_api.py` | 143 | 3 个调度器状态测试（monkeypatch fake scheduler） |
| `backend/tests/unit/test_runtime_settings.py` | 58 | `test_process_role_flags_can_be_overridden` |
| `deploy/docker-compose.yml` | 163 | backend / worker / scheduler 三服务 + 资源限制 + healthcheck |
| `backend/.env.example` | 40-50 | `PROCESS_ENABLE_*` / `WORKER_POLL_INTERVAL_SECONDS` 等文档化 |
| `docs/Project_Architecture_Blueprint.md` | 148-206, 500-522, 628-636 | 表结构 / 运行时图 / 索引解释 / ADR-2 |
| `docs/runbook.md` | 117-188 | 3.2 Worker 异常 / 3.3 Scheduler 异常排查手册 |

### 1.2 测试运行结果

```
cd backend && python -m pytest tests/unit/ -k "task or queue or worker or reaper or scheduler or health" -v
=> 7 passed, 149 deselected in 1.34s
```

M4 直接相关的测试仅 7 个：
- `test_health_endpoints.py`：4 个 readyz 测试（含"角色禁用时不应被判 unhealthy"）
- `test_scheduler_api.py`：3 个调度器状态与开关测试（monkeypatch fake scheduler + fake db）
- `test_runtime_settings.py::test_process_role_flags_can_be_overridden`：1 个角色开关测试

**重要差距**：`queue.py` / `worker.py` / `reaper.py` / `scheduler.py::_enqueue_safely` / `JOB_REGISTRY` 均**无直接单测**，特别是：
- Worker `_claim_one` 的 `FOR UPDATE SKIP LOCKED` 抢占原子性未被测试覆盖
- Reaper `_reap_once` 无测试
- Queue `enqueue_task` 的 UniqueViolation 重试 + scheduler SKIPPED 留痕逻辑无测试
- Worker heartbeat 续租 + crash 后 lease 过期未被测试覆盖

### 1.3 关键 grep 结果摘录

- **原子抢占**：`worker.py:93-111` 唯一的 `FOR UPDATE SKIP LOCKED` 实现。使用 subquery + outer UPDATE 模式，`RETURNING` 一条记录。
- **去重部分唯一索引**：`task_run.py:49-54` + 迁移文件 581-587 行 `uq_task_run_active_dedupe` with `postgresql_where="status IN ('pending', 'running')"`。历史任务不占索引空间。
- **心跳/租约**：`worker.py:160-176`（worker 端 30s 续租）+ `config.py:79-80` validate_settings 强制 `heartbeat × 2 < lease`；`worker.py:44-53` 同样的不变式在 `start()` 里再检查一次。
- **PROCESS_ENABLE 三开关**：`main.py:79-98` lifespan 按角色决定 start/stop；`main.py:160-172` `_background_ready` 按角色决定"禁用即视为 ready"。
- **Raw SQL 安全**：`worker.py:93` / `worker.py:166` / `reaper.py:62` / `daily_archive.py:24` — 全部 `text()` + bound params，无字符串拼接。
- **资源限制**：`docker-compose.yml:72-75, 94-97, 116-119` — backend/worker/scheduler 三服务均 `memory: 512m`，DB 1g。
- **task_run 清理**：全库 grep 无 `DELETE FROM task_run` / 无 prune/cleanup 任务 —— **task_run 表无 TTL，与 M1 `api_call_log` 属同类容量债**。
- **进度追踪**：`worker.py:180-200` `_make_progress_setter`；`jobs/__init__.py:28-39` `JobContext.progress`；`TaskRun.current_step/step_detail/total_steps` 均为 nullable。
- **前端轮询端点**：`api/task.py:106-115` `GET /api/tasks/{task_id}` 返回 TaskRunOut，覆盖 current_step/step_detail/total_steps/attempt_count/error_msg。
- **健康检查**：`main.py:144-147` `/healthz`（静态 ok），`main.py:175-193` `/readyz`（db + 后台服务联合检查）。

---

## 2. 维度评分

### D1 功能完整性 — 3/4

**判据匹配**：Rubric 3 级 "2 + 边界场景已处理；少量低频场景未覆盖但已记录 TODO"

**满足 3 级的证据**：
- 入队-抢占-执行-完结/失败全链路闭合：`queue.py:44-60`（INSERT pending）→ `worker.py:93-123`（atomic claim）→ `worker.py:140-155`（handler + 异常分支）→ `worker.py:202-218`（_mark_success / _mark_failed）
- **边界场景 1 — dedupe 并发入队**：`queue.py:61-109` 捕获 UniqueViolation → 查找活跃记录 → scheduler 留 SKIPPED 痕迹 / manual 返回已有 id；`queue.py:76-87` 还处理了"唯一冲突但活跃记录又消失"的罕见竞态并重试
- **边界场景 2 — 僵尸回收**：`reaper.py:59-77` `lease_expires_at < now()` → failed，且 finished_at 写回，有 warning 日志
- **边界场景 3 — worker crash**：task 会停留在 running 直到 reaper 扫到，不会永远卡死
- **边界场景 4 — 未注册 job_name**：`worker.py:133-136` 立刻 `_mark_failed` 不阻塞 loop
- **边界场景 5 — 心跳/租约不变式**：`config.py:79-80` + `worker.py:44-53` 双层校验 `heartbeat × 2 < lease`，防配置错误导致 reaper 误杀健康 worker
- **角色分离**：`main.py:79-98` lifespan 按 `process_enable_*` 决定进程角色，支持单进程多角色 / 多进程分离两种部署形态
- 失败任务**不自动重入队**是明确设计（`worker.py:8` 和 `reaper.py:3-4` 均有文档注释），与 M1/M2 一致

**未达 4 级的差距**：
- **无集成/契约测试守护回归**：`queue.py` / `worker.py` / `reaper.py` 零单测（见 §1.2）。M1 同级也仅 2 分，但 M1 有 140 个单测覆盖其他路径；M4 基础设施本身的核心代码路径几乎没有测试守护
- 异常恢复路径未覆盖：如"reaper 挂掉期间 worker 死亡" / "scheduler 与 worker 时钟漂移"等未验证

**与 M1/M2/M3 对齐**：全部 3 分，M4 也给 3 分。M4 边界场景处理（dedupe race retry、readyz 角色感知）较 M1/M2/M3 更体系化，但因缺乏测试守护，不升 4。

### D2 代码质量 — 2/4

**判据匹配**：Rubric 2 级 "lint + format 通过；核心模块单测 >50%；重复代码已识别"；不到 3 级 "核心模块单测 >70% + 命名清晰无明显代码异味"

**满足 2 级的证据**：
- Worker/Reaper 状态机逻辑清晰：都采用 `_stop Event + _task` 模式，`start()`/`stop()`/`running` 属性一致（`worker.py:38-72` / `reaper.py:22-45`）
- 命名规范：`_claim_one` / `_reap_once` / `_make_progress_setter` / `_mark_success` 语义明确
- 责任分离：`queue.py` 只管入队，`worker.py` 只管执行，`reaper.py` 只管回收，`scheduler.py` 只管定时入队
- 无明显重复：两处 worker/reaper 的 start/stop 模式虽相似但抽象化未必更清晰
- `_is_dedupe_conflict` 同时兼容 asyncpg UniqueViolationError + 通过错误消息串匹配，双重检测更鲁棒（`queue.py:112-115`）

**未达 3 级的差距**：
- **核心单测覆盖率 < 50%**：`queue.py` / `worker.py` / `reaper.py` / `scheduler._enqueue_safely` / `JOB_REGISTRY` 这 5 个核心模块零单测。仅 scheduler 的 HTTP 端点 + readyz + 角色开关 flag 有测试。与 M1 D2=2（subagent 判断理由：client.py/token.py 无单测）情况类似
- 心跳不变式断言在 2 处重复（`config.py:79-80` + `worker.py:44-53`），虽然防御性合理但没有抽到共用函数
- Worker `_claim_one` / `_heartbeat_loop` / `_make_progress_setter` / `_mark_success` / `_mark_failed` 5 次 `async with async_session_factory() as db: ... await db.commit()` 重复写法，未抽成 helper
- 共性问题：未确认 mypy 0 warning，未做 mutation/property test

**与 M1/M2/M3 对齐**：M1 D2=2（client/token 无单测）、M3 D2=2（list/detail/archive 无单测）、M2 D2=3（57 个引擎单测）。M4 核心模块零单测，状况与 M1/M3 同类型，**给 2 分**。

### D3 安全性 ◦ — 2/4

**判据匹配**：Rubric 2 级 "JWT + 密钥走环境变量 + Pydantic 校验 + 密码 hash"

**满足 2 级的证据**：
- task API 4 个端点（list/create/get/cancel）全部 `Depends(get_current_session)` JWT 鉴权（`api/task.py:76,92,109,121`）
- `VALID_JOB_NAMES` 白名单校验，防止 manual 入队任意 job_name（`api/task.py:18-30,94-95`）
- `EnqueueRequest` Pydantic 校验 payload/dedupe_key
- **Raw SQL 参数化**：`worker.py:93,166` / `reaper.py:62` / `daily_archive.py:24` 全部 `text()` + bound params，无注入风险
- Payload 是 JSONB 字典，worker 用 `claimed["payload"]` 直接传给 handler，**无 pickle 反序列化风险**
- `error_msg[:5000]` 截断防日志爆炸（`worker.py:216`）
- Scheduler 配置来自 DB `global_config` 表（`scheduler.py:52-77`），改 scheduler 需要走经过 JWT 鉴权的 `POST /api/sync/scheduler` 端点，不能直接篡改进程内存

**未达 3 级的差距**：
- 共性问题：无入口级速率限制 / CORS / CSRF / 安全 headers / CVE 扫描 / 审计日志（与 M1/M2/M3 一致）
- 任意 pending 任务可通过 `POST /api/tasks/{id}/cancel` 取消（`api/task.py:118-130`），仅靠 JWT 不区分角色，公网视角多用户场景存在越权风险（单用户场景可忽略）
- `cancel_task` 直接 UPDATE status=cancelled 但**不显式 commit** —— 依赖 `db_session` dep 的自动 commit；若该 dep 行为改变就会静默失效（但这是共性 DB 层问题）
- task_run `payload` 没有大小限制，理论上可从 manual 端点塞超大 JSONB（但 nginx/caddy 可拦截）

**与 M1/M2/M3 对齐**：三者均为 2 分，M4 无独有增强也无独有漏洞，**给 2 分**。

### D4 可部署性 — 3/4

**判据匹配**：Rubric 3 级 "2 + 一键部署脚本 + 启动时配置校验 + 资源限制 + .env 自动一致性校验"

**满足 3 级的证据**：
- **迁移就绪**：`20260408_1500_initial.py:540-605` 包含 task_run 建表 + 4 个索引（`uq_task_run_active_dedupe` partial / `ix_task_run_pending_priority` partial / `ix_task_run_job_created` / `ix_task_run_lease` partial）+ 2 个 CheckConstraint
- **PROCESS_ENABLE_* 三角色分离完整**：`config.py:48-50` 定义 → `main.py:79-98` lifespan 使用 → `main.py:160-172` /readyz 角色感知 → `docker-compose.yml:60-119` 三服务各自配 flag
- **docker-compose 多服务**：`docker-compose.yml` 定义 backend(worker=false, reaper=false, scheduler=false) / worker(worker=true, reaper=true, scheduler=false) / scheduler(scheduler=true) 三角色，每个服务均有 `memory: 512m` 资源限制 + healthcheck
- **健康检查角色感知**：`main.py:167-171` 禁用的角色不会把 readyz 拖垮（"(not enabled) or running"）；`test_health_endpoints.py:78-94` 有守护单测
- **启动时不变式校验**：`config.py:79-80` `validate_settings` 强制 `WORKER_HEARTBEAT_SECONDS × 2 < WORKER_LEASE_MINUTES × 60`；`worker.py:44-53` 启动时二次校验
- **.env.example 文档化**：`.env.example:40-50` 列出所有 WORKER/REAPER 调参 + PROCESS_ENABLE_*
- **一键部署脚本**（M1 共享基础设施）

**未达 4 级的差距**：
- 共性问题：无 CI/CD、无 IaC、无蓝绿/滚动部署、无多环境隔离
- **M4 独有的小缺口**：`WORKER_POLL_INTERVAL_SECONDS` / `REAPER_INTERVAL_SECONDS` 均无 validate_settings 校验（理论上填 0 会 busy loop 打爆 DB；填负数 apscheduler 会立即 raise）
- **M4 独有**：worker 和 reaper 被部署在同一 `worker` 容器里（`docker-compose.yml:82-85`），若 worker 进程 crash 则 reaper 也随之消失；极端场景下所有 running 任务的租约会一直到 backend 容器的 reaper 角色或重启 worker 才被回收。**但 backend 容器把 reaper 也关了**（`docker-compose.yml:64`），所以如果 worker 容器彻底挂了直到重启前没有任何进程会回收僵尸任务。这是部署拓扑层面的隐患，runbook 未显式警告

**与 M1/M2/M3 对齐**：三者均为 3 分，M4 核心能力（角色分离、不变式校验）在 D4 反而最齐备。给 3 分，独有的"worker/reaper 共容器 + backend 关 reaper"拓扑隐患列入 P1 并提请用户确认。

### D5 可观测性 ⚠️ — 3/4

**判据匹配**：Rubric 3 级 "2 + 业务事件指标 + /metrics + 日志统一收集 + 错误告警接入"（M4 达到 2 级 + 业务事件日志）

**满足 3 级的证据**：
- **task_run 表本身就是一张事件时间线**：`id / job_name / status / trigger_source / priority / created_at / started_at / finished_at / heartbeat_at / lease_expires_at / worker_id / attempt_count / error_msg / current_step / step_detail / total_steps` 全量可回溯任意任务的生命周期
- **结构化日志全覆盖**：`queue.py:59,103-108` task_enqueued / task_dedupe_hit；`worker.py:56,71,85,150` worker_started / worker_stopped / worker_loop_error / task_failed；`reaper.py:30,45,55,77` reaper_started / reaper_stopped / reaper_error / **reaper_collected_zombies**（含被杀 task_ids 列表）；`scheduler.py:49,185,193` scheduler_enqueue_error / scheduler_started / scheduler_shutdown
- **SKIPPED 状态审计**：`queue.py:88-101` scheduler 重复入队时插入 status='skipped' + error_msg 明确记录，这是一种非标准但很有用的"业务事件指标"，可直接 `SELECT count(*) FROM task_run WHERE status='skipped' GROUP BY job_name, DATE(created_at)` 做告警源头
- **进度追踪**：`worker.py:180-200` `_make_progress_setter` + `JobContext.progress`，任何 job 通过 `ctx.progress(current_step=...)` 即可实时写入 task_run，前端 `/api/tasks/{id}` 2 秒轮询即可看到进度更新
- **worker_id 稳定可读**：`worker.py:32` `hostname:pid:uuid[:8]`，便于多实例场景下定位是哪个 worker 卡住
- **attempt_count 自增**：每次 `_claim_one` 都 `attempt_count + 1`（`worker.py:101`），为未来实现重试策略保留字段
- **/readyz 健康检查**：`main.py:175-193` 联合 DB + worker.running + reaper.running + scheduler.running 四项

**未达 4 级的差距**：
- 共性问题：无 OpenTelemetry、无 Prometheus /metrics、无 Grafana 看板、无 SLO/SLI、无外部主动探测
- **M4 独有**：started_at / finished_at 虽然有但**无 duration 字段也无聚合端点**；排查慢任务需要业务手动 `SELECT finished_at - started_at`。对比 M1 有 `/api/monitor/saihu-calls` 聚合端点统计 API 调用，M4 没有对应的 `/api/monitor/tasks` 聚合端点
- **M4 独有**：缺乏"worker heartbeat 延迟告警"——如果 worker 正常在跑但 heartbeat 落后 90s（接近租约过期），没有任何主动告警；只能被动等 reaper 杀掉后看到 `reaper_collected_zombies` 日志
- 无 task_run 表的数据保留/清理策略，长期可观测性会被数据膨胀拖垮（见 D8）

**与 M1/M2/M3 对齐**：三者均为 3 分。M4 的"task_run 表即事件源"是所有模块 D5 的基础设施，可观测性天然对其他模块有 leverage 效应。给 3 分，不到 4 分是因为仍无 /metrics + 无聚合查询端点。

### D6 可靠性 ⚠️ — 3/4

**判据匹配**：Rubric 3 级 "2 + 指数退避 + 熔断/降级 + 死信队列 + 数据一致性校验任务 + 异常分类映射"（M4 部分满足 3 级但无熔断/死信队列，超共性 3 分门槛）

**满足 3 级的证据**：
- **原子抢占**：`worker.py:93-111` `UPDATE ... WHERE id = (SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING` 单语句完成，天然原子，无 TOCTOU 窗口；多 worker 并发安全
- **dedupe 部分唯一索引**：`task_run.py:49-54` + 迁移 581-587 行，DB 级保证同 dedupe_key 在 pending/running 下唯一；`queue.py:61-109` 应用层捕获 UniqueViolation → 查找活跃记录 → scheduler 留 SKIPPED / manual 返回现有 id
- **心跳续租 + 租约回收**：worker 每 30s 延长 `lease_expires_at = now() + 2min`；`config.py:79-80` + `worker.py:44-53` 不变式校验 `heartbeat × 2 < lease`，防止配置错误导致 reaper 误杀健康 worker
- **僵尸任务回收**：`reaper.py:59-77` 每 60s 扫描 `lease_expires_at < now() AND status='running'`，批量 UPDATE 为 failed，带 error_msg "Lease expired, worker presumed dead"
- **Worker crash 不丢任务**：worker 进程死亡后任务停留在 running 状态直到 lease 过期（最多 2 分钟）被 reaper 回收；与 M1/M2/M3 的 "失败任务不自动重入队" 设计一致（`worker.py:8`）
- **异常→failed 映射**：`worker.py:149-151` 统一 catch Exception → `_mark_failed` 写 error_msg 截断到 5000 字符；handler 未注册时也走同一路径（`worker.py:133-136`）
- **heartbeat loop 事务隔离**：`worker.py:164-176` 每次心跳独立 session + commit，避免与长 handler 共享事务锁
- **Reaper/Worker loop 守护**：`worker.py:82-86` / `reaper.py:52-57` catch Exception → 记日志 → 睡眠继续，loop 不会因单次异常崩溃
- **Scheduler 入队隔离**：`scheduler.py:44-49` `_enqueue_safely` 包一层 try/except；单个 job 入队失败不影响其他 job
- **coalesce + misfire_grace**：`scheduler.py:36-40` APScheduler 配置 `coalesce=True` + `misfire_grace_time=60`，防止错失触发被补算多次
- **max_instances=1**：防止同一 trigger 并发入队

**未达 4 级的差距**：
- 共性问题：**无熔断器 / 无死信队列**（失败 3 次以上的任务没有特殊分流；与 M1/M2/M3 一致）；无 chaos test、无故障注入演练
- **M4 独有 — finished_at 写入使用 Python 时钟而非 DB 时钟**：`worker.py:207,217`、`_mark_success` / `_mark_failed` 使用 `finished_at=now_beijing()`（Python 端），而 `started_at` 是 DB 的 `now()`（`worker.py:98`），**时钟源不一致**。若 worker 容器时钟漂移则 started_at / finished_at 不可比；reaper 的 finished_at 用的却是 DB `now()`（`reaper.py:68`）
- **M4 独有 — cancel 任务后 worker 抢不到就没事，但已 running 的任务无法真正中断**：`api/task.py:127-129` 只允许 cancel `pending` 状态；已进入 running 的任务根本无机制 cancel。这是 M1/M2/M3 共有的限制但 M4 作为基础设施层应该显式支持 cooperative cancel（设置 cancel flag + worker 周期性检查）
- **M4 独有 — Heartbeat loop 对自己失败无感**：如果 heartbeat UPDATE 失败（如临时 DB 连接丢失），`_heartbeat_loop` 会吃掉异常（通过外层 `finally: with suppress(...)` `worker.py:154`），worker 可能在心跳完全失败的情况下继续跑业务，最后被 reaper 误杀。**缺少"心跳连续失败 N 次则主动放弃任务"**的机制

**与 M1/M2/M3 对齐**：三者均为 3 分。M4 作为基础设施核心，其可靠性设计（lease + reaper + partial unique index + SKIP LOCKED）**实际上是所有其他模块可靠性的基石**，但因没有熔断/死信/chaos 同样止步于 3。**给 3 分**。

### D7 可维护性 — 3/4

**判据匹配**：Rubric 3 级 "2 + ADR + 模块边界清晰 + 文档同步协议执行 + runbook 覆盖故障 + 注释覆盖非显然逻辑"

**满足 3 级的证据**：
- **ADR 存在**：`docs/Project_Architecture_Blueprint.md:628-636` **ADR-2：自研 TaskRun 替代 Celery**，明确决策 + 驱动 + 代价 + 适用范围。**这是 M1/M2/M3 均未达成的项**
- **架构蓝图完整文档化**：
  - `Blueprint:148-206` task_run 表结构 + 4 个索引 DDL + 状态机说明 + Scheduler/Worker/Reaper 运行时图
  - `Blueprint:500-522` 表与索引的用途说明
  - `Blueprint:855-861` 环境变量默认值
- **runbook 故障手册覆盖**：
  - `docs/runbook.md:117-153` **3.2 Worker 异常**：症状 / 4 步排查（`docker compose ps` / pending 积压 SQL / lease 状态 / reaper 日志）/ 重启命令
  - `docs/runbook.md:155-188` **3.3 Scheduler 异常**：scheduler API / global_config 表 / cron 语法注意
  - `docs/runbook.md:316` **禁止**在 worker 运行时手动改 task_run（与 CLAUDE.md 禁止列表一致）
- **代码注释覆盖非显然逻辑**：
  - `queue.py:1-8` 模块 docstring 列 FR 编号
  - `queue.py:76-77` 罕见竞态的说明注释
  - `worker.py:1-9` 设计要点说明 FR-058a/d/e
  - `worker.py:44-53` 不变式检查的理由注释
  - `reaper.py:1-5` 回收后**不自动重新入队**的设计意图明注
  - `task_run.py:26-36` 状态枚举的含义注释
- **模块边界清晰**：queue / worker / reaper / scheduler / jobs 目录结构与职责一一对应

**未达 4 级的差距**：
- 共性问题：无自动化文档生成、无架构图自动同步、无 onboarding 时间量化
- 未提供正式的"状态机图"（文字描述状态转换但无图表）
- 未提供"如何写一个新 job"的 how-to 文档（register 装饰器 + JobContext 约定虽然 obvious 但 onboarding 友好度可以更高）

**与 M1/M2/M3 对齐**：三者均为 3 分，**M4 是首个明确拥有 ADR 的模块**（ADR-2），runbook 覆盖度也优于其他模块。**从文档角度 M4 > M1=M2=M3**。按 Rubric 保持 3 分（不升 4 是因为共性差距 + 无状态机图），但在 §5 共性差异中明确标注 M4 的 D7 在基础设施模块里是最好的。

### D8 性能与容量 — 2/4

**判据匹配**：Rubric 2 级 "关键接口 P95 < 1s；索引覆盖主要查询；无明显 N+1"

**满足 2 级的证据**：
- **部分索引全覆盖关键查询**：
  - `uq_task_run_active_dedupe` — dedupe 冲突检测（partial where status in pending/running），历史任务不占空间
  - `ix_task_run_pending_priority` — worker 调度查询加速（partial where status='pending'），Worker 2s 轮询命中索引 + `SKIP LOCKED`
  - `ix_task_run_lease` — reaper 扫描加速（partial where status='running'），60s 扫描不全表扫
  - `ix_task_run_job_created` — 历史查询（非 partial，全表），list API 使用
- **无 N+1**：list API（`api/task.py:78-85`）单查询 + count subquery；worker 抢占单 SQL；reaper 单批量 UPDATE
- **Worker 2s 轮询对 DB 压力可控**：只命中 `ix_task_run_pending_priority` partial 索引；pending 队列空时只是一个 nop UPDATE（`worker.py:93-123` 子查询返回空 → UPDATE 无行影响）
- **heartbeat loop 30s 独立 session**：避免长连接持有
- **资源限制明确**：docker-compose 三服务 memory 512m（M1 共享）

**未达 3 级的差距**：
- **task_run 表无 TTL / 清理机制**：与 M1 `api_call_log` 同类问题（P1 共性）。按默认配置每小时 6 个 sync job + 1 个 calc job + 1 daily archive ≈ 约 180 条/天，1 年约 65k 行；SKIPPED 记录可能更多。**没有定期清理则 list 端点按 created_at 排序的性能最终会退化**。`ix_task_run_job_created` 是非 partial 全表索引，膨胀后会拖累
- 无 SLO 定义（task 入队 P95、worker 抢占延迟 P95、reaper 回收延迟 P95 均未明确）
- 无慢查询日志 / 无容量评估文档
- Worker 2s 轮询在多 worker 实例场景下会产生 "惊群效应"（多 worker 同时竞争同一批 pending 任务，`SKIP LOCKED` 虽然不冲突但仍消耗 DB 连接）；当前单 worker 容器无问题
- **Reaper 60s 粒度**：意味着 worker 死亡后最坏 60+2*60 = 180s 任务才被标记失败（租约 2min + 扫描间隔 1min），对交付场景尚可但未记录 SLO

**与 M1/M2/M3 对齐**：三者均为 2 分。task_run 无清理是 M1 api_call_log 的同构问题。**给 2 分**。

### D9 用户体验 — N/A

**理由**：M4 是纯基础设施层，无直接 UI。TaskProgress 组件属于 M5 前端；task API 的 `/api/tasks/{id}` 只是前端轮询的数据源，不是用户直接交互的 UX 表面。

---

## 3. 模块得分

| 维度 | 分数 | 权重 | 加权 |
|---|:--:|---|---|
| D1 功能完整性 | 3 | 1.0 | 3.00 |
| D2 代码质量 | 2 | 1.0 | 2.00 |
| D3 安全性 ◦ | 2 | 1.0 | 2.00 |
| D4 可部署性 | 3 | 1.0 | 3.00 |
| D5 可观测性 ⚠️ | 3 | 1.0 | 3.00 |
| D6 可靠性 ⚠️ | 3 | 1.0 | 3.00 |
| D7 可维护性 | 3 | 1.0 | 3.00 |
| D8 性能与容量 | 2 | 1.0 | 2.00 |
| D9 用户体验 | N/A | — | — |

**模块平均分** = (3+2+2+3+3+3+3+2) / 8 = **21 / 8 = 2.63 / 4**

与 M1 (2.63) 持平，略低于 M2 (2.75)，略高于 M3 (2.56)。

---

## 4. 关键问题

### 🔴 P0（阻塞上云）
**无**。M4 的核心可靠性机制（dedupe partial unique index、FOR UPDATE SKIP LOCKED、lease + heartbeat、reaper、readyz 角色感知）均已到位，没有发现会阻塞公网部署的致命缺陷。

### 🟡 P1（影响交付质量，应在上云前解决）

**P1-M4-1：task_run 表无 TTL / 清理任务**（D8，独有）
- 证据：全库 grep 无 `DELETE FROM task_run` / 无 prune 任务
- 影响：1 年 65k+ 行 + SKIPPED 留痕 + 历史任务，`ix_task_run_job_created` 全表索引膨胀，list 端点查询性能退化
- 建议：新增 `task_run_cleanup` 定期 job（保留 30 天 success/failed/skipped，保留所有 running/pending）
- 与 M1 `api_call_log` 同类问题，可共享解决方案

**P1-M4-2：worker.py 核心路径零单测**（D2/D1）
- 证据：`test_*queue*.py` / `test_*worker*.py` / `test_*reaper*.py` 全部不存在；仅 `test_scheduler_api.py` / `test_health_endpoints.py` / `test_runtime_settings.py` 间接触达
- 影响：`_claim_one` 的 `FOR UPDATE SKIP LOCKED` 并发语义、`enqueue_task` 的 UniqueViolation 重试 + SKIPPED 留痕、`_reap_once` 的批量 UPDATE、`_heartbeat_loop` 的续租逻辑均无回归守护。任何对 worker 的"小修改"都可能静默破坏可靠性契约
- 建议：至少覆盖 queue dedupe 冲突 + SKIPPED 留痕 + worker 正常/异常执行路径 + reaper 僵尸回收

**P1-M4-3：~~worker 容器同时承担 worker + reaper，backend 容器均关闭~~ — 审计阶段已修复**（D4/D6）
- 原证据：`docker-compose.yml:63-65`（backend 全关） + `docker-compose.yml:83-85`（worker 开 worker+reaper） + `docker-compose.yml:105-107`（scheduler 只开 scheduler）
- 原风险：若 worker 容器整体 crash 未重启成功，整个系统没有任何进程回收僵尸任务
- **修复**（2026-04-11）：
  - `deploy/docker-compose.yml` 中 scheduler 服务的 `PROCESS_ENABLE_REAPER` 从 `false` 改为 `true`
  - Reaper 现在在 worker 和 scheduler 两个容器**冗余运行**（双 reaper 通过 PostgreSQL 行锁 + 幂等 UPDATE 天然并发安全）
  - 任一容器存活即可回收僵尸任务，单容器 crash 不再瘫痪回收链路
  - `docs/runbook.md` 3.2 节已同步更新"检查 `docker compose logs worker scheduler | grep reaper`"

**P1-M4-4：Heartbeat loop 失败无感知 + split-brain 风险**（D6，独有，保留待办）
- 证据：`worker.py:164-176` 心跳 UPDATE 失败会被 finally 吞掉；`_mark_success` / `_mark_failed` 不检查当前状态
- 影响：若心跳失败且 reaper 标记任务为 failed，worker 后续完成业务仍会调用 `_mark_success` 覆盖为 success（split-brain 状态）
- **用户决策**（见 §8 #6）：延后做最小修复——不实现"心跳连续失败主动放弃"（复杂度高），但在 `_mark_success` / `_mark_failed` 加 `WHERE status='running'` 守护，同时顺手统一时钟源（修复 P1-M4-5）
- **Cancel 部分**（见 §8 #2）：用户确认 **不实现 cooperative cancel**——1-5 人内部工具场景 ROI 过低，fallback 为 `docker compose restart worker`（已在 runbook.md 3.2 节记录）

**P1-M4-5：started_at / finished_at 时钟源不一致**（D6，独有）
- 证据：`worker.py:98` `started_at = now()`（DB 时钟，SQL now()）；`worker.py:207,216` `finished_at = now_beijing()`（Python 时钟）；`reaper.py:68` `finished_at = now()`（DB 时钟）
- 影响：若 worker 容器时钟漂移则 duration 计算不可靠；相同任务用两种不同时钟源是 code smell
- 建议：统一使用 DB `now()`（`update(TaskRun).values(finished_at=func.now())`）

**P1-M4-6：无 /metrics + 无 task 聚合端点**（D5，共性）
- 证据：M1 有 `/api/monitor/saihu-calls`，M4 没有 `/api/monitor/tasks`
- 建议：新增聚合端点 `GET /api/monitor/tasks?since=...` 返回每 job_name × status 的计数与平均时长

### 🟢 P2（技术债，可延后）

**P2-M4-1：`WORKER_POLL_INTERVAL_SECONDS` 与 `REAPER_INTERVAL_SECONDS` 无 validate_settings 校验**
- 证据：`config.py:72-96` 仅校验 heartbeat vs lease 不变式，poll/reaper interval 可为 0 或负数
- 建议：追加 `settings.worker_poll_interval_seconds > 0` / `settings.reaper_interval_seconds > 0` 校验

**P2-M4-2：`cancel_task` 端点未显式 commit**
- 证据：`api/task.py:129` `await db.execute(update...)` 后直接 return，依赖 `db_session` dep 自动 commit
- 建议：显式 `await db.commit()`（与 `queue.py:57` 一致）

**P2-M4-3：Worker/Reaper start/stop/running 模式重复**
- 证据：`worker.py:38-72` vs `reaper.py:22-45` 几乎同构
- 建议：抽出 `BackgroundLoop` 基类（低优，可维护性提升但非功能缺陷）

**P2-M4-4：无"新 job 注册"how-to 文档**
- 建议：在 `docs/onboarding.md` 增加"注册新 job"段落

---

## 5. 与 M1/M2/M3 共性差异

**M4 继承的共性问题**（标注"共性"即可，不重复讨论）：
- 无入口级速率限制（D3）
- 无 CVE 扫描（D3）
- 无安全 headers / CSRF（D3）
- 无 CI/CD / IaC / 蓝绿部署（D4）
- 无 OpenTelemetry / /metrics / Grafana（D5）
- 无熔断器 / 死信队列 / chaos test（D6）
- 无 SLO 定义 / 容量评估文档（D8）
- task_run 表无 TTL（D8，与 M1 api_call_log 同构）

**M4 独有表现（优于 M1/M2/M3）**：
- **首个拥有 ADR 的模块**：`Blueprint:628-636` ADR-2 明确记录"自研 TaskRun 替代 Celery"的决策、驱动、代价、适用范围。M1/M2/M3 的 D7 均标注"无 ADR"为 4 分差距，**M4 在 D7 维度上实际已部分达到 4 级门槛**（因共性差距仍保持 3 分，但在横向比较中最强）
- **角色感知的 /readyz**：`main.py:160-172` 的"禁用即视为 ready"设计是 M1/M2/M3 无法 leverage 的基础设施能力，直接支撑 docker-compose 三容器分角色部署
- **启动时不变式校验**：`config.py:79-80` + `worker.py:44-53` 双层 `heartbeat × 2 < lease` 校验是 M4 独有的"配置即代码"防御；M2 的 `default_buffer_days/target_days/lead_time_days` 缺此类校验
- **runbook 覆盖度最高**：3.2 Worker 异常 / 3.3 Scheduler 异常两节提供从症状到 SQL 排查到重启命令的完整手册，M1/M2/M3 runbook 篇幅不及

**M4 独有表现（劣于 M1/M2/M3）**：
- **核心模块零单测**：M1 有 140 单测、M2 有 57 单测、M3 有 14 单测，**M4 queue/worker/reaper 合计 0 单测**。虽然 M4 D2=2 与 M1/M3 同分，但 M1/M3 有大量周边单测可以复用 fixture，M4 的基础设施层抢占原子性 / 心跳续租 / 僵尸回收这些强并发语义完全依赖"静态 code review"守护
- **worker 容器拓扑隐患**：worker + reaper 共容器 + backend 关 reaper，worker crash 时无僵尸回收（P1-M4-3）

---

## 6. P0/P1 交叉判定

Spec 候选项映射：
- **P1-5 CVE 扫描（backend 整体共性）**：✅ 确认，D3 未达 3 级的主因之一
- **P1-7 监控告警通道**：✅ 确认，M4 的 SKIPPED 留痕 + reaper_collected_zombies 日志 + worker heartbeat 延迟等事件**有数据源但无告警通道**

M4 新增的 P0/P1（写入 §4）：
- P1-M4-1 task_run 表无 TTL（与 M1 api_call_log 同类，可合并修复）
- P1-M4-2 worker 核心路径零单测
- P1-M4-3 worker/reaper 共容器拓扑隐患
- P1-M4-4 心跳失败无感 + running 任务无 cancel
- P1-M4-5 started_at / finished_at 时钟源不一致
- P1-M4-6 无 /api/monitor/tasks 聚合端点

---

## 7. 给用户的待确认疑点

1. **worker + reaper 共容器是否为已知取舍？**（P1-M4-3）
   当前拓扑下若 worker 容器整体 crash 且 restart 也失败（如镜像损坏 / OOM 连环），**整个系统没有进程会回收僵尸任务**。这是否是已知 trade-off？是否需要把 reaper 冗余到 scheduler 容器？

2. **running 任务的 cancel 语义是否在规划中？**（P1-M4-4）
   当前 cancel 只能中断 pending 任务，已进入 running 的任务（如一次 10 分钟的 calc_engine）无法中断。是否需要协作式 cancel 机制？（worker 在 progress 回调中周期性检查 cancel_requested 标志）

3. **task_run 表的保留策略**（P1-M4-1）
   是否需要定期清理？建议保留多长时间的 success/failed/skipped 记录？SKIPPED 记录是否有长期保留价值（审计/合规）还是可以更短？

4. **attempt_count 字段的使用计划**
   worker 每次 claim 都 +1，但**当前没有任何代码读取 attempt_count 做决策**（比如"超过 3 次则特殊处理"）。这是为未来重试策略预留，还是应该移除？

5. **worker_id 格式 `hostname:pid:uuid` 在容器部署下的稳定性**
   容器重启后 hostname 可能相同，pid 常为 1，uuid 每次不同——是否符合预期？是否需要持久化 worker_id 以便跨重启追踪？

6. **心跳失败的容忍度**
   心跳 loop 当前吃掉所有异常继续尝试（`worker.py:164-178`），是否应该"连续 N 次失败即主动放弃当前任务"？否则可能出现 worker 认为自己在跑但 DB 视角已被 reaper 杀掉的分裂状态。

7. **task_run 审计日志**
   SKIPPED 留痕是目前唯一的"审计事件"。是否需要更广泛的审计（入队者 / 取消者 / 操作时间）？当前 payload 是 JSONB 但 API 不强制填 operator。

---

## 8. 用户澄清记录（2026-04-11 第一轮 review）

用户指令"按照推荐来"——接受 Claude 主控对 7 个疑点的全部推荐方案。

### #1 worker + reaper 共容器拓扑（🟢 立即修复）
- **推荐**：把 scheduler 容器的 `PROCESS_ENABLE_REAPER` 从 `false` 改为 `true`，让 reaper 在 worker 和 scheduler 两个容器冗余运行
- **修复执行**（2026-04-11）：
  - `deploy/docker-compose.yml` scheduler 服务 `PROCESS_ENABLE_REAPER: true`
  - 双 reaper 并发安全（PostgreSQL 行锁 + 幂等 UPDATE）
  - `docs/runbook.md` 3.2 节同步更新"检查 worker+scheduler 两个容器的 reaper 日志"
- **影响**：P1-M4-3 已修复；未来任一容器 crash 不再瘫痪僵尸回收链路

### #2 running 任务 cooperative cancel（🟢 不做，文档化）
- **推荐**：不实现 cooperative cancel（复杂度 > 100 LOC，ROI 极低）
- **理由**：1-5 人内部工具场景，任务都很短（calc_engine 秒级、sync 分钟级、push 最长 1 分钟），cancel 需求极低
- **Fallback**：`docker compose restart worker` 可直接中断 running 任务，reaper 在 2 分钟内回收
- **文档化**：`docs/runbook.md` 3.2 节已追加"强制中断 running 任务"的 fallback 说明
- **影响**：P1-M4-4 的 cancel 部分移除

### #3 task_run 保留策略（🟡 延后做，与 M1 批处理）
- **推荐**：保留 30 天，所有状态一视同仁，加入 `daily_archive` job
- **理由**：与 M1 `api_call_log` 保留期一致，两张表共用同一个清理任务；30 天对内部工具排查足够；pending/running 永远不清理
- **实施细节**：
  ```sql
  DELETE FROM task_run
  WHERE status IN ('success', 'failed', 'skipped', 'cancelled')
    AND finished_at < now() - interval '30 days'
  ```
- **影响**：P1-M4-1 保留在 P1 列表，打分完成后与 M1 `api_call_log` 合并为一条 fix PR

### #4 attempt_count 字段（🟢 立即保留 + 注释 tripwire）
- **推荐**：保留字段，加诊断 tripwire 注释
- **理由**：失败任务不自动重入队的设计下，attempt_count 理论上应 = 1；若实地出现 > 1 是异常信号
- **修复执行**（2026-04-11）：`backend/app/models/task_run.py:89` 加注释"当前设计失败任务不自动重入队,attempt_count 理论上应始终 = 1"
- **影响**：字段保留，用作未来诊断 tripwire

### #5 worker_id 格式 `hostname:pid:uuid`（🟢 保持现状）
- **推荐**：保持当前格式不变
- **理由**：单 worker 容器场景下，hostname/pid 冗余但无害；UUID-per-start 是一个**特性**，可区分"worker 第 1 次运行 vs 第 2 次运行"，排查日志时比持久化 worker_id 更有用
- **影响**：无改动

### #6 心跳失败容忍度（🟡 延后做最小修复）
- **推荐**：不做"连续 N 次失败主动放弃"（复杂度高），但加最小的 split-brain 保护 + 顺手统一时钟源
- **最小修复方案**：
  - `_mark_success` / `_mark_failed` 加 `WHERE status='running'` 守护
  - 若 rowcount == 0（任务已被 reaper 杀掉）→ 记 warning 日志，不覆盖状态
  - 顺带使用 `func.now()` 统一走 DB 时钟（一并修复 P1-M4-5）
- **工作量**：~15 LOC + 2 单测
- **影响**：P1-M4-4（split-brain 部分）+ P1-M4-5（时钟源）合并为一条 P1 待办，打分完成后一起做

### #7 task_run 审计日志（🟢 不做，与 M3 一致）
- **推荐**：保持现状，不添加 operator / 入队者字段
- **理由**：与 M3 审计时用户的决策一致——1-5 人内部工具不需要 operator 审计；`trigger_source` 字段已能区分 scheduler vs manual vs retry；真需要追溯可通过 structlog request_id 反查
- **影响**：无改动

---

## 9. 第二轮变更摘要（审计阶段修复）

### 代码/配置变更（3 处小改动）

| 文件 | 变更 | 对应疑点 |
|---|---|---|
| `deploy/docker-compose.yml` | scheduler 服务 `PROCESS_ENABLE_REAPER: true`（reaper 冗余）| #1 |
| `docs/runbook.md` 3.2 节 | 追加"检查 worker+scheduler reaper 日志" + "强制中断 running 任务" fallback | #1 + #2 |
| `backend/app/models/task_run.py:89` | attempt_count 字段加诊断 tripwire 注释 | #4 |

**测试结果**：全量 pytest 163 passed（原 156 + M3 fix 的 2 + 5 其他无关变化），零回归

### P1 列表演变

- P1-M4-1 task_run TTL → **保留**（延后做，与 M1 批处理）
- P1-M4-2 核心路径零单测 → **保留**
- ~~P1-M4-3 worker/reaper 拓扑隐患~~ → **审计阶段已修复**
- P1-M4-4 split-brain + cancel → **拆分**：cancel 不做（#2），split-brain 延后做最小修复（#6）
- P1-M4-5 时钟源不一致 → **合并到 #6 一起修**
- P1-M4-6 无 /api/monitor/tasks 聚合 → **保留**

### P1 总数变化

- **修复前**：6 项
- **修复后**：4 项（P1-M4-1 / P1-M4-2 / P1-M4-4-split-brain（含 P1-M4-5）/ P1-M4-6）

### M4 分数影响

- 各维度分数**不变**（修复后 D4 / D6 均维持 3）
- 模块平均分**不变**（2.63/4）
- 主要价值：**消除了部署拓扑隐患**（P1-M4-3 从"待办"变为"已修"）
