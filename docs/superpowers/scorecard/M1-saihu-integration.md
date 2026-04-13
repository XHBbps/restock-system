# M1 赛狐集成 评分

> 评估日期：2026-04-11
> 评估人：subagent (claude-sonnet-4-6)
> 范围：与赛狐 API 的所有交互层
> 主战场维度：D3 / D4 / D6

---

## 1. 证据采集摘要

### 1.1 阅读的文件

- `backend/app/saihu/client.py` — 279 行
- `backend/app/saihu/token.py` — 171 行
- `backend/app/saihu/rate_limit.py` — 31 行
- `backend/app/saihu/sign.py` — 56 行
- `backend/app/saihu/endpoints/order_detail.py` — 21 行
- `backend/app/saihu/endpoints/order_list.py` — 50 行
- `backend/app/saihu/endpoints/product_listing.py` — 44 行
- `backend/app/saihu/endpoints/out_records.py` — 36 行
- `backend/app/saihu/endpoints/shop.py` — 30 行
- `backend/app/saihu/endpoints/purchase_create.py` — 54 行
- `backend/app/saihu/endpoints/warehouse.py` — 28 行
- `backend/app/saihu/endpoints/inventory.py` — 41 行
- `backend/app/sync/order_detail.py` — 231 行
- `backend/app/sync/order_list.py` — 192 行
- `backend/app/sync/product_listing.py` — 97 行
- `backend/app/sync/inventory.py` — 106 行
- `backend/app/sync/out_records.py` — 166 行
- `backend/app/sync/shop.py` — 75 行
- `backend/app/sync/warehouse.py` — 86 行
- `backend/app/models/api_call_log.py` — 41 行
- `backend/app/config.py` — 103 行
- `backend/app/core/exceptions.py` — 97 行
- `backend/app/core/logging.py` — 69 行
- `backend/app/core/middleware.py` — 50 行
- `backend/tests/unit/test_saihu_sync_helpers.py` — 57 行
- `backend/tests/unit/test_sync_order_detail_classification.py` — 44 行
- `backend/tests/unit/test_sync_warehouse.py` — 15 行
- `backend/tests/unit/test_sign.py` — 59 行
- `backend/tests/unit/test_runtime_settings.py` — 57 行
- `deploy/docker-compose.yml` — 163 行
- `deploy/scripts/validate_env.sh` — 48 行
- `docs/deployment.md` — 205 行

### 1.2 测试运行结果

```
pytest tests/unit/ -k "saihu or sync or order_detail" -v
结果：58 passed, 82 deselected in 1.06s

M1 直接相关测试（通过）：
- test_saihu_sync_helpers.py::test_normalize_online_status_lowercases_real_response
- test_saihu_sync_helpers.py::test_sanitize_detail_country_uses_marketplace_id
- test_saihu_sync_helpers.py::test_postal_code_for_routing_preserves_real_postal_code
- test_saihu_sync_helpers.py::test_disabled_address_fields_are_all_null
- test_saihu_sync_helpers.py::test_disabled_order_detail_fields_hide_existing_values
- test_sync_order_detail_classification.py::test_saihu_biz_error_is_permanent
- test_sync_order_detail_classification.py::test_saihu_rate_limited_is_transient
- test_sync_order_detail_classification.py::test_saihu_network_error_is_transient
- test_sync_order_detail_classification.py::test_saihu_auth_expired_is_transient
- test_sync_order_detail_classification.py::test_bare_saihu_api_error_is_transient
- test_sync_order_detail_classification.py::test_generic_exception_is_transient
- test_sync_warehouse.py::test_normalize_replenish_site_truncates_long_values
- test_sync_warehouse.py::test_normalize_replenish_site_keeps_short_values
- test_sign.py（3 个签名算法测试，含官方 fixture 比对）
- test_runtime_settings.py::test_production_settings_require_real_secrets

全量 pytest tests/unit/：140 passed, 0 failed
```

### 1.3 关键 grep 结果摘录

- **SAIHU_ 密钥来源**：`SAIHU_CLIENT_ID` / `SAIHU_CLIENT_SECRET` 全部走环境变量（`backend/app/config.py:36-38`，`deploy/docker-compose.yml:9-10`）；`backend/.env.example:22-23` 有示例占位符，不含真实值
- **重试策略**：tenacity `AsyncRetrying`，`stop_after_attempt(settings.saihu_max_retries)`（默认 3），`wait_exponential(multiplier=1, min=1, max=10)`，retry 仅针对 `SaihuRateLimited | SaihuNetworkError`；`SaihuAuthExpired` 在预算外额外给一次完整重试（`backend/app/saihu/client.py:76-97`）
- **限流策略**：`aiolimiter.AsyncLimiter`，默认 1 QPS/接口；`/api/order/detailByOrderId.json` 有独立 override 3 QPS（`backend/app/saihu/rate_limit.py:18-20`）；`sync/order_detail.py` 并发度 `CONCURRENCY=3` 与之匹配（`backend/app/sync/order_detail.py:31`）
- **出口 IP / 代理**：Grep 全库无 `proxy`、`HTTP_PROXY`、`HTTPS_PROXY`、`outbound`、`whitelist` 相关配置。`httpx.AsyncClient` 创建时未传 `proxies` 参数（`backend/app/saihu/client.py:51-54`，`backend/app/saihu/token.py:115`）。无任何代理接入点。
- **错误分类**：`SaihuBizError`（永久错误，不重试）/`SaihuRateLimited`/`SaihuNetworkError`（可重试）/`SaihuAuthExpired`（token 刷新重试）四类明确区分（`backend/app/core/exceptions.py:83-97`，`backend/app/sync/order_detail.py:34-45`）
- **日志脱敏**：日志器通过 `get_logger` 调用 structlog；日志事件为语义名（`saihu_token_refresh_start`、`saihu_auth_expired_retry_outside_budget`），无 `token=`、`secret=`、`password=` 明文字段出现在日志调用处
- **api_call_log**：每次请求（成功或失败）都在 `_log()` 写入（`backend/app/saihu/client.py:237-267`）；有错误类型字段 `error_type`（auth_fail / rate_limit / biz_error / network）和 `retry_count`；监控 API（`monitor.py`、`metrics.py`）基于此表做聚合查询

---

## 2. 维度评分

### D1 功能完整性
- **得分**：3/4
- **判据匹配**：满足 Rubric 3 级"边界场景已处理；少量低频场景未覆盖但已记录 TODO"；未满足 4 级"异常恢复路径覆盖；契约/集成测试守护回归"
- **支撑证据**：
  - `backend/app/saihu/client.py:75-97` — 主链路完整：限流重试 + token 失效预算外重试
  - `backend/app/saihu/rate_limit.py:18-20` — detailByOrderId 的 3 QPS 特殊限额已实现
  - `backend/app/sync/order_detail.py:34-45` — 永久/瞬态错误分类，防止坏订单 ID 无限重试
  - `backend/app/sync/out_records.py:138-156` — 在途记录老化机制完整
  - `backend/app/saihu/endpoints/purchase_create.py:34-38` — include_tax / action 入参校验
  - `backend/app/sync/order_list.py:80-84` — 首次回填 + 增量重叠窗口
- **未达上一级的差距**：缺乏针对 `SaihuClient._do_request`、`TokenManager._refresh` 等核心方法的集成/契约测试；无 HTTP 层 mock 测试验证实际 POST 体、签名注入、分页终止条件
- **疑点**：✅ 已澄清（见 §7 用户澄清记录 #2）——地址字段为**临时规避**，将来启用时需要回填历史数据。已加入 P1 列表。

### D2 代码质量
- **得分**：2/4
- **判据匹配**：满足 Rubric 2 级"lint + format 通过；核心模块单测 >50%；重复代码已识别"；未满足 3 级"type check 通过 + 单测覆盖 >70% + 命名清晰无明显代码异味"
- **支撑证据**：
  - `backend/tests/unit/test_sign.py:17-28` — 签名算法有官方 fixture 比对测试
  - `backend/tests/unit/test_sync_order_detail_classification.py` — 错误分类逻辑 6 个测试全部通过
  - `backend/app/saihu/client.py:61-97` — async/await 使用正确，类型注解清晰
  - 140 个单测全部通过（0 failed）
- **未达上一级的差距**：`SaihuClient.post`、`_do_request`、`TokenManager` 核心方法无单测覆盖（需 httpx mock）；`rate_limit.py` 无测试；整个 `saihu/client.py` 和 `saihu/token.py` 均无测试；覆盖率达不到 70%
- **疑点**：无

### D3 安全性 ⚠️
- **得分**：2/4
- **判据匹配**：满足 Rubric 2 级"密钥走环境变量 + Pydantic 全量校验 + 启动时配置校验"；未满足 3 级"速率限制 + 日志脱敏 + TLS + 安全 headers"（部分满足，部分缺失）
- **支撑证据**：
  - `backend/app/config.py:36-38` — `saihu_client_id` / `saihu_client_secret` 均为 pydantic-settings 字段，从环境变量读取
  - `backend/app/config.py:86-90` — 生产环境启动时检查 `SAIHU_CLIENT_ID` / `SAIHU_CLIENT_SECRET` 不为空，否则 raise ValueError
  - `deploy/scripts/validate_env.sh:17-32` — 部署前脚本强制校验 SAIHU_ 凭证非空
  - `backend/app/saihu/client.py:113-125` — `access_token` 以 query param 方式注入，走 HTTPS（`saihu_base_url` 默认 `https://openapi.sellfox.com`）；不会在 JSON body 出现
  - `backend/app/core/logging.py:40-43` — 生产环境输出 JSON 结构化日志
  - 日志调用处无 `token=` / `secret=` 明文字段（grep 确认）
- **未达上一级的差距（3 级缺失项）**：
  - **出口 IP 接入点缺失**：代码无 proxy/HTTP_PROXY 支持，赛狐有 IP 白名单，上云后出口 IP 变化将导致 API 完全不可达（见 P0-1）
  - **CVE 扫描**：无 `pip-audit` / `safety` 集成
  - **依赖安全扫描**：无 CI pipeline 扫描
  - 注：`access_token` 明文存 DB 已经过用户确认接受（短周期 24h 凭证）—— 见 §7 #4
- **疑点**：✅ 已澄清（见 §7 #4）——`access_token` 明文 DB 存储用户已接受；URL query param 传输方式因 worker 直接出公网不经反向代理，实际泄漏面很小，已降级到 P2

### D4 可部署性
- **得分**：3/4
- **判据匹配**：满足 Rubric 3 级"2 + 一键部署脚本（备份/迁移/部署/回滚/smoke）+ 启动时配置校验 + 资源限制"；未满足 4 级"蓝绿/滚动部署 + IaC + 多环境 + CI/CD"
- **支撑证据**：
  - `deploy/docker-compose.yml:8-10` — SAIHU_ 凭证通过环境变量注入容器
  - `deploy/scripts/validate_env.sh:17-32` — 部署前校验 SAIHU_CLIENT_ID/SECRET 非空
  - `deploy/scripts/deploy.sh` 存在，含备份/迁移/部署/smoke/回滚完整流程（deployment.md 第 4.1 节）
  - `backend/app/config.py:72-96` — 启动时 `validate_settings()` 生产环境校验 SAIHU_ 凭证
  - `deploy/docker-compose.yml:51-55、74-76、96-98` — 所有服务有 `deploy.resources.limits.memory` 资源限制
  - `deploy/docker-compose.yml:20-29` — `/readyz` 健康检查
- **未达上一级的差距**：无 CI/CD pipeline；无 IaC（Terraform 等）；无蓝绿/滚动部署能力；无多环境（staging）配置
- **疑点**：⚠️ `deploy/docker-compose.yml` 中 SAIHU_ 凭证无 `SAIHU_BASE_URL` 代理配置预留位——出口 IP 问题无法通过环境变量切换代理解决

### D5 可观测性
- **得分**：3/4
- **判据匹配**：满足 Rubric 3 级"结构化日志 + request_id + 业务事件指标 + 监控端点 + 错误告警"；未满足 4 级"OpenTelemetry + Grafana + SLO/SLI + 外部主动探测"
- **支撑证据**：
  - `backend/app/core/logging.py:32-51` — structlog JSON 结构化日志，生产环境启用
  - `backend/app/core/middleware.py:22-24` — 每请求绑定 `request_id` 到 contextvars，X-Request-Id 随响应返回
  - `backend/app/models/api_call_log.py` — 记录 endpoint / duration_ms / http_status / saihu_code / error_type / retry_count，双索引（按接口+时间、按失败）
  - `backend/app/saihu/client.py:196-210` — rate_limit 命中（40019）写 `error_type="rate_limit"` 到 api_call_log
  - `backend/app/api/monitor.py` — `/api/monitor/saihu-calls` 端点提供成功率聚合；`/api/monitor/api-calls` 提供原始日志查询
  - `backend/app/api/metrics.py` — 独立的 `/api/metrics/saihu` 端点
- **未达上一级的差距**：无 OpenTelemetry trace；无外部 /metrics（Prometheus 格式）暴露；无 Grafana 看板；无 SLO/SLI 定义；无外部主动探测（uptime robot 等）
- **疑点**：无

### D6 可靠性
- **得分**：3/4
- **判据匹配**：满足 Rubric 3 级"2 + 指数退避 + 错误分类映射 + 异常分类"；未满足 4 级"chaos test + 灾难恢复演练 + 故障注入 + 自动故障转移"
- **支撑证据**：
  - `backend/app/saihu/client.py:77-80` — tenacity 指数退避 `wait_exponential(multiplier=1, min=1, max=10)`，3 次上限
  - `backend/app/saihu/client.py:79` — retry 仅针对可重试错误（`SaihuRateLimited | SaihuNetworkError`）；`SaihuBizError` 不重试（永久错误隔离）
  - `backend/app/saihu/client.py:89-97` — `SaihuAuthExpired` 在预算外单独处理，0.5s 回退后 force_refresh + 完整重试
  - `backend/app/saihu/client.py:53` — `timeout=settings.saihu_request_timeout_seconds`（默认 30s）
  - `backend/app/saihu/rate_limit.py` — aiolimiter 防止应用侧主动超速，降低 40019 概率
  - `backend/app/sync/order_detail.py:34-45` — `_is_permanent_saihu_error()` 明确永久/瞬态分类，测试守护
  - `backend/app/sync/order_list.py:141-144` — UPSERT 保证幂等
  - `backend/app/saihu/token.py:73-96` — single-flight 防止并发刷 token
- **未达上一级的差距**：无熔断器（circuit breaker）；无死信队列；无 chaos test；无自动故障转移；超时仅为整体请求超时，无连接超时单独配置
- **疑点**：⚠️ `saihu_max_retries=3` 配合 `wait_exponential(max=10)` 最坏情况等待 ≈ 1+2+4=7s（加请求本身 30s × 3 ≈ 97s），在高失败率下单次 sync job 可能超时

### D7 可维护性
- **得分**：3/4
- **判据匹配**：满足 Rubric 3 级"模块边界清晰 + 文档同步协议 + 注释覆盖非显然逻辑"；未满足 4 级"自动化文档生成 + 完整 ADR 历史 + onboarding < 1h + 架构图自动同步"
- **支撑证据**：
  - `backend/app/saihu/` 分层清晰：`client.py`（HTTP+retry+log）/ `token.py`（token 生命周期）/ `rate_limit.py`（限流）/ `sign.py`（签名）/ `endpoints/`（业务接口封装）
  - `backend/app/saihu/client.py:1-9` — 模块级文档字符串完整列出所有特性
  - `backend/app/sync/order_detail.py:34-44` — `_is_permanent_saihu_error` 有详尽 docstring 解释分类依据
  - `backend/app/saihu/client.py:67-70` — token 失效重试预算分离逻辑有注释
  - `docs/saihu_api/` 包含完整的 API 文档目录
  - AGENTS.md / CLAUDE.md / docs/deployment.md 存在
- **未达上一级的差距**：无 ADR（架构决策记录）追踪如"为何选 aiolimiter 而非 token bucket"等决策；无自动化文档生成（OpenAPI 以外）；onboarding 时间未量化
- **疑点**：无

### D8 性能与容量
- **得分**：2/4
- **判据匹配**：满足 Rubric 2 级"关键接口无明显 N+1；批量接口分页"；未满足 3 级"接口 SLO 明确 + 慢查询日志 + 容量评估文档"
- **支撑证据**：
  - `backend/app/saihu/rate_limit.py:18-20` — 订单详情 3 QPS，接近赛狐允许上限充分利用
  - `backend/app/sync/order_detail.py:31,101-104` — `CONCURRENCY=3` 与 rate limiter 匹配，无浪费
  - `backend/app/saihu/endpoints/order_list.py:29-49` — 分页迭代，`page_size=100`
  - `backend/app/models/api_call_log.py:20-26` — `ix_api_call_log_endpoint_time` + 失败过滤索引
  - `backend/app/sync/order_detail.py:124-155` — `_find_pending_orders` 使用 join + left outer join + distinct，有 LIMIT 500 防暴走
- **未达上一级的差距**：无 SLO 定义（如"sync_order_detail 每批 500 条完成时间 < X 分钟"）；无慢查询日志配置；无负载测试基线；无容量评估文档（当 order 量 > 10 万时 api_call_log 表增长速率未评估）；api_call_log 无清理/归档机制
- **疑点**：✅ 已澄清（见 §7 #3 / #5）——`api_call_log` 保留 30 天 + daily_archive 清理（已纳入 P1）；`MAX_PER_RUN=500` 在用户日均订单 < 500 的场景下完全够用，已不构成问题

### D9 用户体验
- **得分**：N/A
- **理由**：M1 赛狐集成层无直接 UI，不参与计分

---

## 3. 模块得分

- **各维度分数**：D1=3, D2=2, D3=2, D4=3, D5=3, D6=3, D7=3, D8=2
- **平均分（剔除 N/A，8 维度）**：(3+2+2+3+3+3+3+2) / 8 = **2.63 / 4**
- **主战场维度**：D3=2 D4=3 D6=3

---

## 4. 本模块发现的关键问题

### 🔴 P0 阻塞

1. **赛狐 API 出口 IP 不可达：代码层无代理接入点** ｜ 状态：📌 用户已 acknowledge，云部署阶段统一解决
   - 现状：用户已知当前 IP 无法调用赛狐 API（IP 白名单机制）；`httpx.AsyncClient` 创建时无 `proxies` 参数，环境变量中无 `SAIHU_HTTP_PROXY` / `HTTP_PROXY` 支持（`backend/app/saihu/client.py:51-54`，`backend/app/saihu/token.py:115`）
   - 风险：上云部署后出口 IP 改变，赛狐 API 将完全不可达，所有 sync job 均失败，系统无法获取数据
   - 修复动作：方案 A — 向赛狐申请云服务器 IP 加白名单（无需代码改动）；方案 B — 在 `SaihuClient._ensure_http()` 中读取 `SAIHU_HTTP_PROXY` 环境变量并注入到 `httpx.AsyncClient(proxies=...)`，`token.py:115` 同样处理，并在 `deploy/.env.example` 和 `deploy/docker-compose.yml` 中添加 `SAIHU_HTTP_PROXY` 可选配置项
   - **用户决策**：方案待定，云部署阶段统一处理。本评分卡保留 P0 标记作为待办提醒，不影响其他维度评分

### 🟡 P1 强烈建议

1. **`api_call_log` 无清理机制，存在无界增长风险** ｜ 用户已确认保留 30 天
   - 现状：每次赛狐 API 调用（包括重试）都写入 `api_call_log`，无 TTL、无清理任务（`backend/app/models/api_call_log.py`）
   - 风险：高频同步（6 个 job × 每小时 1 次 × 分页调用数十次）数周后表可达数十万行；影响查询性能
   - 修复动作：在现有 `daily_archive` job（02:00 触发）中添加 `api_call_log` 清理逻辑，**保留最近 30 天数据**（用户确认）；删除超过 30 天的记录

2. **核心客户端层缺乏集成测试（SaihuClient / TokenManager）**
   - 现状：`saihu/client.py`（279 行）和 `saihu/token.py`（171 行）无任何单测，仅有间接测试
   - 风险：retry 逻辑、token 刷新 single-flight、分页终止条件等关键路径无回归保护
   - 修复动作：使用 `respx` 或 `pytest-httpx` mock httpx，添加核心路径测试（retry 次数验证、40001 触发 force_refresh 验证、分页终止验证）

3. **订单详情地址字段当前禁用，将来启用时需要回填策略** ｜ 用户已确认未来要回填
   - 现状：`backend/app/sync/order_detail.py:9-10` 注释 "Address fields from Saihu order detail are not used and are stored as null"，邮政编码路由逻辑已实现但 state/city/detail_address/receiver_name 全部存 null
   - 风险：用户已确认这是临时规避，将来需要启用并**回填历史订单的地址数据**；如不提前规划字段映射保留策略，回填时可能因为来源数据已被覆盖或赛狐侧已无法查询而无法补全
   - 修复动作：（a）记录"地址字段启用"为待办；（b）启用前评估是否需要重新拉取历史订单详情；（c）建议先在 sync 层保留地址字段从赛狐返回中提取的逻辑（注释掉而非删除），便于将来一键启用

### 🟢 P2 可延后

1. **`api_call_log` 中 `saihu_msg` 字段无长度截断保护**
   - 现状：`ApiCallLog.saihu_msg` 为 `Text` 类型（无限制），`_log_fetch_failure` 有 `[:1000]` 截断但 `client._log()` 无截断
   - 风险：赛狐返回异常长消息时写入超大文本行
   - 修复动作：`client._log()` 中对 `saihu_msg` 截断至 1000 字符

2. **无 CVE/依赖安全扫描**
   - 现状：无 `pip-audit` 或 `safety` 集成
   - 风险：第三方依赖（httpx, tenacity, aiolimiter）存在已知漏洞时无自动告警
   - 修复动作：添加到 CI pipeline 或定期 pre-commit hook

3. **`access_token` 通过 URL query param 传输** ｜ 从 P1 降级（用户已接受 token 风险）
   - 现状：`client.py:120-126` 中 `access_token` 以 query param 注入到 URL；HTTPS 加密保护传输，但中间代理 access log 可能明文记录
   - 风险：worker 容器直接出公网调用赛狐，**不经过 Caddy 反向代理**，应用侧 access log 也未启用 → 实际泄漏面很小
   - 修复动作（如未来增加出口代理 / NAT 网关）：确认中间组件不记录 query string，或将 token 改为 header 传递（需评估赛狐 API 是否支持）

---

## 5. P0/P1 候选清单交叉判定

### P0-1 赛狐 API 对当前 IP 不可达 / 出口 IP 接入点

- **判定**：❌ 未实现
- **证据**：
  - `backend/app/saihu/client.py:49-54` — `httpx.AsyncClient(base_url=..., timeout=...)` 无 `proxies` 参数
  - `backend/app/saihu/token.py:115` — `httpx.AsyncClient(timeout=...)` 同样无 `proxies` 参数
  - Grep 全库无 `proxy`、`HTTP_PROXY`、`HTTPS_PROXY`、`outbound`、`whitelist` 任何相关配置（0 匹配）
  - `deploy/docker-compose.yml` 无 `SAIHU_HTTP_PROXY` 环境变量
- **结论**：代码层完全未预留代理/出口 IP 切换接入点，上云部署后若赛狐 IP 白名单未更新则所有赛狐 API 调用失败

---

## 6. 给用户的确认问题

✅ 全部 5 个疑点在第一轮 review 中已由用户澄清，详见 §7 用户澄清记录。

---

## 7. 用户澄清记录（2026-04-11 第一轮 review）

### #1 出口 IP / 白名单问题
- **疑问**：方案 A（申请白名单）vs 方案 B（部署代理/NAT）？
- **用户回答**：暂不考虑，云部署阶段统一解决
- **影响**：P0-1 保留为待办（📌 acknowledge 标记），不影响其他维度评分；不立即修改代码

### #2 订单详情地址字段禁用决策
- **疑问**：永久禁用还是临时规避？将来需要回填吗？
- **用户回答**：临时规避，**后续如果拉取到数据就要回填**
- **影响**：D1 疑点改为已澄清；新增 P1 项"地址字段启用与回填策略"（防止将来回填时数据来源已不可用）

### #3 api_call_log 数据保留策略
- **疑问**：30 天 / 90 天 / 永久？
- **用户回答**：**同意 30 天**（Claude 建议）
- **影响**：P1 项"api_call_log 无清理机制"明确修复动作为"在 daily_archive job 中删除超过 30 天的记录"

### #4 access_token 明文存 PostgreSQL
- **疑问**：是否接受短周期 token 明文存储？
- **用户回答**：**接受**
- **影响**：D3 未达上一级清单删除 token 加密项；原 P1 "access_token URL query param" 降级到 P2（worker 直接出公网，不经反向代理 access log，泄漏面小）

### #5 sync_order_detail MAX_PER_RUN=500
- **疑问**：500/批速率是否满足？
- **用户回答**：**日均新订单 < 500**
- **影响**：D8 疑点解除；MAX_PER_RUN=500 在稳态运行下完全够用，不构成 P1/P2 问题；冷启动场景可手动连续触发 job 追平历史
