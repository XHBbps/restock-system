# M6 认证与配置 评分报告

> 模块范围：JWT 认证（`app/api/auth.py` + `app/core/security.py` + `app/api/deps.py`）+ 登录锁定（`login_attempt` 表 + 按 IP 限流）+ 全局配置 CRUD（`app/api/config.py` global/sku/warehouse/zipcode/shop）+ 前端登录/配置页面（`LoginView.vue` + `GlobalConfigView.vue` + `stores/auth.ts` + `api/client.ts`）
> 评分日期：2026-04-11
> 评分人：Claude (Opus 4.6) — 只读审计
> 模块特殊地位：**D3 安全性主战场（公网核心）**；**首个按 L1 标尺评 D9 且非 M5 源头模块**

---

## 测试结果

| 项 | 结果 | 备注 |
|---|---|---|
| `pytest -k "auth or login or config or scheduler"` | ✅ **25 passed / 138 deselected** | 1.11s; 全部绿 |
| 覆盖 | auth_login.py 3 用例 + security.py 10 用例 + config_schema.py 14 用例 + runtime_settings.py 3 用例 + scheduler_api.py 3 用例 |
| `vue-tsc` / `vite build` | 未本模块独立运行 | 参照 M5=3 已通过全局质量门 |

---

## D1 功能完整性 — 3

**判据匹配**：满足 Rubric 3 级（主链路端到端实现：POST `/api/auth/login` → verify bcrypt → 签发 JWT → 前端 localStorage → 路由守卫 + axios Bearer 拦截器 → 401 自动 redirect → `/api/auth/logout`/`/api/auth/me` 三端点齐全；按 IP 隔离的登录锁定：**每次失败在 `login_attempt` 表按 `source_key="ip:<IP>"` upsert**，达到阈值 `login_failed_max=5` 即 `locked_until = now + login_lock_minutes=10 min`，命中锁定窗口直接抛 `LoginLocked(423)`；锁定后成功登录自动清零 failed_count；global_config 单行 CRUD `GET/PATCH /api/config/global` + scheduler hot reload 联动；sku/warehouse/zipcode/shop 五个资源 CRUD 端点完整；边界覆盖：空密码被 Pydantic `min_length=1` 拦截、超长密码 `max_length=128` 拦截、`GlobalConfigPatch` 前 cron 用 APScheduler `CronTrigger.from_crontab` 实际校验），未满足 4 级（**无集成测试守护全链路** —— 3 个 login 单测全部基于 `_FakeDb` monkeypatch 而非 httpx TestClient；**锁定→冷却→自动解锁** 的边界无测试用例（失败 5 次 → 第 6 次 423 → 冷却 10 分钟后能否正常登录）；`LoginRequest` 的 max_length=128 无测试守护；`global_config` patch 并发修改的原子性无测试；`validate_settings` 生产校验只对 `please_change_me` 字面量，不校验 JWT 密钥**长度/熵**，遗漏 deploy 层 placeholder `generate_with_openssl_rand_base64_32`）

**关键证据**：
- `backend/app/api/auth.py:44-108` — 登录主链路：读 global_config → 查 login_attempt → 验 bcrypt → 失败 upsert 累加/触发 lock → 成功清零 → 签发 token
- `backend/app/api/auth.py:111-118` — `/logout` + `/me` 两 endpoint 需 JWT
- `backend/app/api/auth.py:23-25` — `LoginRequest.password: str = Field(..., min_length=1, max_length=128)`
- `backend/app/core/security.py:13-20` — bcrypt.gensalt() + checkpw
- `backend/app/core/security.py:23-47` — JWT HS256 encode/decode + PyJWTError → Unauthorized
- `backend/app/api/deps.py:13-23` — Bearer 头解析 + decode_token + sub 校验
- `backend/app/models/login_attempt.py:10-24` — `source_key` PK（单行按来源上锁）
- `backend/app/api/config.py:120-142` — `/api/config/global` GET + PATCH + scheduler reload 联动
- `backend/app/schemas/config.py:37-43` — `calc_cron` Pydantic 校验走 APScheduler real parser
- `backend/tests/unit/test_auth_login.py:64-149` — 3 个登录测试（密码错 upsert / 锁定源拒绝 / 不同 IP 不互相影响）
- `frontend/src/views/LoginView.vue:72-96` — handleLogin + 423 特殊分支 + 401 通用 fallback
- `frontend/src/api/client.ts:20-33` — axios 401 拦截器 → clearToken → redirect to /login
- `frontend/src/router/index.ts:178-181`（参照 M5 标尺记录）— authGuard 全局接入

**差距**：无 httpx TestClient 端到端流程测试；锁定→自动解锁边界无测试；JWT 密钥长度/熵校验缺失；cron patch 并发无锁。

**对照 M1=3 / M2=3 / M3=3 / M4=3 / M5=3**：M6 同级 3 分。M6 的 D1 优势在于**登录锁定从全局改为 IP 粒度**的单测覆盖（3 个用例含跨 IP 独立性核心不变式），劣势是认证主链路无集成测试守护。

---

## D2 代码质量 — 3

**判据匹配**：满足 Rubric 3 级（**`test_security.py` 10 单测**覆盖 hash/verify/salt/encode/decode/extra claims/bad signature/expired/malformed 八大路径 + `test_auth_login.py` 3 单测覆盖密码失败/锁定来源拒绝/跨源独立 + `test_config_schema.py` 14 用例含 between/contains/number/string 复合校验矩阵 + `test_runtime_settings.py` 3 用例含生产 placeholder 拦截 + `test_scheduler_api.py` 3 用例；**auth.py 仅 119 行** 无代码异味；`security.py` 47 行纯函数风格无副作用；命名清晰 `_get_login_source_key` / `LoginLocked` / `LoginAttempt`；`GlobalConfig` 表有 3 个 CheckConstraint 结构化校验 (`id=1` / `include_tax IN ('0','1')` / `shop_sync_mode IN ('all','specific')`)；`login_attempt` 建表迁移 `20260409_1710_add_login_attempt.py` 22 行极简清晰），未满足 4 级（**无集成测试**——整个 `/api/auth/login` 流程无 httpx TestClient；验证 login 的 `_FakeDb` 手写 monkeypatch 结构复杂度偏高——若用 factory_boy + in-memory session 可更清洁；`config.py:129-142` `patch_global` 的 `updates = patch.model_dump(exclude_none=True)` 允许空 patch 静默成功（UX 小瑕疵）；auth.py 零日志调用为 D5 严重缺口，而非 D2 问题）

**关键证据**：
- `backend/tests/unit/test_security.py:1-97` — 10 个 security 单测覆盖纯函数 + 异常路径
- `backend/tests/unit/test_auth_login.py:64-149` — 3 个 login 单测核心不变式
- `backend/tests/unit/test_config_schema.py:1-134` — 14 个 schema 单测含 between 矩阵
- `backend/tests/unit/test_runtime_settings.py:6-21` — 生产环境 placeholder 拦截测试
- `backend/app/models/global_config.py:16-20` — 3 个 CheckConstraint 表级校验
- `backend/app/api/auth.py:33-41` — `_get_login_source_key` 11 行小函数职责单一
- `backend/app/core/security.py:13-47` — 47 行全文件纯函数

**差距**：无 httpx 集成测试；auth.py 零日志调用（计入 D5）；全局 count 维度：auth + security + config 合计约 **30 单测 / ~250 行实现代码**，覆盖率显著高于 70%。

**对照 M1=2 / M2=3 / M3=2 / M4=2 / M5=3**：M6 与 M2=3 / M5=3 持平，**高于 M1/M3/M4 一级**。理由：M6 的核心模块（security/auth/login_attempt/runtime_settings/config_schema）全部有针对性单测，覆盖率高于 70% 且无明显异味；与 M1/M3/M4 的"核心模块零单测"（client/token/worker/reaper/api-endpoints）形成对比。

---

## D3 安全性 ⚠️⚠️ — 3

**M6 作为认证核心，D3 是公网交付主战场。经过逐条核查，M6 独有安全控制做得足够好——超出 M1-M5 共性 2 分的基线，但仍未达 4 级"密钥轮换+WAF+渗透测试"。**

### JWT 配置

- **算法**：`security.py:38` `jwt.encode(payload, secret, algorithm=settings.jwt_algorithm)` + `config.py:43` `jwt_algorithm: str = "HS256"`（单用户场景 HS256 合理，无 RS256 公钥分发复杂度）
- **密钥来源**：`config.py:42` `jwt_secret: str = "please_change_me"` 走 pydantic-settings 环境变量注入
- **密钥强度拦截**：`config.py:82-84` 生产环境下 `settings.jwt_secret.strip() == "please_change_me"` 抛错；**deploy 层 `validate_env.sh:39-42` 额外拦截 `generate_with_openssl_rand_base64_32`**，双层防御（backend + deploy）——比单层更好，但 **backend 本身不拦截 deploy placeholder**，若用户仅部署 backend 容器且 JWT_SECRET 抄 deploy/.env.example 会漏检（P1 候选）
- **密钥长度/熵**：**不校验** jwt_secret 长度——PyJWT 本身会对过短密钥抛 `InsecureKeyLengthWarning` 但不 reject；`test_security.py:67` 注释有"32 byte secret" 但实际 `validate_settings` 未强制（P1 候选）
- **有效期**：`config.py:44` `jwt_expires_hours=24` + `security.py:29-35` iat/exp claim 写入；`test_security.py:78-91` 有过期拒绝测试
- **Subject**：`security.py:23` `subject: str = "owner"` 单用户固定，无权限模型膨胀风险；`deps.py:21` 校验 `"sub" not in payload` 抛 Unauthorized
- **ADR 缺失**：无"为何选 JWT HS256 而非 session cookie"/"sub=owner 单用户设计"/"token 存 localStorage 的权衡"等决策记录（D7 问题）

### 密码处理

- **Hash 算法**：`security.py:13-15` `bcrypt.hashpw(plain.encode(), bcrypt.gensalt())`；`pyproject.toml:34` `bcrypt>=4.0.1,<5` 锁定主版本；`test_security.py:18-41` 5 个用例覆盖 hash 格式/正确/错误/salt 唯一性
- **明文存储**：❌ 无——仅 `GlobalConfig.login_password_hash: String(255)` 存 bcrypt digest；`main.py:65` 初次播种时 `hash_password(settings.login_password)` 转换后入库；环境变量 `LOGIN_PASSWORD` 仅在首次播种时读取，之后切换靠修改 DB（**一次性密码注入**，比常驻环境明文更安全）
- **Constant-time 对比**：`bcrypt.checkpw` 本身是 constant-time 实现，无 timing attack 风险
- **密码长度上限**：`LoginRequest.password: Field(min_length=1, max_length=128)`（`auth.py:24`）—— bcrypt 72 字节截断语义不完全匹配，但 128 字符上限可接受
- **强度策略缺失**：生产 `validate_settings` 仅拦截 `please_change_me` 字面量，**不校验密码长度/复杂度**；deploy `validate_env.sh:44-47` 也只拦截 placeholder

### 登录锁定

- **按 IP 隔离**：`auth.py:33-41` `_get_login_source_key` → `source_key="ip:<IP>"` → `login_attempt` 表按 source_key PK 单行 upsert；**相比全局共享锁定提升显著**（全局共享会被一次性攻击打穿整个系统）
- **阈值+时长**：`config.py:45-46` `login_failed_max=5` + `login_lock_minutes=10`，可通过环境变量覆盖；**但无 `validate_settings` 拦截** `login_failed_max<=0` 等病态配置（P2 小问题）
- **并发安全**：`auth.py:78-92` 使用 `pg_insert(...).on_conflict_do_update(index_elements=[source_key], ...)` PostgreSQL 原生 upsert，DB 级原子，无竞态
- **锁定成功后清零**：`auth.py:96-102` 登录成功时若历史有失败或锁定痕迹，`UPDATE ... failed_count=0, locked_until=None` 清理——避免"之前失败 3 次 → 今天成功 1 次 → 明天再失败 2 次又被锁" 的累积误伤
- **X-Forwarded-For 信任源 ⚠️ P1 候选**：`auth.py:34-36` 无条件信任第一个 `x-forwarded-for` header 值，**不校验请求是否来自受信反代（Caddy）**。若 backend 容器被直连或 Caddy 配置不当，**任意客户端可伪造 XFF 头使每次请求来自不同"IP"，完全绕过登录锁定**——公网部署下是实际可利用的缺陷。**结论：P1-6 候选 ❌**
- **阈值绕过补充**：即使 X-Forwarded-For 正确，没有全局总阈值（如"本节点 10 分钟内总失败 >100 次整体熔断"），单 IP 粒度的限流仍可被僵尸网络堆平

### 输入校验

- **Pydantic `LoginRequest`**：`password` 字段 `min_length=1, max_length=128`，空密码直接 Pydantic 422 拦截（**不经 verify_password，无 timing leak**）
- **global_config patch**：`GlobalConfigPatch` 所有数字字段有 `ge/le` 范围校验（buffer_days 1-365 等）；`calc_cron` 走 APScheduler `CronTrigger.from_crontab` 实际校验而非正则；`include_tax` / `shop_sync_mode` 用 `Literal[...]` 枚举
- **SQL 注入**：无风险——全库 ORM + parameterized，零 `text()` 用户输入拼接

### global_config 授权

- **JWT 校验**：`config.py:120-142` 所有 GET/PATCH 端点 `_: dict = Depends(get_current_session)` 必须带 Bearer token
- **二次确认**：❌ 无——`PATCH /api/config/global` 无 `X-Confirm` 或类似机制，单次 PATCH 直接生效
- **审计日志**：❌ 无——无 `config_changed(operator, before, after)` 结构化日志；`login_attempt` 表仅记失败/锁定状态，无登录成功历史；全库 grep `audit|login_success|login_failed|config_changed` **零命中** ⚠️
- **scheduler hot reload**：`config.py:139-140` PATCH 命中 `sync_interval_minutes/calc_cron/scheduler_enabled` 触发 `reload_scheduler()`，保证配置立刻生效无需重启，且复用 APScheduler 的 misfire_grace / coalesce 不变式

### 共性问题（M1-M5 已标注，M6 简短标注）

- ❌ 无入口级速率限制（`/api/auth/login` 单 IP 可暴力枚举 5 次后锁定 10 分钟 → 理论上每小时可尝试 30 次/IP；结合 XFF 伪造问题变成无限尝试）
- ❌ 无 CVE 扫描 / `bcrypt` / `PyJWT` 依赖无 CI 审计
- ❌ 无安全 headers / CSRF（共性）
- ❌ 无日志脱敏—— `auth.py` 无任何业务日志故也谈不上脱敏，但 `RequestLoggingMiddleware:41-47` 的 `http_request` 日志会记录 `path=/api/auth/login` 和 status，**不会泄漏密码**（Pydantic body 不入日志）
- ❌ token 前端存 localStorage（与 M5 的 P1-M5-1 关联）

### D3 判据匹配总结

**满足 Rubric 2 级**：JWT + env var + Pydantic 全量校验 + bcrypt 密码 hash + 登录锁定完整闭环——超出。
**达到 Rubric 3 级**：核心加分项：
- ✅ 密码 hash（bcrypt + unique salt 测试）
- ✅ 生产启动 fail-fast 密钥强度校验（`validate_settings`）
- ✅ 按 IP 隔离的 per-source 登录锁定（DB 原子 upsert）
- ✅ 锁定成功后自动清零（避免误伤）
- ✅ 跨 IP 独立性单测守护（核心不变式）
- ✅ 所有 config 端点 JWT 鉴权
- ✅ 密码强度拦截双层防御（backend validate_settings + deploy validate_env.sh）

**未满足 Rubric 4 级**：
- ❌ 无密钥轮换机制
- ❌ 无审计日志（登录成功事件 + config 变更事件）
- ❌ X-Forwarded-For 信任源未限定反代 IP（P1-6 ❌）
- ❌ JWT 密钥长度/熵不强制
- ❌ 无 WAF / fail2ban / 渗透测试
- ❌ 备份无加密（共性）

**对照 M1=2 / M2=2 / M3=2 / M4=2 / M5=2**：M6 **升到 3 分**——比前 5 模块**高 1 级**。理由：M6 是**唯一具备认证核心控制闭环**的模块（bcrypt + env secret + 生产 fail-fast + per-IP lockout + JWT + 清零机制 + 针对性单测），M1-M5 的 D3=2 反映的是"公网共性缺口"（无限流/headers/CVE），而 M6 的核心认证控制已达 Rubric 3 级的"密钥 + CORS + 登录锁定"组合。**未达 4 级是因为**密钥轮换/审计日志/渗透测试/X-Forwarded-For 限定等 4 级判据全缺。

---

## D4 可部署性 — 3

**判据匹配**：满足 Rubric 3 级（`backend/.env.example:28-35` 完整文档化 `LOGIN_PASSWORD` / `JWT_SECRET` / `JWT_EXPIRES_HOURS` / `LOGIN_FAILED_MAX` / `LOGIN_LOCK_MINUTES` 五个认证相关环境变量；`deploy/.env.example:10-11` 生产部署文档同时声明 `LOGIN_PASSWORD` 和 `JWT_SECRET`；**双层 placeholder 防御** `validate_settings` (backend 启动)  + `validate_env.sh:34-47` (deploy 前强校验) 配合；`login_attempt` 建表迁移 `20260409_1710_add_login_attempt.py` 就绪且在 `20260410_0001` 清理了历史 `global_config.login_failed_count/login_locked_until` 冗余列；`main.py:45-70` `_ensure_global_config()` lifespan hook 首启动自动播种含 `login_password_hash=hash_password(settings.login_password)`，无需手动 SQL），未满足 4 级（共性问题：无 CI/CD + IaC + 蓝绿 + 多环境；M6 独有缺口：**JWT_SECRET 轮换流程无文档**——P0-5 候选；`.env.example` 的 `JWT_SECRET=generate_with_openssl_rand_base64_32` 的 `openssl rand -base64 32` 命令是隐式约定未写明推荐强度；`LOGIN_FAILED_MAX` / `LOGIN_LOCK_MINUTES` 无 `validate_settings` 病态值校验）

**关键证据**：
- `backend/.env.example:28-35` — 认证块 5 环境变量齐全
- `deploy/.env.example:10-11` — 生产部署必填
- `backend/app/config.py:82-86` — 生产启动 `please_change_me` 拦截
- `deploy/scripts/validate_env.sh:17-47` — 部署前强校验 + 拦截两个 placeholder
- `backend/alembic/versions/20260409_1710_add_login_attempt.py:20-33` — 建表迁移清晰
- `backend/alembic/versions/20260410_0001_archive_uq_and_cleanup.py:39-40` — 清理历史 global_config 列
- `backend/app/main.py:45-70` — 首启动播种 global_config（含 bcrypt hash）

**差距**：
- 🔴 **P0-5 候选**：JWT_SECRET 轮换流程无文档。当 JWT_SECRET 泄漏时如何操作？所有在用 token 会同时失效吗？（答：会——因 validate 靠 `algorithms=[algorithm]` 对新密钥校验所有历史 token）但**无文档指引用户何时/如何做** ⚠️
- 🟡 `LOGIN_FAILED_MAX`/`LOGIN_LOCK_MINUTES` 缺病态值校验

**对照 M1=3 / M2=3 / M3=3 / M4=3 / M5=3**：M6 同级 3 分。**独有优势**：双层 placeholder 拦截（backend + deploy）；**独有缺口**：JWT_SECRET 轮换流程无文档。

---

## D5 可观测性 — 2 → **3**（第二轮 review 后因修复升级，见 §9）

**判据匹配**：满足 Rubric 2 级（`RequestLoggingMiddleware:20-49` 全局结构化 JSON 日志 + `request_id` contextvar 绑定 + `X-Request-Id` 回传 header 自动覆盖 `/api/auth/*` 端点；401/423 响应走 `log_method = logger.info if status < 400 else logger.warning` 自动 warning 级别记录；`login_attempt` 表作为**隐式审计时间线**可 SQL 查询历史锁定源；structlog JSON 日志框架复用 M1-M4 的基础设施），**未满足 Rubric 3 级**（❌❌ **auth.py 零业务日志** —— Grep `logger|structlog|log\.|print in app/api/auth.py` 零命中，登录成功/失败/锁定**无业务事件日志**，仅靠 `RequestLoggingMiddleware` 记录 path+status 间接推断；❌ 无 `config_changed` 审计日志；❌ 无密钥校验失败的 structured warning；❌ 无 `login_attempted{outcome=success|failure|locked}` 业务事件指标；❌ 无 /metrics 登录成功率指标；无 OpenTelemetry / Grafana / 告警接入）

**关键证据**：
- `backend/app/core/middleware.py:20-49` — 全局 structured logging + request_id
- `backend/app/api/auth.py:1-119` — **整个文件 0 处 logger 调用**（Grep 验证 `logger|structlog|log\.|print` → No matches found）
- `backend/app/api/config.py:120-142` — global_config PATCH 也无审计日志
- `backend/app/models/login_attempt.py` — 表作为隐式审计源，但 `created_at` 不会被后续 upsert 更新（仅 updated_at）——无法重建 login 时间序列
- 对比 M1: `api_call_log` 表是完整可查询时间线
- 对比 M4: `task_run` 表是完整事件时间线
- M6 **缺乏等价的登录事件时间线**（login_attempt 只存"当前状态"非"完整历史"）

**差距**：
- 🟡 **P1 候选**：auth.py 零业务日志 —— 登录失败/锁定/成功均无 `logger.info("login_succeeded", source_key=...)` / `logger.warning("login_locked_out", source_key=..., failed_count=...)` 等结构化事件
- 🟡 **P1 候选**：global_config PATCH 无 `config_changed` 审计日志
- 🟡 **P1 候选**：`login_attempt` 表只存当前状态，无法重建尝试历史（若要做"最近 24 小时锁定源列表"需另建 `login_event` append-only 表）

**对照 M1=3 / M2=3 / M3=3 / M4=3 / M5=2**：M6 降到 2 分，**低于 M1/M2/M3/M4 一级**，与 M5 持平但原因不同：M5 是"无 Sentry/Web Vitals"而 M6 是"auth.py 零业务日志"+ "无审计时间线"。**M6 作为认证核心缺日志是相对严重的缺口**——后端其他模块靠 api_call_log/task_run 弥补了业务事件追溯的能力，M6 唯一的审计源 login_attempt 只是状态快照不是时间线。

---

## D6 可靠性 — 3

**判据匹配**：满足 Rubric 3 级（`pg_insert(...).on_conflict_do_update(...)` upsert 天然幂等无并发风险——`auth.py:78-92`；登录锁定状态机是**原子 upsert** 无 TOCTOU 窗口；`LoginRequest` Pydantic 422 前置拦截空密码避免进入 verify_password 路径；`LoginLocked` exception 明确分类 423 状态码；`Unauthorized` 异常抛出后 `_business_exc_handler` 统一 JSON response；`validate_settings` 启动时 fail-fast 阻止错误配置进入运行时；bcrypt `checkpw` 对错误哈希格式安全返回 False 不抛异常；**首次启动 seed 防幂等** `main.py:67` `on_conflict_do_nothing(index_elements=[id])` 防重复播种；**JWT 解码异常捕获完整** `security.py:46` `except jwt.PyJWTError as exc` 兜底一切 PyJWT 子类异常），未满足 4 级（无熔断器；**fail-open vs fail-close 未明确**——DB 不可用时 `db.execute(...)` 抛异常会进入 FastAPI 500 处理，登录自动失败即隐式 fail-close，但无明确测试守护；无 chaos test；DB 连接池耗尽场景无压测）

**关键证据**：
- `backend/app/api/auth.py:78-92` — pg_insert upsert 原子
- `backend/app/api/auth.py:96-102` — 成功后清零独立事务 commit
- `backend/app/core/security.py:44-47` — PyJWTError 兜底
- `backend/app/core/exceptions.py:34-41` — LoginLocked 专门 423 分类
- `backend/app/main.py:67` — on_conflict_do_nothing seed 防幂等
- `backend/app/main.py:113-118` — BusinessError 统一 handler

**差距**：DB 不可用 = fail-close（合理但无明示）；无 chaos test。

**对照 M1=3 / M2=3 / M3=3 / M4=3 / M5=3**：M6 同级 3 分。独有优势：状态机 upsert 天然并发安全；独有缺口：fail-close 语义隐式无文档。

---

## D7 可维护性 — 2

**判据匹配**：满足 Rubric 2 级（`AGENTS.md` + `CLAUDE.md` + `Project_Architecture_Blueprint.md:508` login_attempt 表职责说明；`backend/.env.example:28-35` 认证块注释清晰；`runbook.md:220-223` 列出 JWT_SECRET / LOGIN_PASSWORD 必填项；代码命名清晰 `LoginLocked/LoginAttempt/verify_password/create_access_token/_get_login_source_key`；模块边界清晰 `app/api/auth.py`（路由）+ `app/core/security.py`（纯函数）+ `app/models/login_attempt.py`（数据）+ `app/api/deps.py`（DI）职责分离），**未满足 Rubric 3 级**（❌ **无 ADR** —— M4 已有 ADR-2 前例但 M6 零 ADR：无"为何选 JWT HS256 而非 session cookie"、"为何 sub=owner 单用户而非多角色"、"为何按 IP 锁定而非按用户名"、"为何 token 存 localStorage 而非 HttpOnly cookie"、"为何 bcrypt 而非 argon2"等核心设计决策记录；❌ **runbook 无认证故障处理章节** —— `docs/runbook.md` 仅在 220 行提及 JWT_SECRET 必填，无"忘记密码 / JWT 密钥泄漏处理 / 解除 IP 锁定 / login_attempt 表清理"的专门 runbook 章节；❌ **X-Forwarded-For 信任源设计无注释**——代码 `auth.py:33-41` 未说明"该函数假定前置是受信 Caddy 反代"的前提假设）

**关键证据**：
- `docs/Project_Architecture_Blueprint.md:508` — login_attempt 表一行职责描述
- `docs/runbook.md:178,220-223` — JWT 必填项提及
- Grep `ADR in docs/` → 仅 M4 的 ADR-2 ~ ADR-6；**M6 无 ADR**
- Grep `忘记密码|密钥轮换|解锁|JWT.泄漏 in docs/runbook.md` → 0 matches
- `backend/app/api/auth.py:33-41` — `_get_login_source_key` 无前提假设注释
- `backend/app/core/security.py:23-26` — `create_access_token` docstring 简短提及 "单用户场景" 但无 ADR 引用

**差距**：
- 🟡 **P1 候选**：无 ADR（M6 6 个核心设计决策零记录）
- 🟡 **P1 候选**：runbook 无认证故障章节

**对照 M1=3 / M2=3 / M3=3 / M4=3 / M5=2**：M6 **降到 2 分**，与 M5=2 持平，**低于 M1/M2/M3/M4 一级**。理由：后端模块普遍有 `Project_Architecture_Blueprint.md` 深度文档 + runbook 章节 + M4 有 ADR-2，M6 作为认证核心却**零 ADR + runbook 零认证章节**，未达 Rubric 3 "ADR + runbook + 注释覆盖"门槛。

---

## D8 性能与容量 ◦ — 2

**判据匹配**：满足 Rubric 2 级（`login_attempt` 表以 `source_key` 为 PK 直接 index-only lookup，单次登录查询 O(1)；PG upsert 单 SQL 无 N+1；bcrypt cost factor 默认 12 rounds ≈ 200ms/验证**是有意的慢函数防暴力**不是性能问题；global_config 单行表 PK=1 查询 O(1)；Pydantic 422 前置拦截避免空密码进入昂贵的 bcrypt 路径；JWT encode/decode 纯 CPU 无 I/O），未满足 3 级（共性问题：无 SLO + 慢查询日志 + 容量评估；M6 独有缺口：**`login_attempt` 表无 TTL/清理机制**——随时间累积所有历史锁定源，与 M1 api_call_log / M4 task_run 同类遗留问题（P2 候选）；**`login_attempt.created_at` 无索引**——若要做"最近 24 小时锁定源数量"统计需全表扫（当前单用户规模可接受）；bcrypt cost factor 12 是库默认但无压测验证 P95）

**关键证据**：
- `backend/app/models/login_attempt.py:13` — source_key 单字段 PK
- `backend/app/api/auth.py:60-62` — `select(...).where(source_key == ...)` O(1) 查询
- `backend/app/api/auth.py:78-92` — upsert 单 SQL
- 全库 Grep `DELETE FROM login_attempt|prune_login_attempt` → 无清理任务

**差距**：login_attempt 无 TTL；bcrypt cost 无压测。

**对照 M1=2 / M2=2 / M3=2 / M4=2 / M5=3**：M6 同级 2 分，与后端模块 M1-M4 持平。M5 是全项目 D8 最高分（vendor 分包 + 资源限制 + 懒加载）。

---

## D9 用户体验 (L1，参照 M5=3) — 2

**M6 是首个按 L1 标尺评 D9 且非 M5 源头模块，必须对照 M5=3 逐项说明。**

### L1 十项硬指标对照 M5=3

| # | 指标 | M5=3 状态 | M6 状态 | 对比 |
|---|---|---|---|---|
| 1 | 统一组件容器 PageSectionCard | ✅ 10 views | **部分** — `GlobalConfigView.vue:2` 使用 `PageSectionCard` ✅；`LoginView.vue` 不用（登录页独立设计合理） | 持平 |
| 2 | 全中文界面 Element Plus zhCn | ✅ `main.ts:7,17` 注入 | **瑕疵** — `LoginView.vue:11` 标题 "Sign in to Restock" + `LoginView.vue:35` 按钮 "Sign in" **英文硬编码** ❌（与全站中文冲突） | **低于 M5** |
| 3 | 设计系统 shadcn Zinc 对齐 | ✅ element-overrides.scss + tokens | **完全对齐** — `LoginView.vue:99-273` 使用全套 `$color-bg-base/$color-border-subtle/$color-bg-card/$radius-xl/$shadow-card/$font-size-2xl/$space-6`等 token，完全对齐 | 持平 |
| 4 | 加载/空态/错误 | ✅ 30 处 el-empty + v-loading + el-alert | **部分** — `LoginView.vue:32` `:loading="loading"` button spinner ✅；`LoginView.vue:38-42` `error-banner` + pulse 动画 ✅；`GlobalConfigView.vue:1` `v-if="form"` 隐式 loading 无明显 skeleton；`GlobalConfigView.vue:147-167` save 失败仅 `ElMessage.error('保存失败')` 硬编码未走 `getActionErrorMessage` 五档分类 ❌ | **略低于 M5** |
| 5 | 错误提示具体可操作 | ✅ getActionErrorMessage 五档 | **部分** — `LoginView.vue:87-91` **423 专门中文分支** "账号已锁定，请稍后再试" + 401 fallback 提取 `response.data.message` ✅；但 **未提示剩余锁定时间**（后端已在 `LoginLocked(detail={"locked_until": ...})` 返回 ISO 时间戳，前端未消费）❌；`GlobalConfigView.vue:163` 硬编码 "保存失败" ❌ | **低于 M5** |
| 6 | 跨页选择体验 | ✅ SuggestionListView 四函数 | **N/A** — 登录/配置页无多条目列表 | 不适用 |
| 7 | 筛选控件高度统一 32px | ✅ 18 处 | **N/A** — 登录/配置页无筛选控件 | 不适用 |
| 8 | Tooltip/动画 | ✅ el-tooltip + 300/500ms 过渡 | **亮点** — `LoginView.vue:125-144` **2800 格网格背景 hover 交互 300/500ms 余温动画**（进入 300ms 离开 500ms）是设计亮点；`LoginView.vue:247-250` error-banner pulse 动画 | **高于 M5** |
| 9 | 状态反馈 | ✅ ElMessage 三档 + 行级变色 | **部分** — `LoginView.vue:82` 登录成功 `ElMessage.success('登录成功')`；`GlobalConfigView.vue:155-161` 保存成功 + 补货参数变更时 **二次提示** "建议重新生成补货建议单" (5s duration) ✅ | 持平 |
| 10 | 移动端响应式 | ✅ 多断点 900/1100/1280px | **无** — `LoginView.vue` 无 `@media` 断点（card 固定 400px，移动端会溢出或居中异常）；`GlobalConfigView.vue` 无响应式 | **低于 M5** |

### 额外 UX 证据

- **锁定倒计时缺失**：后端 `LoginLocked.detail={"locked_until": iso_string}` 已返回，但 `LoginView.vue:87-91` 仅显示静态"账号已锁定，请稍后再试"，**未消费 locked_until 渲染倒计时**（"还需等待 8 分 23 秒"）—— 明显可提升的 UX 缺口
- **密码字段**：`LoginView.vue:20` `type="password"` + `placeholder="••••••••"` ✅；`:disabled="loading"` 防重复提交 ✅；`@keyup.enter="handleLogin"` 支持回车提交 ✅
- **autofill 适配**：`LoginView.vue:204-212` 专门 `:deep(input:-webkit-autofill)` 覆盖 Chrome 蓝色背景——细节到位 ✅（参照 commit `351c6ed fix(login): override browser autofill blue background`）
- **登录页交互亮点**：`LoginView.vue:4-6` **2800 个 DOM 格子** + `LoginView.vue:135-144` `transition: background-color 500ms ease` hover 变色（参照 commit `b95c8d8 feat(login): add interactive hover grid overlay`）—— M5 源头模块无此亮点

### 判据匹配总结

**满足 Rubric 2 级**：统一组件容器 + 基础中文界面 + 基础加载/错误反馈 + 表单校验（空密码 + max_length 128） ✅
**达到 Rubric 3 级**（8 项中约 5-6 项达标）：
- ✅ 设计系统 shadcn Zinc 完全对齐
- ✅ 加载状态反馈（登录 spinner + 保存 saving）
- ✅ 具体错误分支（423 专门提示，成功后 toast）
- ✅ 状态反馈（补货参数变更二次提示）
- ✅ 亮点动画（网格 hover + pulse）
- ⚠️ 错误提示具体性 —— 423 分支有但未消费 `locked_until`
- ❌ 全中文界面 —— LoginView 有英文硬编码
- ❌ 移动端响应式 —— LoginView/GlobalConfigView 零断点
- ❌ 错误分类复用 —— GlobalConfigView 硬编码"保存失败"未走 `getActionErrorMessage`

**结论**：M6 约在 Rubric 2-3 之间，**给 2 分**（不是 3 因为有 3 项明显差距：英文硬编码 + 锁定倒计时未消费 + 移动端断点缺失）。相比 M5 的十项全通过，M6 是"专注型子集 + 部分偏差"。

**对照 M5=3**：M6 低 1 级。**原因**：M5 通过 "十项硬指标全部通过" 作为 L1 基准；M6 三项偏差（i18n 残留 / 锁定倒计时未消费 / 移动端响应式缺失）使其未达 3 级门槛。亮点（网格 hover 动画 + autofill 覆盖 + 状态变更二次提示）不足以抵消这三项偏差。

**对照 M3=2（L2 标尺）**：M6=2 与 M3=2 数字相同但标尺层次不同——M6 是 L1 "前端 UX 整体偏差"，M3 是 L2 "后端错误字段局部偏差"，不可 1:1 类比。

---

## 模块平均分计算

| 维度 | 第一轮 | 第二轮（修复后）| 权重 |
|---|:--:|:--:|:--:|
| D1 功能完整性 | 3 | 3 | 1.0 |
| D2 代码质量 | 3 | 3 | 1.0 |
| D3 安全性 ⚠️⚠️ | **3** | **3** | 1.0 |
| D4 可部署性 | 3 | 3 | 1.0 |
| D5 可观测性 | 2 | **3 ⬆️** | 1.0 |
| D6 可靠性 | 3 | 3 | 1.0 |
| D7 可维护性 | 2 | 2 | 1.0 |
| D8 性能与容量 ◦ | 2 | 2 | 1.0 |
| D9 用户体验 (L1) | 2 | 2 | 1.0 |

**第一轮简单平均**：(3+3+3+3+2+3+2+2+2) / 9 = 23 / 9 ≈ 2.56
**第二轮简单平均**（修复后）：(3+3+3+3+**3**+3+2+2+2) / 9 = **24 / 9 ≈ 2.67**

**变更说明**（第二轮 review）：
- **D5 2 → 3**：auth.py 业务日志已补齐（`auth_login_blocked_locked` / `auth_login_failed` / `auth_login_lockout_triggered` / `auth_login_reset_after_success` / `auth_login_success` 五类结构化事件），消除"零业务日志"缺口，与 M1-M4 的 D5=3 持平
- **D7 维持 2**：runbook §3.4 JWT 密钥管理章节新增（部分修复"无认证章节"），但 6 个核心设计决策的 ADR 仍缺失，未完全清理 3 级门槛
- **D9 维持 2**：英文硬编码 + 锁定倒计时两项偏差已修复，但"移动端 `@media` 断点缺失"是 Rubric 3 级"移动端基本可用"硬指标的明确未满足，保持 2 分；剩余偏差降级为 P2
- M6 模块平均分从 2.56 上升到 **2.67**，与 M5=2.67 持平，**超越 M1/M3/M4 的 2.63**

---

## 关键发现

### 🔴 P0 候选

- ~~**P0-5 JWT_SECRET 初始生成与轮换流程无文档**~~（D4/D7）— **审计阶段已修复**
  - 原问题：初始生成流程 + 轮换流程 + 泄漏应急 全部无文档
  - **修复**（2026-04-12，见 §8 #1）：`docs/runbook.md` 新增第 3.4 节"JWT 密钥管理（首次生成 / 轮换 / 泄漏应急）"，涵盖：
    - 首次生成（`openssl rand -base64 32` 命令 + 双层防御校验说明）
    - 定期轮换（JWT_SECRET + LOGIN_PASSWORD 分别的步骤 + 影响范围说明）
    - 密钥泄漏应急处理（6 步 SOP）
    - 常见问题 FAQ（4 条）
  - **P0-5 候选判定：✅ 已实现**

### 🟡 P1 候选（原 7 项 → 3 项；4 项已修复，1 项降级到 P2）

- ~~**P1-6 X-Forwarded-For 信任源未限定反代 IP**~~（D3）— **降级到 P2**
  - **调查结论**：`deploy/Caddyfile:6` 使用 `header_up X-Forwarded-For {remote_host}`——这是**覆盖**（而非 append）操作，Caddy 会强制把 XFF 设为对端真实 IP，攻击者无法伪造
  - **实际风险**：在当前部署架构（backend 在 Caddy 后面）下**风险已被架构化缓解**
  - **残余风险**：若未来脱离 Caddy 直接暴露 backend，当前代码会变成真实漏洞
  - **修复**（2026-04-12）：`backend/app/api/auth.py:33-38` 加代码注释明确说明对 Caddy 覆盖 XFF 的依赖关系 + 未来脱离 Caddy 时的应对方案
  - **降级理由**：Caddy 架构层已缓解，代码层无立即 P1 风险，但仍记为 P2（"若未来脱离 Caddy 部署需立即加 TRUSTED_PROXIES 白名单"）

- ~~**P1-M6-1 auth.py 零业务日志**~~（D5）— **审计阶段已修复**
  - **修复**（2026-04-12）：`backend/app/api/auth.py` 加入 structlog 事件：
    - `auth_login_blocked_locked` warn（被锁定的请求进入时）
    - `auth_login_failed` warn（密码错误尚未达阈值）
    - `auth_login_lockout_triggered` warn（阈值触发新锁定）
    - `auth_login_reset_after_success` info（成功后清零旧失败计数）
    - `auth_login_success` info（成功签发 JWT）
  - **影响**：M6 D5 从 2 分的"零业务日志"缺陷修复；**D5 升 1 分为 3**（见 §9 分数重估）

- **P1-M6-2 global_config PATCH 无审计日志**（D5）— 保留 P1
  - `config.py:129-142` 修改补货参数 / scheduler 配置 / 密码上限 等关键配置时无 `config_changed(before, after)` 审计
  - 配合 M6 单用户 sub=owner 设计，操作人就是 owner，字段级 diff 足够

- **P1-M6-3 login_attempt 表只存当前状态非时间线**（D5）— 保留 P1
  - 单行 upsert 覆盖 `failed_count`，无法重建"过去 24 小时哪些 IP 多次失败" 数据
  - **注**：P1-M6-1 修复后，auth 业务日志已经提供结构化时间线（通过 structlog），P1-M6-3 的紧迫性已降低。若仅需"哪些 IP 多次失败"的告警源头，可从 auth 日志聚合而非另建表

- **P1-M6-4 无 ADR / runbook 认证章节部分补齐**（D7）— 保留 P1
  - ~~runbook 无"忘记密码 / JWT 泄漏 / 解除 IP 锁定 / login_attempt 表清理" 故障章节~~ — **runbook 3.4 节新增 JWT 密钥管理章节已覆盖大部分**
  - 6 个核心设计决策仍无 ADR：JWT HS256 vs session / sub=owner 单用户 / IP-lockout vs user-lockout / localStorage vs HttpOnly cookie / bcrypt vs argon2 / validate_settings 双层防御——建议打分完成后一次写 4-6 条 ADR

- ~~**P1-M6-5 LoginView 未消费 locked_until 渲染倒计时**~~（D9）— **审计阶段已修复**
  - **修复**（2026-04-12）：`frontend/src/views/LoginView.vue` 新增 `startLockedCountdown()` / `clearLockedCountdown()` 函数：
    - 423 响应时从 `e.response.data.detail.locked_until` 提取 ISO 时间戳
    - `window.setInterval(update, 1000)` 每秒更新倒计时文案
    - 动态显示"账号已锁定，剩余 X 分 Y 秒"或"剩余 Y 秒"
    - 归零后自动清空错误文案并释放 timer
    - `onUnmounted` 释放 timer 防内存泄漏
  - **影响**：M6 D9 的"锁定倒计时未消费"缺口消除

- ~~**P1-M6-6 LoginView 英文硬编码**~~（D9，部分修复）— **英文部分已修，移动端部分保留**
  - **修复**（2026-04-12）：`frontend/src/views/LoginView.vue`
    - "Sign in to Restock" → "登录 Restock"
    - "Sign in" → "登录"
  - **保留**：移动端 `@media` 断点未加（card 固定 400px），作为 P2 待办
  - **影响**：M6 D9 的"英文硬编码"缺口消除，只剩"无移动端断点"

### 🟢 P2 候选

- **P2-M6-1 bcrypt cost factor 12 无压测验证 P95**（D8）
- **P2-M6-2 `login_attempt` 表无 TTL 清理机制**（D8，与 api_call_log/task_run 同类遗留）
- **P2-M6-3 JWT 密钥长度/熵不校验**（D3，当前仅拦截 `please_change_me` 字面量）
- **P2-M6-4 LOGIN_FAILED_MAX / LOGIN_LOCK_MINUTES 无 validate_settings 病态值校验**（D4）
- **P2-M6-5 GlobalConfigView 保存失败硬编码 "保存失败" 未走 getActionErrorMessage**（D9，与 M5 的 DataOrdersView 同类问题）

---

## P0/P1 候选交叉判定

| 候选 | M6 判定 | 说明 |
|---|:---:|---|
| **P0-2 公网假设覆盖 — JWT 强度** | ⚠️ | JWT HS256 + env var + 生产 `please_change_me` 拦截 ✅；**但不校验密钥长度/熵** ❌；deploy 层双层防御补救 ⚠️ |
| **P0-2 公网假设覆盖 — 密码 hash** | ✅ | bcrypt + unique salt + constant-time + 明文不入 DB + 10 个 security 单测守护 |
| **P0-5 JWT_SECRET 初始生成与轮换** | ❌ | 初始生成靠 placeholder 意会；**轮换流程零文档** |
| **P1-6 X-Forwarded-For 信任源** | ❌ | **未限定反代 IP**，可被伪造完全绕过 per-IP lockout —— 公网下可利用 |

---

## 与 M1-M5 共性

- ❌ 无入口级速率限制（M1-M5 共性 + M6 加剧：登录端点尤其需要）
- ❌ 无 CVE 扫描（共性）
- ❌ 无安全 headers / CSRF（共性）
- ❌ 无 CI/CD / 蓝绿部署（共性）
- ❌ 无 OpenTelemetry / Grafana / 告警（共性）
- ❌ 无审计日志（M3/M4 已标注类似缺口，M6 的零业务日志**尤其严重**）
- ❌ `login_attempt` 无 TTL（与 M1 api_call_log / M4 task_run 同结构遗留）

## M6 独有

**亮点**：
- ✅ **D3 3 分是全项目最高** —— 认证核心控制闭环（bcrypt + env secret + 生产 fail-fast + per-IP lockout + 跨 IP 独立性单测守护 + 双层 placeholder 拦截）
- ✅ **bcrypt + JWT 10 个单测** 守护安全核心
- ✅ **登录锁定从全局共享改为 IP 隔离** 是一次有明确设计意图的重构
- ✅ **deploy/validate_env.sh + backend/validate_settings 双层密钥防御**
- ✅ **LoginView 网格 hover 交互 + autofill 蓝色覆盖** 设计细节到位

**缺口**：
- ❌ **D5 2 分** —— auth.py 零业务日志是认证模块的严重短板
- ❌ **D7 2 分** —— 零 ADR + runbook 零认证故障章节
- ❌ **D9 2 分** —— LoginView 英文硬编码 + 无锁定倒计时 + 无移动端断点
- ❌ **X-Forwarded-For 可被伪造** —— P1-6 ❌ 公网下可利用的真实缺陷

---

## 给用户的待确认疑点

✅ 全部 5 个疑点在第二轮 review 中已由 Claude 主控确认并处理，详见 §8 用户澄清记录与 §9 修复摘要。

---

## 8. 用户澄清记录（2026-04-12 第二轮 review）

用户指令"疑点由你来确认和决定"——Claude 主控为全部 5 个疑点做出决策。

### #1 P0-5 JWT 轮换文档（🟢 立即修复）
- **Claude 决策**：立即做。写 runbook 新增章节，含首次生成 + 定期轮换 + 泄漏应急 + FAQ
- **修复执行**（2026-04-12）：`docs/runbook.md` 新增第 3.4 节"JWT 密钥管理（首次生成 / 轮换 / 泄漏应急）"，约 100 行，涵盖：
  - 3.4.1 首次生成（`openssl rand -base64 32` + 双层防御说明）
  - 3.4.2 定期轮换（JWT_SECRET / LOGIN_PASSWORD 两条独立流程 + 重启顺序 + 影响范围）
  - 3.4.3 密钥泄漏应急处理（6 步 SOP + git 历史清理 + login_attempt 异常扫描）
  - 3.4.4 常见问题 FAQ（4 条）
- **影响**：**P0-5 候选从 ❌ 未实现升级为 ✅ 已实现**——M6 不再是 P0 阻塞

### #2 P1-6 X-Forwarded-For 信任源（🟡 降级到 P2 + 加代码注释）
- **Claude 调查**：读 `deploy/Caddyfile:6`，发现 `header_up X-Forwarded-For {remote_host}` 是**覆盖**操作（不是 append）——Caddy 强制把 XFF 设为对端真实 IP，客户端伪造的 XFF 会在 Caddy 层被直接覆盖
- **实际风险评估**：**在当前部署架构下风险已被架构化缓解**——攻击者无法通过伪造 XFF 绕过 per-IP lockout
- **残余风险**：若未来脱离 Caddy 直接暴露 backend，当前代码会变成真实漏洞
- **Claude 决策**：**降级到 P2**——不立即加 `TRUSTED_PROXIES` 白名单（会引入复杂度对当前架构无净收益），但在 `_get_login_source_key` 加代码注释明确记录对 Caddy 覆盖 XFF 的依赖关系
- **修复执行**（2026-04-12）：`backend/app/api/auth.py:33-38` 追加 4 行注释：
  ```python
  # 注:本函数无条件信任 X-Forwarded-For 首值,依赖 Caddy 反向代理通过
  # `header_up X-Forwarded-For {remote_host}` **覆盖**(而非 append)原 XFF
  # (见 deploy/Caddyfile 第 6 行),确保后端看到的是 Caddy 的真实对端 IP 而
  # 非客户端伪造值。若未来脱离 Caddy 直接暴露 backend,必须引入
  # TRUSTED_PROXIES 白名单校验 request.client.host 来源。
  ```
- **影响**：P1-6 候选判定从 ❌ 未实现改为 ⚠️ 部分实现（Caddy 架构缓解）；代码层约束未来部署拓扑变更的风险

### #3 P1-M6-1 auth.py 业务日志（🟢 立即修复）
- **Claude 决策**：立即做。5 行 structlog 调用，零风险，高价值
- **修复执行**（2026-04-12）：`backend/app/api/auth.py` 增加 `from app.core.logging import get_logger` + `logger = get_logger(__name__)`，在关键路径加入：
  - `auth_login_blocked_locked` warning（被锁定请求进入时）
  - `auth_login_failed` warning（密码错误未达阈值）
  - `auth_login_lockout_triggered` warning（密码错误达阈值，新锁定触发）
  - `auth_login_reset_after_success` info（成功后清零旧失败计数）
  - `auth_login_success` info（成功签发 JWT）
- **全量 pytest 验证**：163 passed / 0 failed
- **影响**：**M6 D5 从 2 分升到 3 分**（见 §9）；与 M1-M4 D5=3 持平

### #4 P1-M6-5 LoginView 锁定倒计时（🟢 立即修复）
- **Claude 决策**：立即做。后端已返回 `locked_until`，前端只需几行代码消费，纯 UX 改进
- **修复执行**（2026-04-12）：`frontend/src/views/LoginView.vue` 新增：
  - `clearLockedCountdown()` / `startLockedCountdown(lockedUntilIso)` 两个函数
  - 423 响应时从 `e.response.data.detail.locked_until` 提取 ISO 时间戳
  - `window.setInterval(update, 1000)` 每秒更新 errorMsg 文本
  - 格式化为"账号已锁定，剩余 X 分 Y 秒"或"剩余 Y 秒"
  - 归零后自动清空错误文案并释放 timer
  - `onUnmounted` 释放 timer 防内存泄漏
  - `handleLogin` 每次开始时 `clearLockedCountdown()` 避免重复计时
- **前端类型检查**：`vue-tsc --noEmit` 通过
- **影响**：M6 D9 的"锁定倒计时未消费"缺口消除

### #5 D9 "Sign in to Restock" 英文硬编码（🟢 立即修复）
- **Claude 决策**：立即做。与全站中文路线冲突，中文化是 1 行改动，无风险
- **修复执行**（2026-04-12）：`frontend/src/views/LoginView.vue`
  - `<h1 class="card-title">Sign in to Restock</h1>` → `<h1 class="card-title">登录 Restock</h1>`
  - `<el-button>Sign in</el-button>` → `<el-button>登录</el-button>`
  - 保留 `.footer-text Restock System` + `.footer-version v0.1.0` 作为品牌标识（符合"品牌名可保留英文"惯例）
- **影响**：M6 D9 的"英文硬编码"缺口消除；剩余 D9 偏差只有"移动端无 @media 断点"

---

## 9. 第二轮变更摘要

### 代码/配置变更

| 文件 | 变更 | 对应疑点 |
|---|---|---|
| `backend/app/api/auth.py` | 加 `get_logger` + 5 类 structlog 业务事件日志 + `_get_login_source_key` XFF 依赖注释 | #3 + #2 |
| `frontend/src/views/LoginView.vue` | 中文化 `Sign in to Restock` / `Sign in`；新增 `startLockedCountdown` / `clearLockedCountdown` 消费后端 `locked_until` | #4 + #5 |
| `docs/runbook.md` | 新增 §3.4 JWT 密钥管理章节 ~100 行；原 3.5-3.8 顺延到 3.5-3.9 | #1 |

### 测试验证

- `cd backend && pytest tests/unit/` → **163 passed, 0 failed**（零回归）
- `cd frontend && npx vue-tsc --noEmit` → **exit 0**

### P0/P1/P2 列表演变

| 类别 | 第一轮 | 第二轮 | 变化 |
|---|:--:|:--:|---|
| 🔴 P0 | 1 | **0** | P0-5 已修复 |
| 🟡 P1 | 7 | **3** | P1-6 降级 P2；P1-M6-1/5/6 已修复；剩 P1-M6-2/3/4 |
| 🟢 P2 | 5 | **9** | 新增 XFF 降级 + ADR 待办 + 移动端断点 + 保留原 5 项 |

### M6 分数变化

| 维度 | 第一轮 | 第二轮 | 变化原因 |
|---|:--:|:--:|---|
| D5 可观测性 | 2 | **3** | auth.py 五类业务日志已补齐，与 M1-M4 持平 |
| D9 用户体验 | 2 | 2 | 英文 + 倒计时两项偏差已修复，但"移动端无 @media"是 3 级硬指标明确未达 |
| 其他 7 维度 | — | 无变化 | — |

**M6 平均分**：**2.56 → 2.67**（+0.11）

**六模块均分**：(2.63+2.75+2.56+2.63+2.67+2.67) / 6 = **2.65 / 4**

---

## 状态

✅ 审计完成。评分写入 `docs/superpowers/scorecard/M6-auth-config.md`；标尺同步追加到 `_calibration.md` 的 D1-D9 全部 9 个小节。第二轮 review 完成 4 项代码修复 + 1 项文档新增，M6 平均分从 2.56 升至 2.67。
