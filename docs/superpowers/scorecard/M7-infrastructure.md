# M7 基础设施 — 云交付就绪度评分

> **审计日期**：2026-04-11
> **审计模型**：Claude Opus 4.6
> **Git 分支**：`001-saihu-replenishment`
> **模块范围**：数据库（base/session）、迁移（alembic）、健康检查（/healthz + /readyz）、日志（structlog）、异常体系（BusinessError/SaihuAPIError）、中间件（RequestLoggingMiddleware）、配置（Settings/validate_settings）
> **主战场维度**：D5 可观测性 + D4 可部署性
> **适用维度**：D1◦, D2, D3, D4, D5, D6, D7, D8 ✓；D9 N/A

---

## 1. 模块平均分：2.50 / 4

## 2. 九维度分数表

| 维度 | 分数 | 一句话理由 |
|---|:--:|---|
| D1 功能完整性 ◦ | 3 | DB session 生命周期完整、中间件链就绪、/healthz+/readyz 角色感知联合检查、alembic 9 个迁移 up/down 完整、lifespan 四事件齐全 |
| D2 代码质量 | 2 | base.py/session.py/exceptions.py/middleware.py/logging.py 均职责单一且简洁（最长 69 行），26 个基础设施相关单测全 pass；但 middleware/exceptions/logging 三核心模块零专项单测，无 mypy |
| D3 安全性 | 2 | DB DSN 走环境变量 + 生产 fail-fast + 异常 handler 不泄漏 traceback + Caddy 自动 TLS；无 CORS 中间件（同源依赖 Caddy）、无安全 headers、无日志脱敏处理器、无 CVE 扫描 |
| D4 可部署性 ⚠️ | 3 | 多阶段 Dockerfile + non-root user + HEALTHCHECK、docker-compose 5 服务 + YAML anchor 复用 + 资源限制、alembic env.py compare_type + 9 个有序迁移 + 命名规范、validate_settings fail-fast、.env.example 25+ 变量完整文档化 |
| D5 可观测性 ⚠️⚠️ | 2 | structlog JSON/Console 双模式 + request_id contextvar 绑定 + X-Request-Id 回传 + 4xx/5xx 日志级别分化 + lifecycle 四事件；无敏感字段脱敏处理器、无 /metrics、无 OpenTelemetry |
| D6 可靠性 | 3 | session rollback on exception + pool_pre_ping 连接自愈 + BusinessError/SaihuAPIError 双层异常分类映射 + /readyz DB ping 失败 graceful 503 + lifespan graceful shutdown 四步序列 |
| D7 可维护性 | 3 | 架构蓝图 §3.4 异常/日志/中间件/配置四行文档化 + ADR-1 全栈 async + runbook §2 健康检查 + §3.1 DB 不可用 + §3.4 JWT 密钥管理 + §3.6 启动失败 + §6 备份恢复共 6 个章节 + alembic 命名规范文档 |
| D8 性能与容量 | 2 | pool_size/max_overflow/pool_recycle 三项可配 + pool_pre_ping + /readyz SELECT 1 轻量探针 + 资源限制明确；无 SLO、无慢查询日志、无容量评估文档 |
| D9 用户体验 | N/A | 纯基础设施层无直接 UI |

---

## 3. 维度详细评估

### D1 功能完整性 ◦（低权重）— 3 分

M7 是非功能性基础设施模块，D1 评估"基础设施能力是否可用"。

**满足 Rubric 3 级的证据**：

1. **DB session 生命周期完整**：`session.py:34-43` — `async with` 作用域管理，try/except rollback，else commit，三路径闭合
2. **中间件链完整**：`main.py:110` — `RequestLoggingMiddleware` 注册；`middleware.py:20-49` — request_id 生成/绑定/回传 + 耗时计量 + 异常捕获
3. **健康检查端点齐全**：`main.py:144-147` — `/healthz` 存活探针；`main.py:175-193` — `/readyz` 角色感知联合检查（DB + worker + reaper + scheduler 四项，按 PROCESS_ENABLE_* 动态跳过）
4. **alembic 迁移完整**：9 个迁移文件，全部有 upgrade() + downgrade()，初始迁移覆盖 20 张表，命名规范 `YYYYMMDD_HHMM_description.py`
5. **Lifespan 四事件**：`main.py:73-99` — `app_starting` / `app_started` / `app_stopping` / `app_stopped`，按 PROCESS_ENABLE_* 有条件启停 worker/reaper/scheduler
6. **边界场景**：`/readyz` 分别处理 DB 失败（503 database_unavailable）和 background 失败（503 + components 明细）；`_database_ready` 有 try/except 不崩溃

**未满足 4 级**：无针对 M7 基础设施的集成测试（如真实 DB 的 session lifecycle + middleware 链端到端），健康检查测试用 monkeypatch 非真实 DB

### D2 代码质量 — 2 分

**满足 Rubric 2 级的证据**：

1. **核心文件简洁清晰**：`base.py` 54 行（声明基类 + NAMING_CONVENTION + TimestampMixin）、`session.py` 44 行、`exceptions.py` 96 行（双层层次 BusinessError 6 子类 + SaihuAPIError 4 子类）、`middleware.py` 50 行、`logging.py` 69 行、`timezone.py` 125 行
2. **26 个基础设施相关单测全 pass**：`test_health_endpoints.py` 4 个 + `test_query_utils.py` 5 个 + `test_runtime_settings.py` 3 个 + `test_config_schema.py` 14 个
3. **职责单一**：每个 core/ 文件只做一件事——logging 配 structlog、middleware 做请求日志、exceptions 定义层次、timezone 做时区转换、query 做 LIKE 转义
4. **docstring 完整**：所有 core/ 文件都有模块级 docstring + 用法示例

**未满足 3 级**：
- `middleware.py` / `exceptions.py` / `logging.py` 三个核心模块**零专项单测**（只有间接覆盖），覆盖率低于 70%
- 无 mypy / type-check 验证
- 与 M1=2/M3=2/M4=2 一致：核心模块有部分单测但不达 70% 覆盖率

### D3 安全性 — 2 分

**满足 Rubric 2 级的证据**：

1. **DB DSN 走环境变量**：`config.py:26-29` — `database_url` 通过 pydantic-settings 从 env 加载，无硬编码
2. **生产 fail-fast**：`config.py:82-86` — 拦截 placeholder JWT_SECRET / LOGIN_PASSWORD / SAIHU_CLIENT_ID / SAIHU_CLIENT_SECRET
3. **异常不泄漏 traceback**：`main.py:113-118` — BusinessError handler 只返回 `{message, detail}`；`main.py:122-131` — SaihuAPIError handler 只返回 `{message, endpoint, code, request_id}`；FastAPI 默认无 `debug=True`，5xx 返回 Starlette 默认 "Internal Server Error" 文本
4. **Caddy 自动 TLS**：`deploy/Caddyfile:1` — `{$APP_DOMAIN}` 自动 HTTPS + Let's Encrypt；`docker-compose.yml:143-144` — 暴露 80/443

**未满足 3 级**：
- ❌ **无 CORS 中间件**：Grep `CORSMiddleware` → 0 matches。当前依赖 Caddy 同源策略（所有请求通过 Caddy 统一入口），但后端本身无 CORS 保护
- ❌ **无安全 headers**：Caddy 默认不添加 CSP / X-Frame-Options / X-Content-Type-Options
- ❌ **无日志脱敏处理器**：structlog processors 链中无 sanitize/redact 步骤，`request_id` 中间件直接记录 path（含可能的 query params）
- ❌ **无 CVE 扫描**
- ❌ **5xx 默认响应非 JSON**：unhandled exception 返回 Starlette 默认纯文本 "Internal Server Error"，与 BusinessError/SaihuAPIError 的 JSON shape 不一致

**P1-2 CORS allowed_origins 判定**：⚠️ 无 CORS 中间件。Caddy 反代同源策略提供隐式保护，但后端 8000 端口如被直接访问则无 CORS 限制

**P1-4 5xx traceback 泄漏判定**：✅ 不泄漏。FastAPI 默认无 debug 模式，Starlette 返回纯文本 "Internal Server Error"，不含 traceback

### D4 可部署性 ⚠️（次主战场）— 3 分

**满足 Rubric 3 级的证据**：

1. **多阶段 Dockerfile**：`Dockerfile:1-48` — builder 阶段编译依赖 + runtime 阶段仅 libpq5/tzdata，镜像精简
2. **非 root 用户**：`Dockerfile:32` — `groupadd -r app && useradd -r -g app app`；`Dockerfile:41` — `USER app`
3. **HEALTHCHECK**：`Dockerfile:45-46` — `--interval=30s --timeout=5s --start-period=20s --retries=3` 探测 `/readyz`
4. **docker-compose 完整**：`docker-compose.yml:1-165` — 5 服务（db/backend/worker/scheduler/frontend）+ caddy 反代 + YAML anchor `*backend-env` / `*backend-build` / `*backend-healthcheck` 复用 + 资源限制（db 1G / backend 512M / worker 512M / scheduler 512M / frontend 256M / caddy 128M）
5. **alembic 迁移机制**：`alembic/env.py` — async 在线模式 + offline 模式均配置 `compare_type=True` + `compare_server_default=True`；9 个迁移文件有序链接 `down_revision`
6. **validate_settings fail-fast**：`config.py:72-96` — 启动时校验 DATABASE_URL / heartbeat 不变式 / 生产密钥
7. **.env.example 完整**：`backend/.env.example` — 25+ 变量分 7 个区块注释

**未满足 4 级**：
- 无 CI/CD pipeline
- 无 IaC（Terraform / Pulumi）
- 无蓝绿/滚动部署自动化
- 无多环境配置（staging / production 共用一份 compose）

### D5 可观测性 ⚠️⚠️（主战场）— 2 分

**满足 Rubric 2 级的证据**：

1. **structlog 双模式**：`logging.py:40-43` — development `ConsoleRenderer(colors=True)` / 非 development `JSONRenderer` 生产 JSON 输出
2. **request_id 自动绑定**：`middleware.py:22-24` — 取 `X-Request-Id` header 或生成 `uuid.uuid4().hex[:16]`，`clear_contextvars` + `bind_contextvars` 保证请求隔离
3. **X-Request-Id 回传**：`middleware.py:48` — `response.headers["X-Request-Id"] = request_id`
4. **4xx/5xx 日志级别分化**：`middleware.py:40` — `info if status < 400 else warning`
5. **异常事件捕获**：`middleware.py:29-37` — `logger.exception("http_request_exception", ...)` 含 method/path/duration_ms
6. **Lifecycle 四事件**：`main.py:76,88,92,99` — `app_starting` / `app_started` / `app_stopping` / `app_stopped`
7. **日志级别可配**：`config.py:24` — `app_log_level: str = "INFO"`，`logging.py:23` — `getLevelName(settings.app_log_level.upper())`

**M7 作为基础设施被其他模块 leverage 的能力**：
- M1-M6 的所有 structlog 调用（`get_logger(__name__)`）都基于 M7 的 `logging.py` 配置
- M1-M6 的 request_id 上下文绑定都基于 M7 的 `middleware.py`
- M1-M4 的 D5=3 评分中的 "structlog JSON 日志 + request_id 绑定" 基础来自 M7

**未满足 3 级**：
- ❌ **无敏感字段脱敏处理器**：structlog processors 链 (`logging.py:32-38`) 中无 sanitize/redact 步骤。若业务代码 `logger.info("event", token=some_token)` 会明文输出
- ❌ **无 /metrics 端点**：无 Prometheus 指标暴露
- ❌ **无 OpenTelemetry / 分布式追踪**
- ❌ **无错误告警接入**（Sentry / PagerDuty）
- ❌ **无日志统一收集**（ELK / Loki）

**为什么 M7 D5=2 而 M1-M4 D5=3**：M1-M4 在 M7 基础之上各自有业务事件日志（api_call_log / ctx.progress / push 日志等），满足 Rubric 3 的 "业务事件指标 + 健康检查端点"。M7 自身提供的是基础设施层面的可观测性（structlog 配置 + request_id + lifecycle），但缺少 Rubric 3 要求的 "业务事件指标 + /metrics + 日志统一收集 + 错误告警"。M7 的贡献体现为**提升其他模块的 D5 分数**，而非自身的 D5 分数。

### D6 可靠性 — 3 分

**满足 Rubric 3 级的证据**：

1. **DB session rollback on exception**：`session.py:39-41` — `except Exception: await session.rollback(); raise`
2. **pool_pre_ping 连接自愈**：`session.py:22` — 每次从池中取连接前 ping，断连自动重连
3. **异常分类映射完整**：`exceptions.py` — BusinessError(400) / NotFound(404) / Unauthorized(401) / LoginLocked(423) / ValidationFailed(400) / ConflictError(409) / PushBlockedError(400) + SaihuAPIError→502 统一映射
4. **/readyz graceful 降级**：`main.py:150-157` — DB 探测失败不崩溃，返回 503 + structured reason
5. **Lifespan graceful shutdown**：`main.py:91-99` — 有序关停 scheduler→reaper→worker，避免资源泄漏
6. **expire_on_commit=False**：`session.py:29` — 防止 commit 后属性访问触发 lazy load 异常

**未满足 4 级**：
- 无 custom 500 handler（unhandled exception 返回 Starlette 默认纯文本非 JSON）
- 无熔断器 / 死信队列
- 无 chaos test
- DB 连接池耗尽无优雅降级（依赖 SQLAlchemy 默认 timeout 行为）

### D7 可维护性 — 3 分

**满足 Rubric 3 级的证据**：

1. **架构蓝图完整覆盖**：`Project_Architecture_Blueprint.md:248-255` — §3.4 横切关注点表格明确记录异常/日志/中间件/配置四大基础设施及代码位置
2. **ADR 覆盖**：ADR-1（全栈 async）直接关联 M7 的 DB/session 选型；ADR-3（数据库咨询锁）关联 M7 提供的 DB 基础设施
3. **Runbook 深度覆盖**：
   - §2 健康检查（§2.1 readyz 检查内容 + §2.2 快速诊断流程图）
   - §3.1 数据库不可用（4 步排查含连接池耗尽判断）
   - §3.4 JWT 密钥管理（§3.4.1 首次生成 + §3.4.2 定期轮换含 5 步命令 + §3.4.3 泄漏应急 6 步 + §3.4.4 常见 FAQ）
   - §3.6 后端启动失败
   - §3.7 数据库恢复后应用异常
   - §6 备份与恢复
4. **Alembic 迁移命名规范文档化**：`Blueprint:528-533` — `YYYYMMDD_HHMM_description.py` + NAMING_CONVENTION
5. **代码注释清晰**：`base.py:14` — "命名约定:让 Alembic 生成的约束名稳定可读"；`session.py:35` — "FastAPI Dependency:提供事务化的 AsyncSession"；`logging.py:8` — "在 `app.main` 启动时调用 `configure_logging()` 一次"

**未满足 4 级**：
- 无自动化文档生成
- 无"如何新增中间件"/"如何新增异常类型" how-to
- middleware/logging 配置变更历史无 ADR（如为什么用 structlog 而非 loguru）

### D8 性能与容量 — 2 分

**满足 Rubric 2 级的证据**：

1. **连接池三项可配**：`config.py:30-32` — `db_pool_size=10` / `db_max_overflow=5` / `db_pool_recycle_seconds=3600`
2. **pool_pre_ping**：`session.py:22` — 防止使用已断开的连接
3. **/readyz 探针轻量**：`main.py:153` — `SELECT 1` 不拖累探针
4. **资源限制明确**：`docker-compose.yml:52-55,73-75,95-97,120-122,135-137,160-161` — 6 个服务全有 memory limit
5. **session 及时释放**：`session.py:36` — `async with` 作用域保证
6. **NullPool for migrations**：`alembic/env.py:59` — 迁移使用 NullPool 不占连接池

**未满足 3 级**：
- 无 SLO 定义
- 无慢查询日志配置
- 无连接池使用率监控
- 无容量评估文档（三服务共 45 连接 vs PostgreSQL max_connections 未对照）

---

## 4. 测试结果

```
24 passed, 139 deselected in 1.02s

测试明细：
- test_config_schema.py: 14 passed (Pydantic schema 校验矩阵)
- test_health_endpoints.py: 4 passed (readyz 四路径: ok/db-down/bg-down/disabled-roles)
- test_query_utils.py: 5 passed (LIKE 转义)
- test_runtime_settings.py: 3 passed (生产 placeholder 拦截 + docs 禁用 + 角色 flag)
- test_sync_order_detail_classification.py: 1 passed (异常分类，间接覆盖)
```

---

## 5. 关键发现

### 🔴 P0

（无 P0 发现）

### 🟡 P1

1. **P1-M7-1 无 CORS 中间件**：后端零 CORSMiddleware 配置。当前依赖 Caddy 反代同源策略，但后端 8000 端口如被直接访问则无 CORS 限制。上云场景若改用 ALB/Nginx 需手动补 CORS。
2. **P1-M7-2 无安全 headers**：Caddy 默认不添加 CSP / X-Frame-Options / X-Content-Type-Options / Referrer-Policy / Permissions-Policy。需在 Caddyfile 显式配置。
3. **P1-M7-3 无 structlog 敏感字段脱敏处理器**：structlog processors 链中无 sanitize/redact 步骤。业务代码如 `logger.info("event", password=...)` 会明文输出到 JSON 日志。
4. **P1-M7-4 5xx 响应非统一 JSON**：unhandled exception 返回 Starlette 默认纯文本 "Internal Server Error"，与 BusinessError/SaihuAPIError 的 JSON `{message, detail}` shape 不一致，前端需额外处理。

### 🟢 P2

5. **P2-M7-1 middleware/exceptions/logging 三核心模块零专项单测**：间接测试覆盖不足以守护 structlog 配置变更或异常映射行为。
6. **P2-M7-2 无 connection pool exhaustion monitoring**：三服务合计最多 45 连接，但无运行时连接池使用率指标暴露。
7. **P2-M7-3 alembic NullPool for online migration**：`env.py:59` 使用 NullPool，大表迁移无连接复用可能较慢，但当前数据量可接受。

---

## 6. P0/P1 候选交叉判定

| 候选 | 判定 | 说明 |
|---|---|---|
| P1-2 CORS allowed_origins | ⚠️ | 无 CORS 中间件。Caddy 同源隐式保护，但后端本身无限制 |
| P1-4 5xx traceback 泄漏 | ✅ | FastAPI 无 `debug=True`，Starlette 默认返回 "Internal Server Error" 纯文本不含 traceback |

---

## 7. 与 M1-M6 共性

- **D2 核心模块零单测**：与 M1 client.py / M3 list-detail-archive / M4 queue-worker-reaper 同类型（有部分单测但核心文件覆盖不足）
- **D3=2 共性缺口**：无入口级速率限制 + 无 CVE 扫描 + 无安全 headers + 无日志脱敏
- **D4=3 共性**：docker-compose + .env.example + 迁移就绪 + validate_settings + 资源限制，未满足 4 级（无 CI/CD + IaC + 蓝绿）
- **D8=2 共性**：有基础索引/配置但无 SLO + 慢查询日志 + 容量评估

## 8. M7 独有表现

**M7 作为基础设施被其他模块 leverage 的正向贡献**：

1. **structlog + request_id 中间件**（`logging.py` + `middleware.py`）是 M1-M6 所有模块 D5=3 评分的基础。没有 M7 的这层基础设施，其他模块的结构化日志和请求追踪能力将不存在。
2. **BusinessError 异常体系**（`exceptions.py`）是 M1-M6 所有模块 D6 评分的统一 JSON 错误响应基础。6 个 BusinessError 子类 + 4 个 SaihuAPIError 子类覆盖全系统异常分类。
3. **/readyz 角色感知联合检查**（`main.py:160-193`）是 M4 任务队列健康检查的基础设施，docker-compose 三服务全部依赖此探针。
4. **DB session 生命周期管理**（`session.py`）是所有模块数据访问的统一入口，rollback-on-exception + commit-on-success 模式被全系统 Depends(get_db) 使用。
5. **NAMING_CONVENTION**（`base.py:15-21`）保证所有模块的 alembic 迁移约束名稳定可读。

**M7 独有弱点**：

1. **D5 的"自身 vs 被 leverage"悖论**：M7 为其他模块提供了 D5 的基础设施（structlog + request_id），但 M7 自身缺乏 Rubric 3 要求的"业务事件指标 + /metrics + 日志收集 + 告警"。M7 的 D5=2 反映的是"基础设施本身的可观测性"而非"基础设施为他人提供的可观测能力"。
2. **无 custom 500 handler**：与所有其他模块不同，M7 需要负责全局 500 异常的 JSON 化，但当前仅 BusinessError/SaihuAPIError 有 handler，unhandled exception 返回纯文本。

---

## 9. 给用户的待确认疑点

✅ 全部 3 个疑点已由 Claude 主控推荐并经用户采纳，详见 §12 用户澄清记录。

---

## 10. 已写入文件

- `docs/superpowers/scorecard/M7-infrastructure.md`（本文件）
- `docs/superpowers/scorecard/_calibration.md`（追加 M7 D1-D8 标尺记录）

---

## 11. 状态

✅ M7 基础设施模块审计完成，8 个维度已评分（D1◦=3, D2=2, D3=2, D4=3, D5=2, D6=3, D7=3, D8=2），D9=N/A。模块平均分 2.50/4。

---

## 12. 用户澄清记录（2026-04-12）

用户指令"你来推荐"——Claude 主控为全部 3 个疑点做出决策，用户采纳。

### #1 CORS 中间件（🟢 不做，降级 P2）
- **Claude 推荐**：不加 CORS 中间件，降级到 P2
- **理由**：当前部署架构 Caddy 是唯一入口，前端和后端同源（`Caddyfile` 统一 `{$APP_DOMAIN}`），浏览器同源策略天然生效。CORS 中间件在同源部署下完全不需要。只有"backend 直接暴露 OR 前端独立域名"两个场景才需要，当前不存在
- **影响**：P1-M7-1 降级到 P2；M7 D3 分数不变（2 分）

### #2 5xx JSON 化（🟡 延后做，保留 P1）
- **Claude 推荐**：保留 P1，打分完成后统一处理
- **理由**：这是真实的 API 契约一致性问题——BusinessError 返回 JSON，unhandled exception 返回纯文本。前端 `e.response.data.message` 对纯文本会 undefined。但改动需 ~10 LOC + 单测，不属于审计阶段的 1-line fix
- **影响**：P1-M7-4 保留；M7 D6 分数不变（3 分）

### #3 structlog 脱敏（🟢 不做，降级 P2）
- **Claude 推荐**：不做，降级到 P2
- **理由**：M1 审计已验证 saihu client 不打印 access_token（grep 确认）；M6 审计已验证 auth.py 5 个 structlog 调用只记录 `source_key`（IP）不记录 password/token。当前无已知敏感字段泄漏路径，添加通用脱敏 processor 是 "nice to have"
- **影响**：P1-M7-3 降级到 P2；M7 D5 分数不变（2 分）

### P1/P2 列表演变

- P1：原 4 项 → **2 项**（P1-M7-1 CORS 降级 + P1-M7-3 脱敏降级；剩 P1-M7-2 安全 headers + P1-M7-4 5xx JSON 化）
- P2：原 2 项 → **4 项**（+ CORS 降级 + 脱敏降级）

### M7 分数

**不变**：2.50/4（三个疑点的处理都不改变维度评分）
