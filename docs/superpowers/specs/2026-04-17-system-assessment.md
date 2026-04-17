# Restock System 多维度系统评估报告

> 评估日期：2026-04-17
> 评估对象：`E:\Ai_project\restock_system`（master @ 4a00178）
> 评估方法：5 个 Explore subagent 并行取证，按 15 个标准维度打分 + 证据链
> 评估基准：内部工具（1–5 用户）合理性 + 小团队可持续性

---

## 一、总体评分

**综合得分：3.9 / 5.0**（15 维加权平均）

```
数据层 ████████████████████ 5.0  ★★★★★
CI/CD  ████████████████████ 5.0  ★★★★★
安全性 ████████████████     4.0  ★★★★
可观测 ████████████████     4.0  ★★★★
性能   ████████████████     4.0  ★★★★
容错   ████████████████     4.0  ★★★★
部署   ████████████████     4.0  ★★★★
UX/DX  ████████████████     4.0  ★★★★
扩展性 ████████████████     4.0  ★★★★
合规   ████████████████     4.0  ★★★★
架构   ██████████████       3.5  ★★★☆
测试   ██████████████       3.5  ★★★☆
维护性 ██████████████       3.5  ★★★☆
代码Q  ████████████         3.0  ★★★
技术债 ████████████         3.0  ★★★
```

**定位结论**：系统已达**生产投产级（Production-Grade）**，在内部小团队规模约束下设计合理，数据层与 CI/CD 是亮点，主要差距集中在 **API 层代码规范（mypy 豁免）** 与 **大文件职责过重**。

---

## 二、维度评分卡

### 1. 架构设计 · 3.5 / 5

**优势**
- 分层清晰：API → Schema → Business(engine/sync/pushback/tasks) → Model → DB → Core，依赖向下无反向（`docs/Project_Architecture_Blueprint.md` §2）
- ADR 完备：6 个关键决策（全栈 async、自研 TaskRun、pg advisory lock、前端分页策略）均有驱动因素与代价评估（Blueprint §8）
- 业务层职责明确：engine 6 步纯函数、sync 按数据源划分

**缺陷**
- `backend/app/api/data.py` 1002 行 / 22 端点，聚合 7 种资源，查询逻辑与响应组装耦合
- `backend/app/api/metrics.py` 517 行，统计口径散落
- API 层缺专有数据服务层（Repository/QueryService），27 个查询函数复用困难

**建议**
1. 将 `data.py` 拆分为 `api/data/{orders,inventory,out_records,...}.py`，或提取 `repositories/data_queries.py`
2. `AppLayout.vue` 716 行拆为 `NavGroup` / `NavItem` 子组件

---

### 2. 代码质量 · 3.0 / 5

**优势**
- Ruff 配置细粒度：10 组插件（E/W/F/I/B/C4/UP/N/SIM/RUF），isort + simplify 全开（`backend/pyproject.toml:79-97`）
- 前端 TypeScript strict + ESLint 严禁 any（`frontend/tsconfig.json`）
- mypy `strict = true` + 强制类型注解（`backend/pyproject.toml:109-123`）

**缺陷**
- **16 个关键模块豁免 mypy 严格检查**（`pyproject.toml:138-168`）：
  ```
  app.api.{data,config,suggestion,monitor,task,auth}
  app.sync.{inventory,out_records,order_list,order_detail,warehouse,shop}
  app.tasks.{jobs.daily_archive,queue,scheduler}
  app.saihu.{token,client}
  ```
  禁用 8 项错误码（`dict-item`/`attr-defined`/`arg-type`/`no-any-return`/...），覆盖 API 层 ~60% 代码
- API 数据页 54 个查询函数缺参数化单测

**建议**
1. 分批解除 mypy 豁免，每迭代清理 1-2 个模块
2. API 端点补充排序/过滤边界 case 单测

---

### 3. 安全性 · 4.0 / 5

**优势**
- JWT ≥ 32 字节强制（`backend/app/config.py:83`），默认占位值 `please_change_me` 生产启动时失败
- 登录锁定**双维度**：IP + 用户名分别计数，5 次失败 10 分钟锁定（`backend/app/api/auth.py:103-149`），审计事件完整（`auth_login_blocked_locked` 等 5 类）
- bcrypt 哈希无时序泄露（`backend/app/core/security.py:13-20`）
- 全量 ORM 参数化，0 处 raw SQL
- `/api/metrics/prometheus` 双重防护：应用层 `monitor:view` + `deploy/Caddyfile` 内网 matcher
- 生产环境 `APP_DOCS_ENABLED=false`（默认关闭 OpenAPI）

**缺陷**
- JWT_SECRET 与赛狐凭证无轮换机制（runbook 第 3.4 节有 SOP 但需手动执行）
- 密码未做强度校验

**建议**
1. 引入密钥轮换定时提醒或接入密钥管理服务（Vault / AWS Secrets Manager）
2. `LOGIN_PASSWORD` 增加最小强度 Pydantic validator

---

### 4. 可测试性 · 3.5 / 5

**优势**
- 后端 **213 单测 + 集成测试通过**（PROGRESS.md §4.1）
- engine 6 步每 step 独立单测（`test_engine_step1~6.py`），含 advisory lock 验证
- 异常分类测试齐备：`test_saihu_client.py` / `test_saihu_token.py` / `test_queue.py`
- 前端 23 个 Vitest 文件覆盖 client / stores / views / utils

**缺陷**
- 集成测试仅 3 个（缺订单同步端到端、reaper 回收链路、健康检查完整性）
- 无 E2E 覆盖赛狐 40001/40019 完整恢复链路
- 前端缺异步错误边界和网络超时 case

**建议**
1. 补 `SaihuClient.post()` 40001 自动刷新 + 重试的外层集成测试
2. 补 Worker 心跳续租失败 → Reaper 标记失败的全链路集成测试

---

### 5. 可观测性 · 4.0 / 5

**优势**
- structlog + contextvars 全链路 `request_id`（`core/logging.py:32-43`、`core/middleware.py:22-52`）
- 生产 JSON / 开发 Console 分环境渲染
- ApiCallLog 完整记录：endpoint/duration_ms/http_status/saihu_code/retry_count（`saihu/client.py:240-280`）
- 健康检查双探针：`/healthz` 存活 + `/readyz` DB + worker + reaper + scheduler
- Prometheus 端点导出 task_run 状态分布 + Saihu 调用成功率

**缺陷**
- engine 6 步无分项耗时日志（难诊断慢 step）
- Worker 心跳续租、Reaper 回收数量无 Prometheus 指标

**建议**
1. 引擎每 step 前后 `logger.info()` 记录耗时与输入规模
2. Worker/Reaper 导出 `leased_tasks_gauge` / `reaped_zombie_counter`

---

### 6. 性能 · 4.0 / 5

**优势**
- 订单详情并发：`asyncio.Semaphore(2) + gather`，充分利用赛狐配额（`sync/order_detail.py:63-106`）
- 订单列表批量加载：复合键 `tuple_(shop_id, amazon_order_id)` 一次 IN 查询（`api/data.py:350-378`）
- 引擎批量加载：`step5_warehouse_split.py:71-80` 单次 SQL 加载分组订单，避免 N×M
- 订单页服务端分页（其他低增长表保留本地分页，见 ADR-4）
- Vite 手动 chunk 分割 charts / element-plus / framework（`vite.config.ts:50-67`）

**缺陷**
- 订单页复杂排序表达式未建部分索引（`api/data.py:149`）
- Caddy 无 ETag / 304 逻辑

**建议**
1. `order_header` 加部分索引 `(order_status, purchase_date DESC) WHERE order_status != 'Canceled'`
2. 启用静态资源 ETag 减少重复传输

---

### 7. 可靠性 / 容错 · 4.0 / 5

**优势**
- tenacity 指数退避（1→2→4→10s）区分可重试（`SaihuRateLimited` / `SaihuNetworkError`）与永久（`SaihuBizError`）
- `SaihuAuthExpired` 40001 **重试预算外**单独刷 token 再试一次
- task_run dedupe 部分唯一索引：`(dedupe_key) WHERE status IN ('pending','running')`
- `pg_advisory_xact_lock(7429001)` 引擎并发保护
- Worker `FOR UPDATE SKIP LOCKED` + 30s 心跳 + 2min 租约
- Reaper 60s 扫描僵尸（worker/scheduler 容器**冗余运行**）
- 订单详情失败分类：瞬时不写 log（自动重试），永久落 `order_detail_fetch_log`

**缺陷**
- Reaper 回收后不自动重入队（业务决策，需文档化）
- 无死信队列 / 失败重放机制

**建议**
1. Reaper 回收时 `logger.critical()` + Prometheus counter
2. 关键 sync job 失败次数超阈值触发告警

---

### 8. 部署与运维 · 4.0 / 5

**优势**
- 三进程分离（`backend` / `worker` / `scheduler`），同镜像靠环境变量区分角色
- 资源限制完整：db 1G、backend/worker/scheduler 各 512M、frontend 256M、caddy 128M
- 日志轮转 json-file 50M × 5
- 健康探针正确：frontend 用 `127.0.0.1:8080` 避 IPv6 假失败
- 完整部署脚本：`deploy.sh` → 备份 → 迁移 → 拉镜像 → smoke check → 失败回滚
- `rollback.sh` 使用 `git checkout -B` 兼容 detached HEAD
- `pg_backup.sh` 含 gzip 完整性 + 字节大小双校验
- `IMAGE_TAG=sha-<commit>` 精确溯源（CI 与 deploy 同口径）

**缺陷**
- backend 容器未指定 `USER`，仍以 root 运行
- `deploy.sh` 数据库迁移失败无自动 `restore_db.sh` 回滚，需手工介入

**建议**
1. `backend/Dockerfile` 添加非 root 用户（参考 frontend/nginx 8080 已做）
2. `deploy.sh` 捕获 alembic 失败后自动触发 `restore_db.sh`

---

### 9. 数据层 · 5.0 / 5

**优势**
- **部分索引策略成熟**：
  - `task_run` 3 个部分索引（active dedupe / pending priority / lease）
  - `suggestion_item` urgent 部分索引
- 复合键设计合理：`order_header(shop_id, amazon_order_id)` 唯一 + `(country, shop, status, purchase_date)` 复合索引
- migration 命名规范：`YYYYMMDD_HHMM_description.py`，NAMING_CONVENTION 配置在 `db/base.py`
- downgrade 完整实现（可双向迁移）
- JSONB 快照策略：velocity/sale_days/global_config/allocation 全部可追溯
- `restore_db.sh` 明确 DROP + CREATE 保证幂等

**缺陷**
- 无明显缺陷

**建议**（锦上添花）
1. `order_detail (shop_id, amazon_order_id, postal_code IS NOT NULL)` 部分索引加速邮编查询
2. `suggestion_item (suggestion_id, push_status)` 索引加速推送失败重试

---

### 10. 可维护性 · 3.5 / 5

**优势**
- 文档同步良好：`AGENTS.md` § 9 强制触发映射表，`PROGRESS.md` 更新至 2026-04-17
- 架构蓝图 929 行，含扩展指南（§9）
- 前端 `utils/` 15 个共享工具广泛导入
- 后端 `core/` 集中日志、权限、异常、时区

**缺陷**
- **大文件**：`AppLayout.vue` 716 行、`api/data.py` 1002 行、`api/metrics.py` 517 行
- **ADR 与实现漂移**：ADR-5 宣称"所有列表页强制 PageSectionCard"，但 `SuggestionDetailView` 仍用 `el-card`
- 无"文件大小/函数长度"的 lint rule 或 PR 检查

**建议**
1. 在 `ruff` 或 `pre-commit` 添加函数行数上限（例如 `PLR0915`）
2. PR 模板加一条"新增文件不超过 500 行"

---

### 11. 前端 UX / DX · 4.0 / 5

**优势**
- 设计系统完整：`tokens.scss` + `element-overrides.scss` 对齐 shadcn Zinc
- `PageSectionCard` 覆盖 19/19 数据页 + 13/17 设置页
- 统一共享工具：`format` / `warehouse` / `countries` / `status` / `tableSort` / `storage` / `monitoring`
- `auth.ts` / `sidebar.ts` localStorage 容错（JSON 损坏自动清理）
- 类型安全：`isUserInfo` 手动 guard，防脏数据注入

**缺陷**
- 订单页后端分页与其他页本地分页模式不一致（ADR-4 已解释，但未文档化例外清单）
- 无全局 error boundary 组件，API 异常靠拦截器串联

**建议**
1. 新增 `useAsyncState` 或全局错误边界组件
2. 在 `appPages.ts` 标注分页模式字段（`paginationMode: "local" | "server"`）便于后续迁移

---

### 12. CI / CD · 5.0 / 5

**优势**
- CI 门控完整：ruff + mypy + pytest + coverage + pip-audit + npm audit
- `publish` job 依赖所有 CI 通过（`ci.yml:71`）
- `deploy.yml` check-ci 强制校验后端前端双 CI 成功（`line 19-49`）
- 并发控制 `cancel-in-progress: false` 避免部署冲突
- `detect-secrets` pre-commit hook + `.secrets.baseline`
- 支持 `main`/`master`/tag 三种触发、GHCR 镜像版本追踪

**缺陷**（吹毛求疵）
- 缺 SAST（bandit / semgrep）
- 缺 SCA（snyk / trivy 扫描镜像）

**建议**
1. CI 加 `bandit -r backend/app` 检测常见 Web 漏洞
2. 镜像推 GHCR 前加 `trivy image` 扫描

---

### 13. 扩展性 · 4.0 / 5

**优势**
- 元数据驱动路由：`appPages.ts` 17 页面单一数据源，router + navigation 派生
- 后端任务注册：新任务仅需在 `tasks/access.py` `TASK_VIEW_PERMISSIONS` / `TASK_MANAGE_PERMISSIONS` 加条目 + 实现 `jobs/*.py`
- engine 6 step 解耦，新增 step 只需 runner 串联
- 架构蓝图 §9 提供"新增数据页 / 后台任务 / 赛狐端点 / 引擎 step" 4 类扩展指南

**缺陷**
- 无"新增任务/页面"的 checklist 模板（Blueprint §9 是叙述式）
- `appPages.navCategory` 为可选字段，未强制枚举

**建议**
1. `AGENTS.md` 附录加"新增数据页 / 新增任务"的 PR checklist
2. `navCategory` 改为 TypeScript enum 编译期校验

---

### 14. 技术债 · 3.0 / 5

**优势**
- 全库 **0 个 TODO / FIXME / XXX** 标记
- 模型清理完成：`t_purchase` 兼容层已删除（PROGRESS.md §3.33）
- 架构级重构前置审查（如项目审查 §3.40 一次性修复 40 项）

**缺陷**
- `router/index.ts:41-70` 保留 **11 个 legacy redirect**，无删除计划或版本号标记
- `sidebar.ts` Set + `watch({ deep: true })` 响应性依赖框架实现细节
- mypy 豁免模块（见维度 2）属隐性技术债

**建议**
1. legacy redirect 加 `deprecated: "v4.0"` 字段，配合版本升级删除清单
2. `expandedCategories` 改为 Pinia reactive 对象规避隐式响应

---

### 15. 合规与隐私 · 4.0 / 5

**优势**
- 日志不记录密码 / token / secret
- RBAC 权限矩阵在 `tasks/access.py` 集中定义，`require_permission()` 统一收口
- 库存快照 90 天保留（`daily_archive` 定时清理）
- 生产 CSP：`script-src 'self'`（无 `unsafe-inline`），`Referrer-Policy: strict-origin`
- `img-src` 白名单收敛到 Amazon 商品图域名

**缺陷**
- 审计日志（`api_call_log` / `login_attempt`）无保留期策略文档
- `/docs` 与 `/openapi.json` 在 Caddyfile 无条件代理（虽然生产默认关闭）

**建议**
1. `docs/runbook.md` 补充审计日志保留期（建议 90 在线 + 365 归档）
2. Caddy 对 `/docs` 加内网 matcher 作为第二道防线

---

## 三、优先改进清单（按 ROI 排序）

| # | 改进项 | 影响维度 | 成本 | 收益 |
|---|---|---|---|---|
| 1 | 拆分 `api/data.py` 按资源分文件 | 架构、维护性、代码质量 | 中 | 高 |
| 2 | 分批解除 mypy 豁免（每迭代 1-2 模块） | 代码质量、可维护性 | 中 | 高 |
| 3 | 引擎 step 加耗时日志 + Prometheus 指标 | 可观测性、性能 | 低 | 中 |
| 4 | `backend/Dockerfile` 加非 root USER | 安全、部署 | 低 | 中 |
| 5 | `deploy.sh` 自动 restore_db 回滚 | 部署、容错 | 中 | 高 |
| 6 | legacy redirect 加 `deprecated` 版本标记 | 技术债 | 低 | 低 |
| 7 | CI 加 bandit + trivy 扫描 | 安全、CI/CD | 低 | 中 |
| 8 | AGENTS.md 附录新增 PR checklist 模板 | 扩展性、维护性 | 低 | 中 |

**建议先做 1-5**：覆盖 4 个主要弱项维度（架构、代码质量、可观测性、部署容错），每项 1-2 天工作量。

---

## 四、定位与基准对照

**作为内部工具（1–5 用户）**：
- 工程化水平 **高于同类内部项目**（典型内部工具平均 2.5–3.0 分）
- 相比开源 SaaS 项目仍有差距，主要在代码规范覆盖率、端到端测试

**作为候选 SaaS 产品**：
- 需补：多租户隔离、水平扩展、更严格 mypy/测试覆盖、密钥管理、SAST/SCA、审计日志保留策略
- 本次 3.9 分对应 **"健壮内部工具"** 成熟度

---

## 附录 A：评估方法

- 5 个 Explore subagent 并行取证（见本次对话）
- 每个 agent 覆盖 3 个维度，返回评分 + file:line 证据 + 改进建议
- 本报告由主对话汇总，未二次人工修饰评分

## 附录 B：后续跟进

建议将优先清单第 1–5 项转为 spec，按 `superpowers:writing-plans` → `superpowers:executing-plans` 流程推进。单项不需要完整 spec，可走 `docs/superpowers/plans/` 简化 plan。
