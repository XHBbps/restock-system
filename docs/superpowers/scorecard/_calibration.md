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

### M1 赛狐集成
- **得分**：3
- **理由**：满足 Rubric 3 级（主链路端到端完整、边界场景已处理、永久/瞬态错误分类、在途老化机制），未满足 4 级（无集成/契约测试守护核心路径，如分页终止、retry 次数、token 刷新 single-flight）
- **关键证据**：`backend/app/saihu/client.py:75-97` — retry + auth_expired 双重重试逻辑；`backend/app/sync/order_detail.py:34-45` — 永久错误分类测试守护

## D2 代码质量

### M1 赛狐集成
- **得分**：2
- **理由**：满足 Rubric 2 级（140 个单测全 pass，签名算法有官方 fixture 比对，错误分类 6 个测试守护），未满足 3 级（`SaihuClient`/`TokenManager` 核心方法无单测，整个 client.py/token.py 无 httpx mock 测试，覆盖率不足 70%）
- **关键证据**：`backend/tests/unit/test_sign.py:17-28` — 官方 fixture 签名测试；`backend/tests/unit/test_sync_order_detail_classification.py` — 6 个错误分类测试；`backend/app/saihu/client.py` — 无对应测试文件

## D3 安全性

### M1 赛狐集成
- **得分**：2
- **理由**：满足 Rubric 2 级（SAIHU_ 密钥走环境变量，pydantic-settings 全量校验，启动时生产环境配置强制校验，日志无明文密钥），未满足 3 级（代码层无代理/出口 IP 接入点是核心缺口；无 CVE 扫描；`access_token` 作为 URL query param 传输）
- **关键证据**：`backend/app/config.py:36-38,86-90` — env var 读取 + 生产校验；Grep 全库无 proxy/HTTP_PROXY 匹配（P0-1 ❌ 未实现）

## D4 可部署性

### M1 赛狐集成
- **得分**：3
- **理由**：满足 Rubric 3 级（docker-compose 一键启动，.env.example，一键部署脚本含备份/迁移/回滚/smoke，启动时配置校验，资源限制），未满足 4 级（无 CI/CD，无 IaC，无蓝绿部署，无多环境）；但 SAIHU_HTTP_PROXY 代理配置未预留是上云缺口
- **关键证据**：`deploy/scripts/validate_env.sh:17-32` — 部署前强校验 SAIHU_ 凭证；`deploy/docker-compose.yml:51-55` — 资源限制；`docs/deployment.md:116-130` — 一键部署脚本流程

## D5 可观测性

### M1 赛狐集成
- **得分**：3
- **理由**：满足 Rubric 3 级（structlog JSON 日志，request_id 自动绑定，api_call_log 完整记录含 error_type/retry_count，限流命中有 rate_limit 错误分类，/api/monitor/saihu-calls 聚合端点），未满足 4 级（无 OpenTelemetry，无 Prometheus /metrics，无 Grafana，无 SLO/SLI）
- **关键证据**：`backend/app/models/api_call_log.py:38-40` — error_type + retry_count 字段；`backend/app/saihu/client.py:197-210` — rate_limit 命中写入 api_call_log；`backend/app/api/monitor.py:42-50` — EndpointStats 聚合模型

## D6 可靠性

### M1 赛狐集成
- **得分**：3
- **理由**：满足 Rubric 3 级（指数退避 wait_exponential，错误分类明确 permanent/transient，token single-flight，aiolimiter 防超速，UPSERT 幂等，超时配置），未满足 4 级（无熔断器，无死信队列，无 chaos test，无故障注入）
- **关键证据**：`backend/app/saihu/client.py:77-80` — tenacity 指数退避；`backend/app/saihu/token.py:73-96` — single-flight；`backend/app/sync/order_detail.py:34-45` — permanent/transient 分类

## D7 可维护性

### M1 赛狐集成
- **得分**：3
- **理由**：满足 Rubric 3 级（client/endpoints/sync 分层清晰，模块级 docstring 完整，非显然逻辑有注释，saihu_api 完整文档目录，AGENTS.md/deployment.md/runbook.md 存在），未满足 4 级（无 ADR，无自动化文档生成，无 onboarding 时间量化）
- **关键证据**：`backend/app/saihu/client.py:1-9` — 特性列表 docstring；`backend/app/sync/order_detail.py:34-44` — _is_permanent_saihu_error 详尽注释；`docs/saihu_api/` — 完整 API 文档目录

## D8 性能与容量

### M1 赛狐集成
- **得分**：2
- **理由**：满足 Rubric 2 级（无明显 N+1，分页迭代覆盖所有接口，aiolimiter 充分利用 3 QPS 上限，api_call_log 有复合索引，MAX_PER_RUN=500 防暴走），未满足 3 级（无 SLO 定义，无慢查询日志，无容量评估，api_call_log 无清理机制）
- **关键证据**：`backend/app/saihu/rate_limit.py:18-20` — 3 QPS override；`backend/app/sync/order_detail.py:31,101` — CONCURRENCY=3 匹配 limiter；`backend/app/models/api_call_log.py:20-26` — 双索引；api_call_log 无 TTL/清理任务（P1 问题）

## D9 用户体验

（待填入）
