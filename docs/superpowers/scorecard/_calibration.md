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

## D9 用户体验

### M3 建议单与推送（首个有实质内容的模块）
- **得分**：2
- **理由**：满足 Rubric 2 级（push 错误分类层次清晰：PushBlockedError 含结构化 detail、SaihuAPIError code+message 格式化，push_error 字段持久化到 suggestion_item），未满足 3 级（无结构化错误码枚举，push 成功响应仅返回 task_id 无建议单状态摘要，主 UX 评估在 M5 前端）
- **关键证据**：`backend/app/api/suggestion.py:291-296` — PushBlockedError 含结构化 detail；`backend/app/pushback/purchase.py:98-100` — SaihuAPIError code+message；`backend/app/models/suggestion.py:103` — push_error Text 字段持久化

> 注：M1/M2 的 D9 均为 N/A（无面向用户的操作型 API），M3 是第一个有实质 API 错误返回的模块。
