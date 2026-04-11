# 评分标尺一致性记录

> 用途：每完成一个模块的评分后，记录每个维度的具体打分理由和判据匹配，
> 确保后续模块的同一维度评分与本记录一致。
>
> 更新规则：每个模块的 checkpoint 完成且用户确认后，由 Claude 追加该模块的标尺记录。
>
> 关联文档：
> - Spec：`docs/superpowers/specs/2026-04-11-delivery-readiness-scorecard-design.md`
> - Plan：`docs/superpowers/plans/2026-04-11-delivery-readiness-scorecard.md`

---

## D1 功能完整性

### M2 补货引擎
- **得分**：3
- **理由**：满足 Rubric 3 级（6 步流水线全部实现，边界场景已处理：空 SKU 早退、零销量跳过、sale_days 缺失退化为今日采购、无仓库空返、push_blocker 预检），未满足 4 级（无集成测试守护全链路路径，`load_in_transit` 90 天窗口逻辑无专项单测）
- **关键证据**：`backend/app/engine/runner.py:77-86` — 无 SKU 早退；`backend/app/engine/step6_timing.py:84-94` — sale_days 缺失即时采购语义；`backend/tests/unit/test_engine_runner.py:165-186` — mock DB runner 无 SKU 路径测试

### M1 赛狐集成
- **得分**：3
- **理由**：满足 Rubric 3 级（主链路端到端完整、边界场景已处理、永久/瞬态错误分类、在途老化机制），未满足 4 级（无集成/契约测试守护核心路径，如分页终止、retry 次数、token 刷新 single-flight）
- **关键证据**：`backend/app/saihu/client.py:75-97` — retry + auth_expired 双重重试逻辑；`backend/app/sync/order_detail.py:34-45` — 永久错误分类测试守护

### M3 建议单与推送
- **得分**：3
- **理由**：满足 Rubric 3 级（主链路 list/detail/patch/push/archive 全实现，边界场景覆盖：archived 拒编辑、push_blocker 双层校验、H4 一致性、H3 urgent 重算），未满足 4 级（list/detail/archive 端点零单测；`error` 状态孤立无写入路径；push 端点未拦截 archived 建议单）
- **关键证据**：`backend/app/api/suggestion.py:172-173` — archived 拒绝编辑；`backend/app/pushback/purchase.py:150-182` — `_refresh_suggestion_counts` 三态升级；全库无 `"'error'"` 写入路径

### M4 任务队列
- **得分**：3
- **理由**：满足 Rubric 3 级（入队-抢占-执行-完结全链路闭合，边界场景处理：dedupe 并发入队 + UniqueViolation 重试 + SKIPPED 留痕、worker crash → reaper 回收、未注册 job_name → _mark_failed、心跳 lease 不变式双层校验、PROCESS_ENABLE_* 三角色分离 + 角色感知 /readyz），未满足 4 级（queue/worker/reaper 核心模块零单测，无集成测试守护回归；无异常恢复路径测试）；与 M1/M2/M3 持平
- **关键证据**：`backend/app/tasks/worker.py:93-111` — `FOR UPDATE SKIP LOCKED` 原子抢占；`backend/app/tasks/queue.py:61-109` — UniqueViolation 重试 + SKIPPED 留痕；`backend/app/tasks/reaper.py:59-77` — 僵尸回收；`backend/app/config.py:79-80` + `backend/app/tasks/worker.py:44-53` — 双层不变式校验；`backend/app/main.py:79-98` — lifespan 角色感知；无 `test_*queue*.py` / `test_*worker*.py` / `test_*reaper*.py` 文件

### M5 前端数据页
- **得分**：3
- **理由**：满足 Rubric 3 级（所有主链路端到端闭合：登录/登出 + Workspace Dashboard + 7 个数据页 + Suggestion list/detail/push + 跨页选择 + TaskProgress 实时轮询 + 401 自动跳转；边界场景覆盖：404 静默回空态、423 登录锁定特殊分支、筛选变化自动清除跨页 selection 防脏选、`selectedIds` 跨页维护 + `handleSelectAll` 跨分页全选、`nextTick` + `suppressSelectionSync` 时序防御），未满足 4 级（views/ 零组件测试，仅 `TaskProgress.test.ts` 2 个；跨页选择+筛选+排序四状态交互矩阵无测试守护；无 e2e）；与 M1/M2/M3/M4 持平
- **关键证据**：`frontend/src/router/index.ts:11-181` — 完整路由 + 守卫 + redirect 遗留路径；`frontend/src/views/SuggestionListView.vue:260-305` — 跨页选择四函数协同；`frontend/src/views/SuggestionListView.vue:166-178` — 404 特殊静默；`frontend/src/api/client.ts:23-30` — 401 自动 clearToken+redirect；`frontend/src/stores/task.ts:17-42` — 2s 轮询 + 终态退出；`frontend/src/api/data.ts:60,98,130,198,232` — 6 接口 `page_size: 5000` 一次拉全量

## D2 代码质量

### M2 补货引擎
- **得分**：3
- **理由**：满足 Rubric 3 级（57 个引擎单测全 pass，所有计算 step 均暴露纯函数独立可测，命名清晰，step 文件均有 FR 编号 docstring，`CountryAllocationResult` dataclass 结构化返回无魔术字典），未满足 4 级（无集成测试守护全链路 DB 路径，`load_in_transit` 异步函数无 mock 单测，未确认 mypy 0 warning）
- **关键证据**：`backend/app/engine/step1_velocity.py:29-34` — `compute_velocity` 纯函数带公式注释；`backend/app/engine/step5_warehouse_split.py:27-32` — `CountryAllocationResult` dataclass；57 个单测全 pass

### M1 赛狐集成
- **得分**：2
- **理由**：满足 Rubric 2 级（140 个单测全 pass，签名算法有官方 fixture 比对，错误分类 6 个测试守护），未满足 3 级（`SaihuClient`/`TokenManager` 核心方法无单测，整个 client.py/token.py 无 httpx mock 测试，覆盖率不足 70%）
- **关键证据**：`backend/tests/unit/test_sign.py:17-28` — 官方 fixture 签名测试；`backend/tests/unit/test_sync_order_detail_classification.py` — 6 个错误分类测试；`backend/app/saihu/client.py` — 无对应测试文件

### M3 建议单与推送
- **得分**：2
- **理由**：满足 Rubric 2 级（PATCH 7 测试 + pushback 7 测试，核心校验分支全覆盖），未满足 3 级（list/detail/archive 端点零单测，整体覆盖率约 60% 低于 70% 门槛；输出 schema JSONB 字段宽泛 `dict[str, Any]`）
- **关键证据**：`backend/tests/unit/test_suggestion_patch.py:66-131` — 7 个 PATCH 单测；`backend/tests/unit/test_pushback_purchase.py:116-260` — 7 个 pushback 单测；`backend/app/schemas/suggestion.py:37` — `country_breakdown: dict[str, Any]` 输出端宽泛

### M4 任务队列
- **得分**：2
- **理由**：满足 Rubric 2 级（状态机逻辑清晰 queue/worker/reaper 职责分离，命名规范 `_claim_one`/`_reap_once`/`_make_progress_setter`，心跳不变式双层防御），未满足 3 级（queue.py/worker.py/reaper.py/scheduler._enqueue_safely/JOB_REGISTRY 五个核心模块零单测；5 处 async session 重复代码未抽取；与 M1=2/M3=2 同类型：核心文件零单测）
- **关键证据**：无 `test_*queue*.py` / `test_*worker*.py` / `test_*reaper*.py`；`backend/app/tasks/worker.py:38-72` / `backend/app/tasks/reaper.py:22-45` — start/stop/running 模式重复；`backend/app/config.py:79-80` + `backend/app/tasks/worker.py:44-53` — 不变式双层校验

### M5 前端数据页
- **得分**：3
- **理由**：满足 Rubric 3 级（`vue-tsc --noEmit` **0 错误**，`eslint --max-warnings 0` **exit 0 零输出**，vitest **33 pass / 8 files** 全绿，TS 严格类型 + defineProps 范型齐全，共享 utils 复用度高 `format/warehouse/countries/status/tableSort/apiError` Grep 39 处跨 18 文件，10 个 views 统一使用 `PageSectionCard`，命名清晰），未满足 4 级（views/ 零组件测试仅 `TaskProgress.test.ts` 2 个，`vitest.config.ts:20` `thresholds.statements: 2` 基线极低；**`ZipcodeRuleView.vue` 1276 行 + `SuggestionDetailView.vue` 729 行**巨型文件未拆子组件；`DataOrdersView.vue:205` 等多处 catch 硬编码"加载失败"未走 `getActionErrorMessage`，utils 复用广度高但深度未 100%）；**与 M2=3 持平，高于 M1/M3/M4 一级**——理由：M5 有 lint + type-check 双 quality gate exit 0，后端模块共性无 mypy 校验
- **关键证据**：`frontend/package.json:10,12` — lint + type-check 脚本；vue-tsc 实测 exit 0；eslint 实测 exit 0 零输出；vitest 实测 33 pass；`frontend/vitest.config.ts:19-21` — threshold 2% 极低；`wc -l src/views/ZipcodeRuleView.vue` = 1276；`frontend/src/views/data/DataOrdersView.vue:204-208` — 硬编码错误字符串反面证据；Grep `from '@/utils/{format,warehouse,...}'` → 39 处 / 18 文件；`PageSectionCard` 使用覆盖 10 个 views

## D3 安全性

### M2 补货引擎
- **得分**：2（低权重，重点评并发安全）
- **理由**：满足 Rubric 2 级（advisory lock 参数化 text 无注入风险，JSONB 快照代码层仅在 INSERT 写入，API PATCH 不暴露快照字段），未满足 3 级（快照字段无 DB 级不可变约束，无 CVE 扫描）
- **关键证据**：`backend/app/engine/runner.py:58-60` — advisory lock 参数化；`backend/app/models/suggestion.py:94-95` — 快照列 nullable 无 immutability 约束；`backend/app/api/suggestion.py:215` — PATCH 层不暴露快照字段（代码层保护）

### M1 赛狐集成
- **得分**：2
- **理由**：满足 Rubric 2 级（SAIHU_ 密钥走环境变量，pydantic-settings 全量校验，启动时生产环境配置强制校验，日志无明文密钥），未满足 3 级（代码层无代理/出口 IP 接入点是核心缺口；无 CVE 扫描；`access_token` 作为 URL query param 传输）
- **关键证据**：`backend/app/config.py:36-38,86-90` — env var 读取 + 生产校验；Grep 全库无 proxy/HTTP_PROXY 匹配（P0-1 ❌ 未实现）

### M3 建议单与推送
- **得分**：2
- **理由**：满足 Rubric 2 级（所有 6 个端点 JWT 认证，Pydantic 全量校验，country_breakdown 值非负校验），未满足 3 级（无入口级速率限制，push 端点未拦截 archived 建议单，无推送操作 audit log 含 operator，无 CVE 扫描）；公网视角下 push-on-archived 是 M3 独有缺口
- **关键证据**：`backend/app/api/suggestion.py:268,313` — push/archive 端点有 JWT；`suggestion.py:263-306` — push 无 sug.status 前置校验；全库无入口级限流

### M4 任务队列
- **得分**：2（低权重）
- **理由**：满足 Rubric 2 级（4 个 task API 端点全 JWT 鉴权，VALID_JOB_NAMES 白名单防任意入队，Raw SQL 全参数化无注入风险，payload 是 JSONB 无 pickle 反序列化风险，error_msg[:5000] 截断防日志爆炸，scheduler 配置经 JWT 鉴权端点修改），未满足 3 级（共性问题：无入口级速率限制 + 无 CVE 扫描 + 无安全 headers；M4 独有小缺口：cancel 端点无越权区分，但单用户场景可忽略）
- **关键证据**：`backend/app/api/task.py:18-30,94-95` — VALID_JOB_NAMES 白名单；`backend/app/tasks/worker.py:93,166` + `backend/app/tasks/reaper.py:62` — text() + bound params；`backend/app/tasks/worker.py:216` — error_msg 截断

### M5 前端数据页
- **得分**：2
- **理由**：满足 Rubric 2 级（**0 处 `v-html` / `innerHTML` / `dangerouslySet`** 零 XSS 注入面；所有请求走 axios + JWT Bearer 拦截器 + 401 自动 clearToken+redirect 幂等；`baseURL: '/'` 同源策略无 CORS 暴露；**0 处 `console.log/error/warn`** 无敏感字段泄漏到浏览器日志），未满足 3 级（**token 存 localStorage** 而非 HttpOnly cookie 是 M5 独有公网 XSS 风险；`nginx.conf:1-31` **缺全部安全 headers**——无 CSP / X-Frame-Options / X-Content-Type-Options / Referrer-Policy / Permissions-Policy；无 npm audit / CVE 扫描 / subresource integrity）；与 M1/M2/M3/M4 持平 2 分
- **关键证据**：Grep `v-html|innerHTML|dangerouslySet in src/` → **0 matches**；`frontend/src/stores/auth.ts:8,14,19` — localStorage token 存储反面证据；`frontend/src/stores/sidebar.ts:8,10,15,18` — localStorage 持久化；`frontend/src/api/client.ts:11-18,23-30` — Bearer 注入 + 401 处理；`frontend/nginx.conf:1-31` — 仅 gzip/cache/SPA fallback 无安全 headers；Grep `console\.log|console\.error|console\.warn in src/` → **0 matches**；Grep `audit` in package.json scripts → 0

## D4 可部署性

### M3 建议单与推送
- **得分**：3（第二轮 review 重新评估，第一轮为 N/A）
- **理由**：满足 Rubric 3 级（docker-compose + .env.example 文档化 PUSH_AUTO_RETRY_TIMES + 迁移已就绪 + 一键脚本 + 启动校验 + 资源限制），未满足 4 级（无 CI/CD + IaC + 蓝绿 + 多环境）；M3 独有缺口：PUSH_MAX_ITEMS_PER_BATCH 是 dead config（P2-5），push_auto_retry_times 缺 validate_settings 校验（P2-6）
- **关键证据**：`backend/.env.example:55-56` — push 配置文档化；`backend/app/config.py:57-58` — 字段定义；全库 grep `PUSH_MAX_ITEMS_PER_BATCH` 仅在 config.py 自身命中

### M2 补货引擎
- **得分**：3（第二轮 review 由 M3 触发的 retroactive 更新，第一轮为 N/A）
- **理由**：满足 Rubric 3 级（docker-compose + 引擎配置文档化 + 迁移就绪 + 一键脚本 + 启动校验 + 资源限制 + PROCESS_ENABLE_* 角色分离），未满足 4 级（无 CI/CD + IaC + 蓝绿）；M2 独有缺口：default_target_days/buffer_days/lead_time_days 缺 validate_settings 校验
- **关键证据**：`backend/app/config.py:60-64` — 引擎默认值字段；`backend/alembic/versions/20260408_1500_initial.py` — suggestion/global_config 表迁移；`backend/app/config.py:49-50` — PROCESS_ENABLE_WORKER/SCHEDULER 角色分离

### M1 赛狐集成
- **得分**：3
- **理由**：满足 Rubric 3 级（docker-compose 一键启动，.env.example，一键部署脚本含备份/迁移/回滚/smoke，启动时配置校验，资源限制），未满足 4 级（无 CI/CD，无 IaC，无蓝绿部署，无多环境）；但 SAIHU_HTTP_PROXY 代理配置未预留是上云缺口
- **关键证据**：`deploy/scripts/validate_env.sh:17-32` — 部署前强校验 SAIHU_ 凭证；`deploy/docker-compose.yml:51-55` — 资源限制；`docs/deployment.md:116-130` — 一键部署脚本流程

### M4 任务队列
- **得分**：3
- **理由**：满足 Rubric 3 级（task_run 建表迁移就绪含 4 个索引 + 2 个 CheckConstraint，PROCESS_ENABLE_* 三角色分离完整 config→lifespan→readyz→docker-compose 全链路贯通，docker-compose 三服务各自资源限制 + healthcheck，角色感知 /readyz 防禁用角色误判，启动时不变式校验 heartbeat×2<lease 双层，.env.example 完整文档化），未满足 4 级（共性问题：无 CI/CD + IaC + 蓝绿部署 + 多环境）；M4 独有缺口：WORKER_POLL_INTERVAL_SECONDS / REAPER_INTERVAL_SECONDS 无 validate_settings 校验；worker + reaper 共容器 + backend 关 reaper 的拓扑在 worker crash 时无僵尸回收（P1-M4-3）
- **关键证据**：`backend/alembic/versions/20260408_1500_initial.py:540-605` — task_run 建表 + 4 个索引；`backend/app/main.py:79-98,160-172` — lifespan 角色感知 + readyz 角色感知；`deploy/docker-compose.yml:60-119` — backend/worker/scheduler 三服务；`backend/app/config.py:79-80` — 心跳不变式 validate；`backend/.env.example:40-50` — 文档化

### M5 前端数据页（按新口径实地评分）
- **得分**：3
- **理由**：满足 Rubric 3 级（`frontend/Dockerfile` 标准两阶段构建 node:20-alpine builder → nginx:1.27-alpine runtime + HEALTHCHECK wget；`vite.config.ts:36-37` 生产 **sourcemap=false** + `chunkSizeWarningLimit: 500`；`vite.config.ts:40-55` `manualChunks` 精准分包 element-plus / charts / framework 三桶；`nginx.conf` 含 gzip + `/assets` `expires 1y immutable` 强缓存 + SPA fallback + deny 隐藏文件；`deploy/docker-compose.yml:124-137` frontend 服务 + `memory: 256m` 资源限制 + 依赖 backend healthy；Caddy 反代统一入口；`.env.example` 存在文档化 `VITE_API_PROXY_TARGET`；build 耗时 **11.14 s**），未满足 4 级（共性：无 CI/CD + 蓝绿 + IaC；M5 独有缺口：`.env.example` **仅 1 行**未覆盖生产前端环境变量；vite build 两处 chunk-size warning (element-plus 906KB / charts 557KB) 未完全处理；element-plus 未按需引入）；与 M1/M2/M3/M4 持平 3 分
- **关键证据**：`frontend/Dockerfile:1-23` — 两阶段 + HEALTHCHECK；`frontend/vite.config.ts:36-55` — sourcemap=false + manualChunks；`frontend/nginx.conf:8-25` — gzip + immutable cache + SPA fallback；`deploy/docker-compose.yml:124-137` — frontend 服务 + 资源限制；`frontend/.env.example:1` — 1 行配置反面证据；vite build 实测产物：首屏 gzip ~358 KB、charts 懒加载 188.66 KB gz、view chunks 2-16 KB

## D5 可观测性

### M2 补货引擎
- **得分**：3
- **理由**：满足 Rubric 3 级（每步调用 `ctx.progress(current_step=...)` 更新 task_run 进度，3 个 JSONB 快照完整持久化供追溯，step6 缺 sale_days 有结构化 warning 日志），未满足 4 级（无 OpenTelemetry，无 /metrics，步骤耗时未记录）
- **关键证据**：`backend/app/engine/runner.py:88-91` — `ctx.progress(total_steps=7)`；`backend/app/engine/runner.py:182-183` — 快照写入；`backend/app/engine/step6_timing.py:85-88` — 结构化警告日志

### M1 赛狐集成
- **得分**：3
- **理由**：满足 Rubric 3 级（structlog JSON 日志，request_id 自动绑定，api_call_log 完整记录含 error_type/retry_count，限流命中有 rate_limit 错误分类，/api/monitor/saihu-calls 聚合端点），未满足 4 级（无 OpenTelemetry，无 Prometheus /metrics，无 Grafana，无 SLO/SLI）
- **关键证据**：`backend/app/models/api_call_log.py:38-40` — error_type + retry_count 字段；`backend/app/saihu/client.py:197-210` — rate_limit 命中写入 api_call_log；`backend/app/api/monitor.py:42-50` — EndpointStats 聚合模型

### M3 建议单与推送
- **得分**：3
- **理由**：满足 Rubric 3 级（structlog + `ctx.progress()` 3 次步骤追踪，`logger.exception("push_saihu_failed", suggestion_id=..., error=...)` 结构化失败日志，`push_attempt_count`/`push_error`/`pushed_at`/`saihu_po_number` 字段级追溯），未满足 4 级（无 /metrics 推送成功率指标，无 OpenTelemetry，无 operator 关联的 audit log）
- **关键证据**：`backend/app/pushback/purchase.py:42,100` — progress 和失败日志；`backend/app/models/suggestion.py:103-105` — push 字段追溯

### M4 任务队列
- **得分**：3
- **理由**：满足 Rubric 3 级（task_run 表即全量事件时间线涵盖 16 个字段可回溯任务生命周期，结构化日志全覆盖 task_enqueued/task_dedupe_hit/worker_started/reaper_collected_zombies/scheduler_enqueue_error 等，SKIPPED 状态留痕直接可用 SELECT count 做业务事件指标，`ctx.progress()` + `_make_progress_setter` 实时写入进度字段支持前端 2 秒轮询，worker_id 稳定可读 hostname:pid:uuid 便于多实例定位，/readyz 联合 DB + worker.running + reaper.running + scheduler.running 四项检查），未满足 4 级（共性问题：无 OpenTelemetry + /metrics + Grafana + SLO/SLI）；M4 独有缺口：无 duration 字段 + 无 /api/monitor/tasks 聚合端点（对比 M1 /api/monitor/saihu-calls）；无 heartbeat 延迟主动告警
- **关键证据**：`backend/app/models/task_run.py:73-106` — 全字段定义；`backend/app/tasks/queue.py:59,103-108` — task_enqueued / task_dedupe_hit 日志；`backend/app/tasks/reaper.py:77` — reaper_collected_zombies 带 task_ids；`backend/app/tasks/worker.py:180-200` — _make_progress_setter；`backend/app/main.py:175-193` — /readyz 联合检查

### M5 前端数据页
- **得分**：2
- **理由**：满足 Rubric 2 级（`ElMessage.error/warning` **39 处跨 18 文件**请求失败用户反馈到位；`ElMessageBox.confirm` 高危操作二次确认；401 自动 clearToken+redirect；后端 `request_id` 回传可通过 axios response 透传——依赖 M1 证据；无 `console.log` 污染），未满足 3 级（**无 Sentry / Rollbar / 自研前端错误上报**，Grep `Sentry|rollbar|otel in frontend/` **0 matches**；无 Web Vitals / performance API 采集基准；`WorkspaceView.vue:199-205` 关键 dashboard 加载失败**静默吞异常**仅 `data.value = null` 无 ElMessage 提示；`stores/task.ts:34-38` TaskProgress 轮询失败吞异常无用户反馈；`DataOrdersView.vue:205` 等多处 catch 硬编码 "加载失败" 未走 `getActionErrorMessage` 五档分类——`getActionErrorMessage` 仅 15 处使用覆盖面不足）；**M5 为 2 分比后端模块 M1-M4 = 3 低 1 级**——理由：后端 structlog JSON 日志 + request_id 绑定 + api_call_log 结构化事件线满足 Rubric 3 "request 追踪"，前端无等价基础设施
- **关键证据**：Grep `ElMessage\.error|ElMessage\.warning in src/` → 39 处 / 18 文件；Grep `Sentry|rollbar|otel in frontend/` → **0 matches**；`frontend/src/views/WorkspaceView.vue:199-205` — 静默吞异常反面证据；`frontend/src/stores/task.ts:34-38` — 轮询失败无反馈反面证据；`frontend/src/views/data/DataOrdersView.vue:204-208` — 硬编码 "加载失败"；Grep `getActionErrorMessage in src/` → 15 处 / 6 文件（广度不足）

## D6 可靠性

### M2 补货引擎
- **得分**：3
- **理由**：满足 Rubric 3 级（advisory lock 防并发，`_persist_suggestion` 事务原子归档旧建议再 INSERT，load_in_transit 90 天窗口防无限累积，worker `_mark_failed` 映射引擎异常为 failed 状态，push_blocker 预检），未满足 4 级（无死信队列，无熔断器，快照无 DB 约束保护，无 chaos test）
- **关键证据**：`backend/app/engine/runner.py:58-60` — advisory lock；`backend/app/engine/runner.py:241-258` — 原子归档+INSERT；`backend/app/tasks/worker.py:149-151` — 异常→failed 状态；`backend/app/engine/step2_sale_days.py:67` — 90 天截止

### M1 赛狐集成
- **得分**：3
- **理由**：满足 Rubric 3 级（指数退避 wait_exponential，错误分类明确 permanent/transient，token single-flight，aiolimiter 防超速，UPSERT 幂等，超时配置），未满足 4 级（无熔断器，无死信队列，无 chaos test，无故障注入）
- **关键证据**：`backend/app/saihu/client.py:77-80` — tenacity 指数退避；`backend/app/saihu/token.py:73-96` — single-flight；`backend/app/sync/order_detail.py:34-45` — permanent/transient 分类

### M3 建议单与推送
- **得分**：3
- **理由**：满足 Rubric 3 级（dedupe_key 防并发重入，tenacity 指数退避 + 永久/瞬态分类，可配置重试次数，两阶段 commit，push_blocker 双层校验），未满足 4 级（JSONB 无 DB 级 immutable 约束，push-on-archived 未拦截，`error` 状态孤立，无熔断器/死信队列/chaos test）
- **关键证据**：`backend/app/api/suggestion.py:303` — dedupe_key；`backend/app/pushback/purchase.py:84-97` — tenacity 永久/瞬态分类；`purchase.py:111-138` — 两阶段 commit

### M4 任务队列
- **得分**：3
- **理由**：满足 Rubric 3 级（FOR UPDATE SKIP LOCKED 单语句原子抢占无 TOCTOU 窗口，partial unique index `uq_task_run_active_dedupe` DB 级保证并发入队去重 + 应用层捕获 UniqueViolation 重试 + SKIPPED 留痕，心跳续租 30s + 2min 租约 + 60s 僵尸回收 + 不变式双层校验 `heartbeat×2<lease`，worker crash 不丢任务（停 running 直到 lease 过期被 reaper 回收），异常→failed 统一映射 + error_msg[:5000] 截断，worker/reaper loop 守护 catch Exception 不崩溃，APScheduler coalesce + misfire_grace 防重复触发 + max_instances=1），未满足 4 级（共性问题：无熔断器 + 死信队列 + chaos test）；M4 独有缺口：started_at(DB now) 与 finished_at(Python now_beijing) 时钟源不一致（P1-M4-5）；heartbeat 失败吞异常无告警 + running 任务无法 cancel（P1-M4-4）；失败任务**不自动重入队**与 M1/M2/M3 一致为明确设计
- **关键证据**：`backend/app/tasks/worker.py:93-111` — SKIP LOCKED 原子抢占；`backend/app/models/task_run.py:49-54` — partial unique；`backend/app/tasks/queue.py:61-109` — UniqueViolation 处理；`backend/app/tasks/reaper.py:59-77` — 僵尸回收；`backend/app/config.py:79-80` — 不变式；`backend/app/tasks/scheduler.py:36-40` — APScheduler 配置

### M5 前端数据页
- **得分**：3
- **理由**：满足 Rubric 3 级（`getActionErrorMessage` 五档错误分类 network-down / 500 / 业务 message / detail array / fallback；401 幂等处理检查 pathname 避免自旋；筛选/sort 变化自动 `nextTick(() => clearSelection())` **清除跨页脏选**；404 特殊静默回空态不触发 error；423 登录锁定专门分支提示；大量 `el-empty` + `v-loading` + `el-alert` 覆盖 13 个 view 共 30 处；`TaskProgress` watch taskId + onBeforeUnmount 清理轮询防内存泄漏；UPSERT 由后端保障幂等），未满足 4 级（TaskProgress 轮询断网即 stop 无指数退避重试——`stores/task.ts:34-38` 反面证据；无 axios-retry；无离线 cache / PWA；无熔断器；无 chaos test）；与 M1/M2/M3/M4 持平 3 分
- **关键证据**：`frontend/src/utils/apiError.ts:9-36` — 五档处理；`frontend/src/api/client.ts:27` — 幂等 401 检查 pathname；`frontend/src/views/SuggestionListView.vue:244-248,310-313` — 筛选清选；`frontend/src/views/SuggestionListView.vue:166-178` — 404 静默；`frontend/src/views/LoginView.vue:87-91` — 423 特殊提示；Grep `el-empty|el-skeleton|v-loading|el-alert in views/` → 30 处 / 13 文件；`frontend/src/components/TaskProgress.vue:70-83` — 生命周期防内存泄漏；`frontend/src/stores/task.ts:34-38` — 断网即停反面证据

## D7 可维护性

### M2 补货引擎
- **得分**：3
- **理由**：满足 Rubric 3 级（6 步流水线公式完整文档化于架构蓝图，step 文件带 FR 编号 docstring，非显然逻辑有注释，advisory lock 设计意图有注释，模块边界清晰），未满足 4 级（无 ADR，无自动化文档生成）
- **关键证据**：`docs/Project_Architecture_Blueprint.md:100-113` — 6 步流水线表格；`backend/app/engine/step4_total.py:73-75` — invariant 注释；`backend/app/engine/runner.py:44-47` — advisory lock 意图注释

### M1 赛狐集成
- **得分**：3
- **理由**：满足 Rubric 3 级（client/endpoints/sync 分层清晰，模块级 docstring 完整，非显然逻辑有注释，saihu_api 完整文档目录，AGENTS.md/deployment.md/runbook.md 存在），未满足 4 级（无 ADR，无自动化文档生成，无 onboarding 时间量化）
- **关键证据**：`backend/app/saihu/client.py:1-9` — 特性列表 docstring；`backend/app/sync/order_detail.py:34-44` — _is_permanent_saihu_error 详尽注释；`docs/saihu_api/` — 完整 API 文档目录

### M3 建议单与推送
- **得分**：3
- **理由**：满足 Rubric 3 级（purchase.py 文件头 FR 编号引用，关键逻辑有注释，架构蓝图完整文档化推送数据流和不可变规则，模块边界清晰），未满足 4 级（无状态机图，push-on-archived 无 ADR 说明设计意图，无自动化文档生成）
- **关键证据**：`backend/app/pushback/purchase.py:1-8` — FR 编号策略说明；`backend/app/api/suggestion.py:166,199,331-337` — 关键注释；`docs/Project_Architecture_Blueprint.md:422-453,723` — 推送流程和不可变规则文档

### M4 任务队列
- **得分**：3
- **理由**：满足 Rubric 3 级（**首个明确拥有 ADR 的模块** ADR-2 自研 TaskRun 替代 Celery 含决策/驱动/代价/适用范围，架构蓝图完整文档化 task_run 表结构 + 4 个索引 DDL + 状态机 + Scheduler/Worker/Reaper 运行时图，runbook 3.2 Worker 异常 + 3.3 Scheduler 异常两节含症状/排查 SQL/重启命令，代码注释覆盖 FR 编号 + 罕见竞态说明 + 不变式理由 + 设计意图明注，模块边界清晰 queue/worker/reaper/scheduler/jobs 目录与职责一一对应），未满足 4 级（共性问题：无自动化文档生成 + 架构图自动同步 + onboarding 时间量化；无状态机图 + 无"如何写新 job" how-to）；**横向比较 M4 的 D7 在基础设施模块里是最好的**（首个 ADR + runbook 覆盖度最高），因共性差距仍保持 3 分
- **关键证据**：`docs/Project_Architecture_Blueprint.md:628-636` — ADR-2 TaskRun 决策；`docs/Project_Architecture_Blueprint.md:148-206,500-522` — 表结构 + 运行时图 + 索引解释；`docs/runbook.md:117-188` — 3.2 Worker 异常 + 3.3 Scheduler 异常；`backend/app/tasks/reaper.py:1-5` — "不自动重新入队"设计意图；`backend/app/tasks/worker.py:44-53` — 不变式理由注释

### M5 前端数据页
- **得分**：2
- **理由**：满足 Rubric 2 级（`AGENTS.md` 第 6.4 节前端约定在代码中实际落地：一次拉全量 5000 + PageSectionCard + 32px 筛选高度全部可核对；`element-overrides.scss:1-13` 显式文档化 shadcn 对齐规范作为注释；目录边界清晰 `views/components/api/stores/utils/styles/config/router`；组件命名一致；`navigation.ts` 结构化导航定义；`tokens.scss` 集中设计 token），未满足 3 级（**`frontend/README.md` 仅 32 行**极简未文档化数据加载模式/组件清单/如何写新数据页；**无 ADR**——M4 已有 ADR-2 前例但前端零 ADR，例如"为什么用 localStorage 存 token"/"为什么不按需引入 element-plus"/"为什么一次拉 5000 条"均无决策记录；**无前端 runbook 章节**——`docs/runbook.md` 仅后端；`ZipcodeRuleView.vue` 1276 行 + `SuggestionDetailView.vue` 729 行违反"模块边界清晰"；`router/index.ts:130-149` 10+ legacy redirect 活化石无文档说明）；**M5 为 2 分低于 M1-M4 = 3 一级**——理由：后端模块普遍有 `Project_Architecture_Blueprint.md` 深度文档 + runbook 章节 + M4 有 ADR-2，而前端 README 32 行 + 零 ADR + 零 runbook 章节未达 Rubric 3 "ADR + runbook + 注释覆盖"门槛
- **关键证据**：`frontend/README.md:1-32` — 全部 32 行仅命令清单；Grep frontend ADR → 无；`docs/runbook.md` 无前端章节；`frontend/src/styles/element-overrides.scss:1-13` — shadcn 对齐注释文档化（唯一亮点）；`wc -l src/views/ZipcodeRuleView.vue` = 1276；`frontend/src/router/index.ts:130-149` — 10+ legacy redirect 未文档化

## D8 性能与容量

### M2 补货引擎
- **得分**：2
- **理由**：满足 Rubric 2 级（无 N+1：`load_all_sku_country_orders` 批量加载，step1/2/4 各自单次查询，有防 N+1 注释），未满足 3 级（无 SLO，无引擎超时，无容量评估文档，无慢查询日志）
- **关键证据**：`backend/app/engine/step5_warehouse_split.py:79` — "避免 NxM 次 N+1" 注释；`backend/app/engine/runner.py:108-109` — 批量加载；引擎代码中无 `asyncio.wait_for` 超时设置（P1 缺口）

### M1 赛狐集成
- **得分**：2
- **理由**：满足 Rubric 2 级（无明显 N+1，分页迭代覆盖所有接口，aiolimiter 充分利用 3 QPS 上限，api_call_log 有复合索引，MAX_PER_RUN=500 防暴走），未满足 3 级（无 SLO 定义，无慢查询日志，无容量评估，api_call_log 无清理机制）
- **关键证据**：`backend/app/saihu/rate_limit.py:18-20` — 3 QPS override；`backend/app/sync/order_detail.py:31,101` — CONCURRENCY=3 匹配 limiter；`backend/app/models/api_call_log.py:20-26` — 双索引；api_call_log 无 TTL/清理任务（P1 问题）

### M3 建议单与推送
- **得分**：2
- **理由**：满足 Rubric 2 级（_build_detail 批量加载防 N+1，suggestion/suggestion_item 有关键索引覆盖主查询），未满足 3 级（无 SLO，无推送超时配置，`_refresh_suggestion_counts` Python 汇总非 SQL GROUP BY，无容量评估文档）
- **关键证据**：`backend/app/api/suggestion.py:331-337,351-366` — N+1 防护注释和批量查询；`backend/app/models/suggestion.py:33-34,68-74` — 关键索引；`backend/app/pushback/purchase.py:84-97` — tenacity 无 timeout 参数

### M4 任务队列
- **得分**：2
- **理由**：满足 Rubric 2 级（4 个部分索引精准覆盖关键查询：`uq_task_run_active_dedupe` partial / `ix_task_run_pending_priority` partial / `ix_task_run_lease` partial / `ix_task_run_job_created`，无 N+1：worker 抢占单 SQL + reaper 单批量 UPDATE + list API 单查询 + count subquery，worker 2s 轮询命中 partial 索引 pending 为空时是空 UPDATE，heartbeat loop 30s 独立 session 避免长连接，资源限制明确 512m×3），未满足 3 级（共性问题：无 SLO + 慢查询日志 + 容量评估文档；task_run 表无 TTL/清理机制与 M1 api_call_log 同构问题 P1-M4-1；Reaper 60s 粒度意味 worker 死亡后最坏 180s 才被标记 failed 未记录 SLO）
- **关键证据**：`backend/app/models/task_run.py:49-71` — 4 个索引含 3 个 partial；`backend/app/tasks/worker.py:93-123` — 单 SQL 抢占；`backend/app/tasks/reaper.py:59-77` — 批量 UPDATE；全库 grep 无 `DELETE FROM task_run` / prune 任务

### M5 前端数据页（全项目 D8 最高分）
- **得分**：3
- **理由**：满足 Rubric 3 级（**vendor 精准分包三桶** `manualChunks` element-plus / charts / framework；所有 view 自动 route code-split 每文件 2-16 KB；charts 懒加载仅 3 个图表页拉取；vite build 实测**首屏 gzip ~358 KB**（index 3.66 + framework 46.27 + element-plus 293.61 + client 15.06）远优于"首屏 < 3s"指标；**charts 懒加载 188.66 KB gz**；`sourcemap: false` 生产不暴露源码；nginx gzip + `/assets` `expires 1y immutable` + SPA fallback；`memory: 256m` 资源限制；table 5000 条走 computed `slice()` 本地分页避免全量渲染；构建 11.14 s），未满足 4 级（**element-plus 906 KB / 293 KB gz** 全量引入未按需 `unplugin-element-plus` 是最大 P1 优化空间；vite build 两处 chunk-size warning 未显式处置；无 Lighthouse / Web Vitals CI 基准；无 CDN；无图片 `loading=lazy`；无 Service Worker；一次拉 5000 条是内存上界但单用户可接受）；**M5 为 3 分高于 M1/M2/M3/M4 = 2 一级**——理由：vendor 分包 + 资源限制 + 懒加载 + sourcemap off + 首屏 358 KB gz 全链路实测通过，符合 Rubric 3 "vendor 分包 + 资源限制 + 容量评估"；后端模块因无 SLO/慢查询日志停留在 2
- **关键证据**：`frontend/vite.config.ts:36-55` — manualChunks + sourcemap false；vite build 实测产物：element-plus 906.32/293.61 KB gz + charts 557.23/188.66 KB gz + framework 123.24/46.27 KB gz + client 37.63/15.06 KB gz + index 10.27/3.66 KB gz；`frontend/nginx.conf:8-20` — gzip + immutable cache；`deploy/docker-compose.yml:134-137` — memory: 256m；`frontend/src/views/SuggestionListView.vue:239-242` — computed `slice` 分页避免渲染 5000 条；`frontend/src/api/data.ts:60,98,130,198,232` — 6 接口 page_size 5000；`frontend/src/main.ts:6` — element-plus 全量 import 反面证据

## D9 用户体验

> **三层标尺说明**（第二轮 review 正式化，详见 M5-frontend.md §8 #4）：
>
> | 层 | 模块类型 | 标尺 | 当前模块 |
> |---|---|---|---|
> | **L1 面向用户 UI 模块** | 完整前端体验 | 参照 **M5=3** | M5、**M6**（含 LoginView/GlobalConfigView）|
> | **L2 后端 + 部分 UX 暴露** | 通过错误字段/响应间接影响 UX | 参照 **M3=2** | M3 |
> | **L3 纯基础设施** | 无 UI 相关代码 | **N/A** | M1、M2、M4、M7、M8 |
>
> M3 的 2 分反映的是"仅 push_error 字符串展示"的狭窄证据，保留作为 L2 基准不 retroactive 调整。M5 的 3 分是基于完整前端体验的实地评估，作为 L1 基准。

### M3 建议单与推送（首个有实质内容的模块）
- **得分**：2
- **理由**：满足 Rubric 2 级（push 错误分类层次清晰：PushBlockedError 含结构化 detail、SaihuAPIError code+message 格式化，push_error 字段持久化到 suggestion_item），未满足 3 级（无结构化错误码枚举，push 成功响应仅返回 task_id 无建议单状态摘要，主 UX 评估在 M5 前端）
- **关键证据**：`backend/app/api/suggestion.py:291-296` — PushBlockedError 含结构化 detail；`backend/app/pushback/purchase.py:98-100` — SaihuAPIError code+message；`backend/app/models/suggestion.py:103` — push_error Text 字段持久化

### M5 前端数据页（**D9 标尺源头模块，主战场**）
- **得分**：3
- **理由**：满足 Rubric 3 级（十项硬指标全部通过：
  1. **统一组件容器** `PageSectionCard` 跨 10 个 views 一致使用 `#title` + `#actions` slot；
  2. **全中文界面** `main.ts:7,17` Element Plus zhCn 注入 + `utils/status.ts` 枚举→中文 StatusMeta，Grep 未发现英文硬编码残留（`Loading/Submit` 57 处均为代码标识符非 UI 文案，LoginView 仅品牌 tagline "Sign in to Restock" 一处英文）；
  3. **设计系统 shadcn Zinc 对齐** `element-overrides.scss:1-80` 显式注释 shadcn 规范 + primary zinc-900 + light-3/5/7/8/9 分级 + 32 行 `:root` CSS 变量覆盖 + `tokens.scss` 设计 token + Vite 全局 SCSS 注入；
  4. **加载/空态/错误** 30 处 `el-empty / v-loading / el-alert` 跨 13 个 view；
  5. **错误提示具体可操作** `getActionErrorMessage` 五档 network-down / 500 / 业务 message / detail loc:msg / fallback；
  6. **跨页选择体验** `SuggestionListView:260-305` 四函数协同（handleSelection / handleSelectAll / syncTableSelection / suppressSelectionSync），筛选/sort 变化 `nextTick(clearSelection)` 防脏选；
  7. **筛选控件高度统一 32px** `PageSectionCard:51-55` + 多 view `:deep(.el-input) --el-component-size: 32px` Grep 18 处；
  8. **Tooltip/动画** `el-tooltip` 表格列名 + 长文本广泛使用；登录页网格交互 300/500ms 余温动画；侧栏 300ms 折叠动画；
  9. **状态反馈** `row-class-name=rowClass` urgent 行标红 + hover 变色；登录失败 pulse 动画 error-banner；任务 indeterminate progress + 状态 tag；ElMessage success/warning/error 三档；
  10. **移动端响应式** `@media (max-width: 900px / 1100px / 1280px)` 多断点，侧栏可收起 64px；423 登录锁定专门中文提示
  ），未满足 4 级（**a11y 严重不足**：Grep `aria-|role=` 仅 5 文件命中且多为 Element Plus 内置非应用层主动标注，无 `aria-label`/`aria-describedby`/`aria-live`/skip-link/对比度测试/键盘焦点管理；**无全局键盘快捷键**除 form `@keyup.enter` 外无 Ctrl+K / Esc 绑定；**无 i18n 基础设施** Grep `vue-i18n` → 0 matches，全中文硬编码；**无用户行为分析/A/B**；移动端非原生优化数据表格仍桌面布局；细节瑕疵：`DataOrdersView:205` 硬编码"加载失败"、WorkspaceView 静默吞异常、LoginView 英文 tagline 与中文 UX 轻微冲突）
- **关键证据**：`frontend/src/components/PageSectionCard.vue:1-64` + Grep 10 views 使用；`frontend/src/main.ts:7,17` Element Plus zhCn；`frontend/src/utils/status.ts:13-26` 枚举→中文 StatusMeta；`frontend/src/styles/element-overrides.scss:1-80` shadcn zinc 对齐；`frontend/src/views/SuggestionListView.vue:260-305` 跨页选择四函数；`frontend/src/utils/apiError.ts:9-36` 五档分类；Grep `el-empty|v-loading|el-alert` → 30 处 / 13 文件；`frontend/src/components/AppLayout.vue:549-563` + 多 view 响应式断点；`frontend/src/views/LoginView.vue:87-91` 423 特殊分支；负面证据：Grep `aria-|role=` 5 文件且多为 Element Plus 内置、Grep `vue-i18n` 0 matches
- **D9 标尺校准说明**：M3 先前试评 D9=2 仅依据"后端 push_error 字段持久化 + PushBlockedError 结构化 detail"是非常狭窄的单点错误信息本地化；M5 覆盖完整 UX 全链路不在同一尺度。**不 retroactive 调整 M3=2**（保留作为"后端模块默认 UX 上限"benchmark 有意义）。**M5=3 作为 D9 真正的标尺基准**，后续面向用户的界面模块（admin / 工作台 / 客户端）参照 M5=3 评；后端模块 D9 默认 N/A 或参照 M3=2。

> 注：M1/M2 的 D9 均为 N/A（无面向用户的操作型 API），M3 是第一个有实质 API 错误返回的模块，M5 是第一个完整覆盖前端 UX 的模块，作为 D9 的真正标尺源头。
