# Restock System 优化项 Backlog（P0–P3）

> 创建日期：2026-04-17
> 数据来源：`2026-04-17-system-assessment.md` 证据链 + 补充扫描
> 分级口径：**P0 必做（事故风险）/ P1 季度内（显著债务）/ P2 有空做（质量提升）/ P3 观察备案**
> 工作量单位：**S < 1 天 / M 1–3 天 / L > 3 天**

---

## 0. 快速索引（Kanban）

### P0 — 必做（8 项）

| # | 项目 | 维度 | 工作量 |
|---|---|---|---|
| P0-1 | backend 容器以 root 运行 | 安全 / 部署 | S |
| P0-2 | `deploy.sh` 迁移失败自动 restore_db | 部署 / 容错 | M |
| P0-3 | 审计日志无保留期清理策略 | 合规 / 数据 | M |
| P0-4 | `/docs` & `/openapi.json` 公网可访问（依赖默认值） | 安全 / 合规 | S |
| P0-5 | JWT_SECRET / 赛狐凭证无轮换执行人 + 频率 | 安全 | S |
| P0-6 | CI 缺 SAST（bandit）/ SCA（trivy）扫描 | 安全 / CI | S |
| P0-7 | backend/.env 曾被误提交（需确认无泄漏） | 安全 | S |
| P0-8 | API 数据页 54 个查询函数缺排序/过滤边界单测 | 测试 / 代码质量 | M |

### P1 — 季度内（18 项）

| # | 项目 | 维度 | 工作量 |
|---|---|---|---|
| P1-1 | `api/data.py` 1002 行按资源拆分 | 架构 / 维护 | M |
| P1-2 | mypy 16 模块豁免分批解除 | 代码质量 | L |
| P1-3 | `AppLayout.vue` 716 行拆子组件 | 维护 / UX | M |
| P1-4 | `api/metrics.py` 517 行按域拆分 | 架构 | M |
| P1-5 | engine 6 step 耗时日志 + Prometheus gauge | 可观测 / 性能 | S |
| P1-6 | Worker/Reaper Prometheus 指标（队列/回收） | 可观测 | S |
| P1-7 | 集成测试仅 3 个（订单同步 / reaper / readyz） | 测试 | M |
| P1-8 | 全局 error boundary 组件 | UX / 可靠性 | S |
| P1-9 | legacy redirect 11 项无版本删除计划 | 技术债 | S |
| P1-10 | `ADR-5` 实现漂移：SuggestionDetailView 未迁 PageSectionCard | 维护 / UX | M |
| P1-11 | 40001/40019 完整恢复链路 E2E 测试 | 测试 / 可靠性 | M |
| P1-12 | `sidebar.ts` Set + watch deep 响应性改 Pinia reactive | 技术债 / 前端 | S |
| P1-13 | order_header 排序部分索引 | 性能 / 数据 | S |
| P1-14 | LOGIN_PASSWORD 强度校验 | 安全 | S |
| P1-15 | `appPages.navCategory` 改为 TS enum 编译期校验 | 扩展 / 代码质量 | S |
| P1-16 | Reaper 回收 `logger.critical()` + counter | 可观测 / 可靠性 | S |
| P1-17 | PR / `AGENTS.md` 加"新增数据页/任务"checklist | 扩展 / 维护 | S |
| P1-18 | 文件/函数行数 lint 规则（PLR0915 + 自定义） | 代码质量 | S |

### P2 — 有空做（18 项）

| # | 项目 | 维度 | 工作量 |
|---|---|---|---|
| P2-1 | `order_detail` 部分索引（邮编非空） | 数据 / 性能 | S |
| P2-2 | `suggestion_item (suggestion_id, push_status)` 索引 | 数据 | S |
| P2-3 | Caddy ETag / 304 缓存 | 性能 | S |
| P2-4 | 前端缺网络超时 case 测试 | 测试 | M |
| P2-5 | Caddyfile `/docs` 加内网 matcher | 安全 | S |
| P2-6 | engine 新增 step 的标准模板文档 | 扩展 | S |
| P2-7 | `paginationMode` 字段标注 appPages | 前端 / 维护 | S |
| P2-8 | `api/data.py` 27 个查询提取 Repository 层 | 架构 | L |
| P2-9 | 死信队列（DLQ）/ 失败重放机制 | 可靠性 | L |
| P2-10 | 数据库迁移 downgrade 真实回跑测试 | 数据 / 部署 | M |
| P2-11 | 前端构建产物体积监控（bundle analyzer） | 性能 / DX | S |
| P2-12 | `/healthz` `/readyz` 响应缓存避免高频压力 | 可观测 | S |
| P2-13 | 前端 Monitor 页图表骨架屏 | UX | S |
| P2-14 | `sync_state` 表消费方统一封装（避免散落 SQL） | 维护 / 数据 | M |
| P2-15 | `core/rate_limit.py` 抽象为可插拔（内存 / Redis） | 扩展 / 安全 | M |
| P2-16 | engine advisory lock 超时可配置 | 可靠性 | S |
| P2-17 | 前端 `useAsyncState` 统一 API 调用封装 | UX / DX | M |
| P2-18 | vendor chunk 再细分 | 性能 | S |

### P3 — 观察备案（10 项）

| # | 项目 | 维度 | 工作量 |
|---|---|---|---|
| P3-1 | 多租户 / 水平扩展（SaaS 化前置条件） | 架构 | L |
| P3-2 | Celery / Redis 替代 TaskRun（规模突破后） | 架构 / 可靠性 | L |
| P3-3 | 前端虚拟滚动（数据量突破 10k 行后） | 性能 | M |
| P3-4 | WebSocket 任务状态推送替代轮询 | UX | M |
| P3-5 | Vault / AWS Secrets Manager 接入 | 安全 | L |
| P3-6 | Playwright E2E 浏览器测试 | 测试 | L |
| P3-7 | Grafana 仪表盘（对接 Prometheus） | 可观测 | M |
| P3-8 | 多机部署（外部分布式锁替代 advisory lock） | 架构 | L |
| P3-9 | 前端 SSR / SSG（seo 无需求，可能永不做） | 前端 | L |
| P3-10 | 英文 i18n（当前仅中文 UI） | UX | L |

**合计**：54 项。建议节奏——本周清 P0 的 S 项（5 项），下周处理 P0 的 M 项 + P1 前 5 项。

---

## 1. 架构设计

### [P1-1] `api/data.py` 1002 行按资源拆分
- **问题**：单文件聚合 7 种资源 22 个端点，查询逻辑与响应组装耦合
- **证据**：`backend/app/api/data.py`（1002 行，27 个查询函数）
- **影响**：可读性差 / 修改冲突多 / 测试难覆盖
- **建议**：拆为 `api/data/{orders,inventory,out_records,products,shops,warehouses,suggestions}.py`，`__init__.py` 聚合路由
- **工作量**：M

### [P1-4] `api/metrics.py` 517 行按域拆分
- **问题**：dashboard / monitor / prometheus 三个域混在一文件
- **证据**：`backend/app/api/metrics.py`
- **影响**：改 dashboard 统计时容易误动 prometheus 输出
- **建议**：拆 `api/metrics/{dashboard,monitor,prometheus}.py`
- **工作量**：M

### [P2-8] API 层缺 Repository 层
- **问题**：27 个查询函数复用困难，`_apply_sort` / `_apply_filters` 私有且签名不一
- **证据**：`backend/app/api/data.py`
- **影响**：新增类似查询仍需从头拼 SQL
- **建议**：提取 `app/repositories/data_queries.py`，统一入参 Pydantic `QueryParams`
- **工作量**：L

### [P3-1] 多租户 / 水平扩展
- **问题**：当前单租户假设深植（`global_config` 单例、`advisory_lock` 常量 key）
- **影响**：若业务转向 SaaS 需要大规模重构
- **建议**：观察，当前 1–5 用户规模不成立
- **工作量**：L

---

## 2. 代码质量

### [P0-8] API 数据页端点缺边界单测
- **问题**：54 个查询函数的排序/过滤组合多数无单测
- **证据**：`backend/tests/unit/test_data_*.py` 只覆盖部分端点
- **影响**：引入 SQL 拼接 bug 难被测试拦截
- **建议**：按资源 parametrize `sort_by × sort_order × filters` 矩阵
- **工作量**：M

### [P1-2] mypy 16 模块豁免分批解除
- **问题**：`pyproject.toml:138-168` 豁免覆盖 API 层 ~60% 代码
- **证据**：`app.api.{data,config,suggestion,monitor,task,auth}` + sync 等
- **影响**：类型签名错误只能在运行期暴露
- **建议**：每迭代清 1-2 个模块，先易后难（`app.saihu.token` → `app.api.config` → ...）
- **工作量**：L（累积）

### [P1-18] 文件/函数行数 lint 规则
- **问题**：当前无文件/函数长度上限约束
- **证据**：`backend/pyproject.toml:79-97` ruff 配置
- **影响**：大文件持续生长（data.py 1002 行 / AppLayout.vue 716 行）
- **建议**：启用 ruff `PLR0915`（函数语句数）+ 自定义 pre-commit 检查文件行数
- **工作量**：S

---

## 3. 安全性

### [P0-1] backend 容器以 root 运行
- **问题**：`backend/Dockerfile` 无 `USER` 指令
- **证据**：`backend/Dockerfile`（容器以 root 运行）
- **影响**：容器逃逸时攻击者直接获得 root 权限
- **建议**：参考 `frontend/Dockerfile` 的非 root 8080 模式，添加 `USER appuser:appuser`
- **工作量**：S

### [P0-4] `/docs` 与 `/openapi.json` 生产默认关闭的路由仍被代理
- **问题**：`deploy/Caddyfile:43-49` 无条件代理 `/docs` `/openapi.json`，依赖 `APP_DOCS_ENABLED=false` 才禁用
- **证据**：`deploy/Caddyfile`
- **影响**：一旦环境变量配错，API 契约直接公网暴露
- **建议**：Caddyfile 对 `/docs*` 加内网 matcher，作为第二道防线
- **工作量**：S

### [P0-5] 密钥轮换无执行人 / 频率
- **问题**：runbook §3.4 有 JWT 轮换 SOP，但无周期性提醒 / 执行记录
- **证据**：`docs/runbook.md` §3.4
- **影响**：长期不轮换密钥一旦泄漏影响持续扩大
- **建议**：日历提醒 / CI 告警 + 在 `deployment.md` 记录最近轮换时间
- **工作量**：S

### [P0-6] CI 缺 SAST / SCA
- **问题**：当前 CI 只有 `pip-audit` + `npm audit`（依赖扫描），无源码 SAST、镜像 SCA
- **证据**：`.github/workflows/ci.yml`
- **影响**：常见 Web 漏洞（XSS / SSRF / 反序列化）无自动检出
- **建议**：加 `bandit -r backend/app` + `trivy image <tag>`（push GHCR 前）
- **工作量**：S

### [P0-7] `backend/.env` 曾被提交的痕迹
- **问题**：需确认 `.env` 历史版本是否包含真实凭证
- **证据**：git history 扫描待定
- **影响**：若泄漏过需立即轮换
- **建议**：`git log --all -- backend/.env` 核查；若命中立即轮换所有密钥
- **工作量**：S

### [P1-14] LOGIN_PASSWORD 强度校验
- **问题**：`config.py` 只要求非空，无长度 / 复杂度校验
- **证据**：`backend/app/config.py`
- **影响**：弱密码被暴力破解（即使 IP 锁定也可从多 IP 尝试）
- **建议**：Pydantic validator 要求 ≥ 12 字符 + 混合字符集
- **工作量**：S

### [P2-5] Caddyfile `/docs` 加内网 matcher
- 与 P0-4 合并解决
- **工作量**：S

### [P3-5] Vault / AWS Secrets Manager
- **问题**：当前密钥通过 `.env` 明文持有
- **建议**：若未来上云再评估
- **工作量**：L

---

## 4. 可测试性

### [P0-8] API 端点边界单测（见代码质量维度）

### [P1-7] 集成测试仅 3 个
- **问题**：`tests/integration/` 只有配置、metrics 快照、conftest 几个文件
- **证据**：`backend/tests/integration/`
- **影响**：跨模块回归漏检（如 sync → engine → suggestion 全链路）
- **建议**：补三条黄金路径：
  1. 订单同步 → 引擎计算 → 生成建议
  2. Worker 心跳超时 → Reaper 回收 → 失败标记
  3. `/readyz` 各状态完整性
- **工作量**：M

### [P1-11] 40001/40019 完整恢复链路 E2E
- **问题**：当前 `test_saihu_client.py` 只测 `_do_request`，不覆盖 `post()` 的重试外层逻辑
- **证据**：`backend/tests/unit/test_saihu_client.py`
- **影响**：token 刷新与重试叠加时的边界 case 无测试保护
- **建议**：mock Saihu 返回 40001 → 验证自动 `force_refresh` → 重试成功
- **工作量**：M

### [P2-4] 前端网络超时 case 缺失
- **问题**：`frontend/src/**/__tests__/` 无网络超时模拟
- **建议**：Vitest + msw 注入延迟响应
- **工作量**：M

### [P3-6] Playwright E2E 浏览器测试
- **问题**：完全无浏览器级测试
- **建议**：规模再扩时引入
- **工作量**：L

---

## 5. 可观测性

### [P1-5] engine 6 step 耗时日志 + Prometheus
- **问题**：`runner.py` 执行完整 6 步后只有一条成功日志
- **证据**：`backend/app/engine/runner.py`
- **影响**：某 step 慢无法定位
- **建议**：每 step 前后 `logger.info("engine_step_done", step=1, duration_ms=...)` + `engine_step_duration_seconds` histogram
- **工作量**：S

### [P1-6] Worker/Reaper Prometheus 指标
- **问题**：`/api/metrics/prometheus` 只有 task_run 状态分布 + Saihu 成功率
- **证据**：`backend/app/api/metrics.py:487-517`
- **影响**：worker 健康 / reaper 回收速率不可见
- **建议**：新增 `worker_leased_tasks_gauge` / `reaper_zombies_reaped_total` / `worker_heartbeat_age_seconds`
- **工作量**：S

### [P1-16] Reaper 回收时结构化告警
- **问题**：僵尸任务被回收时只普通 `logger.info`
- **证据**：`backend/app/tasks/reaper.py`
- **影响**：重要信号混在普通日志里
- **建议**：`logger.critical("reaper_zombie_reaped", task_ids=[...])` + 独立 counter
- **工作量**：S

### [P2-12] `/healthz` `/readyz` 响应缓存
- **问题**：高频探针每次都查 DB
- **建议**：1-2s TTL 缓存（不影响检测时效）
- **工作量**：S

### [P3-7] Grafana 仪表盘
- **问题**：prometheus 端点已有但无可视化
- **建议**：配套 `deploy/grafana/` 仪表盘定义
- **工作量**：M

---

## 6. 性能

### [P1-13] order_header 排序部分索引
- **问题**：按 `order_status` 复杂排序表达式无索引支持
- **证据**：`backend/app/api/data.py:149`
- **影响**：大批量订单排序慢
- **建议**：`CREATE INDEX ... ON order_header (order_status, purchase_date DESC) WHERE order_status != 'Canceled'`
- **工作量**：S

### [P2-3] Caddy ETag / 304
- **问题**：静态资源每次全量传
- **建议**：`@etag` matcher + `header Cache-Control "public, max-age=..."`
- **工作量**：S

### [P2-11] 前端 bundle 体积监控
- **问题**：vendor chunk 已分但无自动监控
- **建议**：`rollup-plugin-visualizer` + CI 阈值告警
- **工作量**：S

### [P2-18] vendor chunk 再细分
- **问题**：当前 element-plus / echarts / framework 三大块，ECharts 仍较大
- **建议**：按图表类型 lazy load
- **工作量**：S

### [P3-3] 前端虚拟滚动
- **问题**：本地分页 5000 条上限，未来订单同步全量时可能超过
- **建议**：数据量突破 10k 行后再评估 `@tanstack/vue-virtual`
- **工作量**：M

---

## 7. 可靠性 / 容错

### [P2-9] 死信队列 / 失败重放
- **问题**：task_run 失败后无统一重放入口
- **证据**：`backend/app/tasks/queue.py`
- **影响**：批量失败需手动 SQL 改状态
- **建议**：`POST /api/tasks/{id}/retry` 创建同 `payload` 新 TaskRun，保留原失败记录作审计
- **工作量**：L

### [P2-16] engine advisory lock 超时可配
- **问题**：`pg_advisory_xact_lock(7429001)` 阻塞无超时
- **证据**：`backend/app/engine/runner.py:58-61`
- **影响**：异常情况下后续引擎调用会堆积等待
- **建议**：改 `pg_try_advisory_xact_lock`，失败时立即抛 `ConflictError`
- **工作量**：S

### [P3-2] Celery 替代 TaskRun
- **问题**：当前自研队列功能够用但生态孤立
- **建议**：规模突破每秒百 task 再评估
- **工作量**：L

---

## 8. 部署与运维

### [P0-2] `deploy.sh` 迁移失败自动 restore_db
- **问题**：migration 失败需手工 `restore_db.sh`
- **证据**：`deploy/scripts/deploy.sh`
- **影响**：故障窗口延长 + 人为错误风险
- **建议**：`alembic upgrade head || bash restore_db.sh <latest-backup>`
- **工作量**：M

### [P2-10] migration downgrade 真实回跑测试
- **问题**：downgrade 实现完整但无自动化验证
- **建议**：CI 增加 `alembic downgrade -1 && alembic upgrade head` 步骤（独立测试库）
- **工作量**：M

### [P3-8] 多机部署
- **问题**：`pg_advisory_xact_lock` 限单 PG 实例
- **建议**：未来评估 Redis Redlock
- **工作量**：L

---

## 9. 数据层

### [P0-3] 审计日志无保留期策略
- **问题**：`api_call_log` / `login_attempt` 持续增长无清理
- **证据**：无相关 daily_archive 任务
- **影响**：表体积膨胀 + 合规风险（GDPR 式数据最小化）
- **建议**：按 `created_at < now() - interval '90 days'` 归档 / 删除（沿用 `daily_archive` job 模式）
- **工作量**：M

### [P2-1] `order_detail` 部分索引
- **问题**：邮编查询未命中索引
- **建议**：`CREATE INDEX ... WHERE postal_code IS NOT NULL`
- **工作量**：S

### [P2-2] `suggestion_item (suggestion_id, push_status)` 索引
- **问题**：推送失败重试时扫描慢
- **建议**：复合索引
- **工作量**：S

### [P2-14] `sync_state` 消费封装
- **问题**：`mark_sync_running/success/failed` 散落各 sync job
- **建议**：集中到 `app/sync/_state.py`，统一参数签名
- **工作量**：M

---

## 10. 可维护性

### [P1-3] `AppLayout.vue` 716 行拆子组件
- **问题**：整个应用导航树 + 布局状态一个文件
- **证据**：`frontend/src/components/AppLayout.vue`
- **建议**：拆 `NavGroup.vue` / `NavItem.vue` / `LayoutShell.vue`
- **工作量**：M

### [P1-10] ADR-5 实现漂移
- **问题**：架构蓝图 §8 ADR-5 说"所有列表页强制 PageSectionCard"，但 `SuggestionDetailView` 仍用 `el-card`
- **证据**：`frontend/src/views/SuggestionDetailView.vue`
- **影响**：文档与实现不同步，新人易混淆
- **建议**：两选一——要么迁移，要么更新 ADR-5 明确例外清单
- **工作量**：M

---

## 11. 前端 UX / DX

### [P1-8] 全局 error boundary
- **问题**：API 异常靠 axios 拦截器串联，无 UI 兜底
- **证据**：`frontend/src/api/client.ts`
- **影响**：未捕获异常白屏
- **建议**：Vue `errorCaptured` hook + 全局错误提示组件
- **工作量**：S

### [P2-7] `paginationMode` 字段标注
- **问题**：订单页服务端分页 vs 其他本地分页，差异未标注
- **建议**：`appPages.ts` 加 `paginationMode: 'local' | 'server'`
- **工作量**：S

### [P2-13] Monitor 页图表骨架屏
- **问题**：加载时图表区空白
- **建议**：`v-loading` + skeleton
- **工作量**：S

### [P2-17] `useAsyncState` 统一封装
- **问题**：各页面 `loading` / `error` / `data` 状态重复实现
- **建议**：composable 统一，替代裸 `ref(false)`
- **工作量**：M

### [P3-10] 英文 i18n
- **问题**：仅中文 UI
- **建议**：无海外用户需求则永不做
- **工作量**：L

---

## 12. CI / CD

### [P0-6] CI 加 SAST / SCA（见安全维度）

### [P2-15] rate_limit 可插拔（内存/Redis）
- **问题**：当前仅进程内限流，多实例重复计数
- **证据**：`backend/app/core/rate_limit.py`
- **建议**：抽象接口，保留内存默认 + 可选 Redis 后端
- **工作量**：M

---

## 13. 扩展性

### [P1-15] `navCategory` 改为 TS enum
- **问题**：`appPages.ts` 中 `navCategory` 为可选字符串
- **证据**：`frontend/src/config/appPages.ts`
- **建议**：改 `enum NavCategory` 强制编译期校验
- **工作量**：S

### [P1-17] PR / AGENTS.md 加 checklist 模板
- **问题**：Blueprint §9 有扩展叙述但无 checklist
- **建议**：`AGENTS.md` 附录 B/C 新增：
  - 新增数据页 checklist（后端端点 / API 客户端 / view / 路由 / 导航 / 测试 / 文档）
  - 新增后台任务 checklist（register / access.py / scheduler / 测试 / 文档）
- **工作量**：S

### [P2-6] engine step 扩展模板
- **问题**：新增 step 文档缺具体代码模板
- **建议**：`backend/app/engine/_template_step.py.example`
- **工作量**：S

---

## 14. 技术债

### [P1-9] legacy redirect 11 项无版本计划
- **问题**：`router/index.ts:41-70` 11 条历史路径重定向无"何时删除"标记
- **证据**：`frontend/src/router/index.ts`
- **建议**：加 `deprecated: 'v4.0'` 注释字段，配合 `CHANGELOG.md` 版本清理清单
- **工作量**：S

### [P1-12] `sidebar.ts` 响应性
- **问题**：`Set` + `watch({ deep: true })` 依赖框架实现细节
- **证据**：`frontend/src/stores/sidebar.ts`
- **建议**：改 `reactive({ expandedCategories: Record<string, boolean> })`
- **工作量**：S

---

## 15. 合规与隐私

### [P0-3] 审计日志保留期（见数据层）

### [P2-5] `/docs` 内网 matcher（见安全）

---

## 跨维度 / 未入 15 维但值得记录

### [P3-4] WebSocket 任务状态推送
- **问题**：当前前端 `TaskProgress` 轮询 `/api/tasks/{id}`
- **建议**：规模突破后改 WebSocket 推送
- **工作量**：M

### [P3-9] 前端 SSR / SSG
- **问题**：当前 SPA，无 SEO 需求
- **建议**：内部工具永不做
- **工作量**：L

---

## 附录：落地建议

**前两周 Sprint**（全部 P0）：
- Day 1–2：P0-1（非 root）+ P0-4（Caddy /docs matcher）+ P0-6（SAST/SCA）+ P0-7（.env 核查）
- Day 3–4：P0-5（密钥轮换记录）+ P0-8（API 单测）
- Day 5–7：P0-2（自动 restore_db）+ P0-3（审计日志归档）

**接下来 2 个月**：按 P1 工作量排：S 项（9 项）并行处理，M/L 项独立 spec。

**未触及的 P3**：每季度回顾一次，根据业务增长决定是否激活。

---

## 操作提示

- 单项 <1 天可直接 commit；需要 spec 的优先级阈值：M 以上 + 涉及架构变更
- P0 清单每项在修复后更新本文件为 `[P0-X ✅] ...`，保留历史记录
- 每季度（或需求节点）回看本 backlog，调整优先级或剔除已过时项
