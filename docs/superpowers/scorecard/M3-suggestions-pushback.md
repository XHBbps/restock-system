# M3 建议单与推送 评分

> 评估日期：2026-04-11
> 评估人：subagent (claude-sonnet-4-6)
> 范围：建议单 CRUD/状态流转 + 采购单推送回赛狐
> 主战场维度：D1 / D6
> 横向参照：M1 赛狐集成（2.63/4，封板）、M2 补货引擎（2.71/4，封板）

---

## 1. 证据采集摘要

### 1.1 阅读的文件

| 文件 | 行数 |
|---|---|
| `backend/app/api/suggestion.py` | 397 行 |
| `backend/app/pushback/purchase.py` | 182 行 |
| `backend/app/pushback/__init__.py` | 1 行（空） |
| `backend/app/schemas/suggestion.py` | 77 行 |
| `backend/app/models/suggestion.py` | 115 行 |
| `backend/tests/unit/test_suggestion_patch.py` | 131 行 |
| `backend/tests/unit/test_pushback_purchase.py` | 260 行 |
| `docs/Project_Architecture_Blueprint.md`（相关段落） | — |

### 1.2 测试运行结果

```
17 passed, 136 deselected in 1.06s
```

M3 专属：
- `test_pushback_purchase.py`：7 个测试全 pass（success path, blocker raises, failure writes error, empty payload, refresh counts ×3）
- `test_suggestion_patch.py`：7 个测试全 pass（archived rejected, pushed rejected, sum mismatch, missing t_purchase, missing t_ship, invalid date, clears allocation snapshot）

全库：153 passed，0 failed。

### 1.3 关键 grep 结果摘录

- **状态机**：`backend/app/models/suggestion.py:29-31` — CheckConstraint `status IN ('draft','partial','pushed','archived','error')`；`suggestion_item:64-66` — CheckConstraint `push_status IN ('pending','pushed','push_failed','blocked')`。`_refresh_suggestion_counts` 将状态收敛到 draft/partial/pushed 三态。**`error` 状态在 DB 约束里定义，但全库任何代码路径均未将 suggestion.status 写为 `"error"`。**

- **推送 dedupe**：`backend/app/api/suggestion.py:303` — `dedupe_key=f"push_saihu#{suggestion_id}"`。任务队列的唯一约束确保同一 suggestion 只有一个 pending/running 推送任务。

- **鉴权**：所有 6 个端点均使用 `Depends(get_current_session)`（`suggestion.py:92,129,148,164,268,313`），全部要求 JWT 认证。

- **JSONB 不可变保护**：API PATCH 层通过 `item.push_status == "pushed"` 判断拒绝编辑（`suggestion.py:185-186`）。但 push 端点（`suggestion.py:263-306`）不检查 `sug.status` 是否为 `archived` 或 `pushed`，可对已归档/已完全推送建议单重新入队推送任务。无 DB 级 immutable 约束（与 M2 一致）。

- **H4 一致性校验**：`suggestion.py:199-205` — 仅当 `total_qty` 和 `country_breakdown` 同时提交时校验两者之和相等，否则跳过；有单测守护（`test_suggestion_patch_sum_mismatch_rejected`）。

- **速率限制**：全 backend 无入口级速率限制（slowapi/throttle 均未引入）。仅赛狐出站调用有 `aiolimiter`（M1 范围）。**推送端点无限流保护。**

- **推送审计**：`purchase.py:100` — `logger.exception("push_saihu_failed", suggestion_id=suggestion_id, error=last_error)` 仅失败路径。成功路径无专门的审计日志记录"谁在何时推送了哪个 suggestion"（worker 执行日志写到 `task_run.error_msg`，但无 operator/session 关联）。

- **批量推送**：`push_items()` 接收 `PushRequest.item_ids: list[int]`（`schemas/suggestion.py:77`，`min_length=1`），无上限约束。服务端在 `SuggestionItem.id.in_(req.item_ids)` 单次 IN 查询取全部条目（`suggestion.py:279-287`），无 N+1。

---

## 2. 维度评分

### D1 功能完整性

- **得分**：3/4
- **判据匹配**：满足 Rubric 3 级——主链路端到端跑通（list/detail/patch/push/archive 全实现），边界场景已处理（archived 拒绝编辑、push_blocker 拒绝推送、H4 一致性校验、H3 urgent 重算、missing_timing_countries 校验、部分条目不存在返回 404），`_refresh_suggestion_counts` 正确驱动 draft→partial→pushed 三态升级。未满足 4 级：无集成测试守护端到端 DB 路径（list/detail/archive 端点零单测）；`error` 状态在 CheckConstraint 定义但全代码库无任何写入路径（孤立状态值，spec 意图未落地）；push 端点未拒绝对 `archived`/`pushed` 建议单重新推送（状态机未封闭）。**对照 M1=[3], M2=[3] 的标尺**，M3 主链路同样完整，边界场景同样覆盖，但 `error` 状态孤立和 push-on-archived 是比 M1/M2 更明显的状态机缺口，仍评 3（差距已记录）。
- **支撑证据**：
  - `backend/app/api/suggestion.py:172-173` — archived 拒绝编辑
  - `backend/app/api/suggestion.py:185-186` — 已推送条目拒绝编辑
  - `backend/app/api/suggestion.py:291-296` — push_blocker 拒绝推送
  - `backend/app/api/suggestion.py:299-305` — 入队 push_saihu 任务
  - `backend/app/pushback/purchase.py:150-182` — `_refresh_suggestion_counts` 驱动 draft/partial/pushed
  - `backend/app/models/suggestion.py:29-31` — CheckConstraint 含 `error` 状态
  - 全库搜索 `"'error'"` 仅命中 CheckConstraint，无写入路径
  - `backend/app/api/suggestion.py:263-306` — push_items 无 sug.status 前置校验
- **未达上一级的差距**：
  1. list/detail/archive 端点无单测（缺集成/契约测试守护）
  2. `error` 状态孤立：定义了但无代码写入，已确认为 dead spec（见 §7 #1），列入打分后清理待办
  3. ~~push 端点未拦截 archived 建议单~~ — **已在审计阶段修复**（见 §7 #2）
- **疑点**：✅ 已澄清（见 §7 #1 / #2）——`error` 是 dead spec（用户选 A 方案删除），push-on-archived 是遗漏（已在审计中即时修复）。

---

### D2 代码质量

- **得分**：2/4
- **判据匹配**：满足 Rubric 2 级——lint+format 通过（全库 153 passed），核心路径有单测覆盖：PATCH 的 7 个测试覆盖所有校验分支，pushback 的 7 个核心测试覆盖 success/blocker/failure/empty payload/refresh counts 三态。未满足 3 级：list/detail/archive 端点无任何单测（三个端点 0 覆盖），整体覆盖率约 60%（低于 70% 门槛）；`SuggestionOut`/`SuggestionDetailOut` 中 JSONB 字段类型宽泛（`dict[str, Any]`），country_breakdown 无字段级 Pydantic schema 约束（输入端 `SuggestionItemPatch` 的 `country_breakdown: dict[str, int]` 有类型约束，但输出端 `SuggestionItemOut` 为 `dict[str, Any]`）。**对照 M1=[2], M2=[3] 的标尺**，M3 覆盖率和分层清晰度接近 M1（核心函数有测试但整体覆盖不足），评 2。
- **支撑证据**：
  - `backend/tests/unit/test_suggestion_patch.py:66-131` — 7 个 PATCH 单测
  - `backend/tests/unit/test_pushback_purchase.py:116-260` — 7 个 pushback 单测
  - `backend/app/schemas/suggestion.py:37` — `country_breakdown: dict[str, Any]`（输出端宽泛）
  - `backend/app/schemas/suggestion.py:64-72` — `SuggestionItemPatch.country_breakdown: dict[str, int]`（输入端有约束）
  - list/detail/archive 端点（suggestion.py:81-327）无对应测试文件
- **未达上一级的差距**：
  1. list/detail/archive 端点 0 单测，覆盖率 < 70%
  2. 输出 schema JSONB 字段宽泛，无结构化约束
- **疑点**：无

---

### D3 安全性 ⚠️

- **得分**：2/4
- **判据匹配**：满足 Rubric 2 级——所有 6 个端点均有 `Depends(get_current_session)` JWT 认证（`suggestion.py:92,129,148,164,268,313`）；POST/PATCH 入参全走 Pydantic 校验（`SuggestionItemPatch` + `PushRequest`）；`country_breakdown` 值级别有非负校验（`suggestion.py:189-197`）。未满足 3 级：（1）全 backend 无入口级速率限制——推送端点可被重复轰炸（与 M1/M2 共性问题）；（2）push 端点无状态前置校验，已归档建议单可被重新推送（越权操作门槛低）；（3）无推送操作审计日志（无法溯源"谁推送了什么"）；（4）无 CVE 扫描；（5）无安全 headers/CSRF 配置（共性）。**对照 M1=[2], M2=[2] 的标尺**，共性问题（速率限制/CVE/安全 headers）完全一致；M3 还有 push-on-archived 这一独有缺口，但不改变级别，评 2。
- **支撑证据**：
  - `backend/app/api/suggestion.py:268,313` — push 和 archive 端点有 JWT
  - `backend/app/api/suggestion.py:263-306` — push 端点无 sug.status 前置校验（archived 可被推送）
  - `backend/app/schemas/suggestion.py:74-77` — `PushRequest.item_ids` Pydantic 校验
  - 全库 grep `rate_limit|throttle|slowapi` 仅命中 saihu 出站限流，无入口级限流
  - `purchase.py:100` — 失败日志无 operator/session 字段
- **未达上一级的差距**：
  1. 无入口级速率限制（全 backend 共性）
  2. ~~push 端点未拦截 archived 状态~~ — **已在审计阶段修复**（见 §7 #2）
  3. ~~无推送操作 audit log~~ — 用户已确认 1-5 人内部工具不需要（见 §7 #3）
  4. 无 CVE 扫描（共性）
- **疑点**：✅ 已澄清（见 §7 #2）——push-on-archived 已即时修复

---

### D4 可部署性

- **得分**：3/4
- **判据匹配**：（M3 D4 在第二轮 review 中由用户决定**不再标 N/A**——理由：项目需要部署到云服务器，每个模块都应为自己的可部署性负责，详见 §8 #6）
  - ✅ 满足 Rubric 2 级：docker-compose 一键启动（M3 共享 backend 容器）；`.env.example:55-56` 文档化 `PUSH_AUTO_RETRY_TIMES`/`PUSH_MAX_ITEMS_PER_BATCH`；`suggestion`+`suggestion_item` 表已在 initial migration 创建；共享 `/readyz` 健康检查涵盖。
  - ✅ 满足 Rubric 3 级：`deploy/scripts/deploy.sh` 一键部署脚本完整流程；`validate_settings()`（`config.py:72-94`）启动时校验关键密钥；共享 docker-compose `deploy.resources.limits.memory` 资源限制。
  - ❌ 未满足 Rubric 4 级：无 CI/CD pipeline、无 IaC（Terraform）、无蓝绿/滚动部署、无多环境（dev/staging/prod）、无部署后自动 smoke test。
- **支撑证据**：
  - `backend/.env.example:55-56` — `PUSH_AUTO_RETRY_TIMES=3` / `PUSH_MAX_ITEMS_PER_BATCH=50`
  - `backend/app/config.py:57-58` — Settings 字段定义
  - `backend/app/config.py:72-94` — `validate_settings()` 启动校验
  - `deploy/scripts/deploy.sh` — 一键部署脚本
  - `backend/alembic/versions/20260408_1500_initial.py` — `suggestion`/`suggestion_item` 表迁移
- **未达上一级的差距**：
  1. 无 CI/CD pipeline（与所有模块共性）
  2. 无 IaC、蓝绿部署、多环境（共性）
  3. **M3 独有**：`PUSH_MAX_ITEMS_PER_BATCH` 是 dead config（定义但全代码库无引用），见 P2-5
  4. **M3 独有**：`push_auto_retry_times` 不在 `validate_settings` 检查范围（设 0/负数会导致 tenacity 异常），见 P2-6
- **对照 M1=[3]，M2 retroactive 同步评 [3] 的标尺**，M3 同样满足 3 级（共享部署基础设施 + 一键脚本 + 配置校验 + 资源限制），未达 4 级缺 CI/CD，与 M1 持平评 3。
- **疑点**：无

---

### D5 可观测性

- **得分**：3/4
- **判据匹配**：满足 Rubric 3 级——structlog 结构化日志（`purchase.py:31` — `get_logger(__name__)`）；`ctx.progress()` 3 次调用含步骤名和数量（`purchase.py:42,71,102,145`）；推送失败有 `logger.exception("push_saihu_failed", suggestion_id=..., error=...)` 结构化字段（`purchase.py:100`）；`push_attempt_count` 字段记录重试次数（model `suggestion_item:104`）；`push_error` 字段持久化失败原因（model:103）；`pushed_at` 记录时间戳（model:105）；`saihu_po_number` 追踪采购单号。未满足 4 级：无 OpenTelemetry，无 /metrics 暴露推送成功率指标，无专门推送操作 audit log 含 operator 信息。**对照 M1=[3], M2=[3] 的标尺**，结构化日志+任务进度追踪+字段级追溯均满足 3 级，评 3。
- **支撑证据**：
  - `backend/app/pushback/purchase.py:42` — `ctx.progress(total_steps=3)`
  - `backend/app/pushback/purchase.py:100` — `logger.exception("push_saihu_failed", suggestion_id=..., error=...)`
  - `backend/app/models/suggestion.py:103-105` — `push_error`, `push_attempt_count`, `pushed_at`
- **未达上一级的差距**：
  1. 无 /metrics 端点暴露推送成功率聚合统计
  2. 无 OpenTelemetry 跨服务追踪
  3. audit log 不含 operator（谁触发推送不可查）
- **疑点**：无

---

### D6 可靠性 ⚠️ 主战场

- **得分**：3/4
- **判据匹配**：满足 Rubric 3 级——（1）**dedupe 防并发重入**：`dedupe_key="push_saihu#{suggestion_id}"`（`suggestion.py:303`），任务队列唯一约束确保同一 suggestion 只有一个活跃推送任务；（2）**tenacity 指数退避重试**：`wait_exponential(min=1, max=10)`，仅对 `SaihuRateLimited` + `SaihuNetworkError` 重试，`SaihuAPIError` 不重试（永久/瞬态分类明确，`purchase.py:84-97`）；（3）**重试次数可配置**：`settings.push_auto_retry_times`（`config.py:57`，默认 3）；（4）**两阶段提交**：item 状态更新 `db.commit()` 后，再执行 `_refresh_suggestion_counts` + 第二次 `db.commit()`（`purchase.py:134,138`），事务边界清晰；（5）**push_attempt_count 幂等计数**：无论成败都递增（`purchase.py:122,132`）；（6）**push_blocker 双重校验**：API 层（`suggestion.py:291`）+ Job 层（`purchase.py:67`）均有校验。未满足 4 级：（1）无 DB 级 JSONB 不可变约束（仅代码层 `push_status=pushed` 拒绝编辑，无 trigger 或 generated column 约束）；（2）push 端点未拦截 `archived` 建议单，可对归档建议单触发重新推送（job 层会成功执行）；（3）`error` 状态孤立，推送彻底失败后 suggestion.status 停留在 `draft/partial`，无 `error` 聚合状态；（4）无熔断器，无死信队列，无 chaos test（与 M1/M2 一致）。**对照 M1=[3], M2=[3] 的标尺**，M3 的 dedupe+重试+事务边界达到 3 级；push-on-archived 和 error-orphan 是比 M1/M2 更具体的状态机问题，但不降到 2 级，评 3。
- **支撑证据**：
  - `backend/app/api/suggestion.py:303` — `dedupe_key=f"push_saihu#{suggestion_id}"`
  - `backend/app/pushback/purchase.py:84-97` — tenacity AsyncRetrying + 永久/瞬态分类
  - `backend/app/pushback/purchase.py:111-138` — 两阶段 commit
  - `backend/app/pushback/purchase.py:67` — Job 层二次 push_blocker 校验
  - `backend/app/models/suggestion.py:94-95` — JSONB 快照字段无 immutable 约束
  - `backend/app/api/suggestion.py:263-306` — push_items 无 sug.status 前置校验
  - 全库无 `"'error'"` 写入路径
- **未达上一级的差距**：
  1. JSONB 不可变无 DB 约束（与 M2 一致）
  2. ~~push 端点不拦截 archived 建议单~~ — **已在审计阶段修复**（见 §7 #2），状态机已封闭
  3. `error` 状态孤立 — 已确认为 dead spec，将在打分后清理（见 §7 #1）
  4. 无熔断器/死信队列/chaos test（共性）
- **疑点**：✅ 已澄清——`error` 状态删除后失败语义统一在 item 层（push_status='push_failed'）+ partial 头表状态，已经够用

---

### D7 可维护性

- **得分**：3/4
- **判据匹配**：满足 Rubric 3 级——（1）`purchase.py` 文件头有 FR 编号引用（FR-027/045/046）和策略描述；（2）AGENTS.md/CLAUDE.md 明确禁止修改已推送 country_breakdown（`docs/Project_Architecture_Blueprint.md:723`）；（3）架构蓝图完整文档化推送数据流（`blueprint:422-453`）和 ADR-6（in-transit 去重设计）；（4）注释覆盖非显然逻辑（`suggestion.py:166` N1 注释、`suggestion.py:199` H4 注释、`suggestion.py:331-337` _build_detail N+1 防护注释）；（5）模块边界清晰（API 层 → pushback 层 → saihu 端点层）。未满足 4 级：无专门的状态机图（状态转换未在文档中以图形方式说明，仅在约束和注释中分散呈现）；无 ADR 文档记录 push-on-archived 不拦截的设计决定；无自动化文档生成。**对照 M1=[3], M2=[3] 的标尺**，M3 文档完整性和注释密度相当，评 3。
- **支撑证据**：
  - `backend/app/pushback/purchase.py:1-8` — 文件头策略说明含 FR 编号
  - `backend/app/api/suggestion.py:166,199,331-337` — 关键逻辑注释
  - `docs/Project_Architecture_Blueprint.md:422-453` — 推送数据流文档
  - `docs/Project_Architecture_Blueprint.md:723` — 不可变规则文档
  - `docs/Project_Architecture_Blueprint.md:660-663` — ADR-6 in-transit 去重
- **未达上一级的差距**：
  1. 无状态机图（draft→partial→pushed→archived 转换路径未图形化）
  2. push-on-archived 未在设计文档中明确说明是有意为之还是遗漏
  3. 无 ADR，无自动化文档生成
- **疑点**：无

---

### D8 性能与容量

- **得分**：2/4
- **判据匹配**：满足 Rubric 2 级——（1）`_build_detail` 明确批量加载 product_listing 防 N+1（`suggestion.py:331-337` 有注释，`suggestion.py:351-366` 一次 IN 查询取所有 sku 的 name/image）；（2）建议单列表有 `ix_suggestion_status` + `ix_suggestion_created_at` 双索引（`model:33-34`）；（3）suggestion_item 有 `ix_suggestion_item_suggestion` + `ix_suggestion_item_urgent` 索引（`model:68-74`）；（4）`_refresh_suggestion_counts` 单次查询取所有 status，Python 汇总（无 N+1，`purchase.py:150-165`）。未满足 3 级：无 SLO 定义，无推送超时配置（tenacity 未设置 timeout 参数），`_refresh_suggestion_counts` 用 Python 汇总而非 SQL GROUP BY（规模小时无影响，但不是最优），无容量评估文档，无慢查询日志。**对照 M1=[2], M2=[2] 的标尺**，M3 索引覆盖主查询、无 N+1，但无 SLO/超时/容量文档，评 2。
- **支撑证据**：
  - `backend/app/api/suggestion.py:331-337` — N+1 防护注释
  - `backend/app/api/suggestion.py:351-366` — 批量 IN 查询 product_listing
  - `backend/app/models/suggestion.py:33-34,68-74` — 关键索引
  - `backend/app/pushback/purchase.py:84-97` — tenacity 无 timeout 参数
  - `backend/app/pushback/purchase.py:150-165` — Python 汇总（非 SQL GROUP BY）
- **未达上一级的差距**：
  1. 无推送超时配置（长时间赛狐 API 无响应无法中断）
  2. 无 SLO 定义
  3. `_refresh_suggestion_counts` 全量 Python 汇总（建议单条目大时有内存开销）
  4. 无容量评估文档
- **疑点**：无

---

### D9 用户体验 ◦

- **得分**：2/4
- **评估**（低权重，主要在 M5）：推送失败错误消息分类层次清晰——`PushBlockedError`（带 `detail.blocked_item_ids`）、`NotFound`（条目不存在）、`SaihuAPIError`（含 code + message 格式化为 `"code: message"`）；`push_error` 字段持久化到 suggestion_item，前端可展示。但推送成功响应仅返回 `{"task_id": ..., "existing": ...}`，无建议单整体状态摘要；无错误码枚举（错误码仅为赛狐原始 code 字符串拼接，无本地分类映射）。**对照 M1/M2 均 N/A，M3 是首个评 D9 的模块**，2 分（基础错误分类和持久化到位，但无结构化错误码体系）。
- **支撑证据**：
  - `backend/app/api/suggestion.py:291-296` — PushBlockedError 含结构化 detail
  - `backend/app/pushback/purchase.py:98-100` — SaihuAPIError code+message 格式化
  - `backend/app/models/suggestion.py:103` — push_error Text 字段持久化
  - `backend/app/schemas/suggestion.py:74-77` — PushRequest 响应无建议单状态摘要

---

## 3. 模块得分

- **各维度分数**：D1=3 D2=2 D3=2 D4=3 D5=3 D6=3 D7=3 D8=2 D9=2
- **平均分（9 维度，无 N/A，第二轮 review 后）**：(3+2+2+3+3+3+3+2+2) / 9 = **23 / 9 ≈ 2.56 / 4**
- **主战场维度**：D1=3 D6=3
- **变更说明**：第一轮 review 平均分为 8 维度的 2.50（D4 标 N/A）；第二轮 review 用户决定 D4 不再标 N/A（理由见 §8 #6），重新评估 D4=3，平均分变为 9 维度的 2.56

---

## 4. 本模块发现的关键问题

### 🔴 P0 阻塞

无

### 🟡 P1 强烈建议

（M3 原本有 3 项 P1，全部在第一轮 review 中处理：1 项即时修复，2 项被用户判定为非问题；剩余 0 项 P1）

### 🟢 P2 可延后

1. **`_refresh_suggestion_counts` 用 Python 汇总**：当前全量加载 suggestion_item.push_status 到 Python 再 count，建议改为 `SELECT push_status, COUNT(*) FROM suggestion_item WHERE suggestion_id=? GROUP BY push_status` 减少数据传输。文件：`purchase.py:150-165`
2. **输出 schema JSONB 字段宽泛**：`SuggestionItemOut.country_breakdown: dict[str, Any]` 缺少结构化约束，建议考虑 `dict[str, int]` 或专用 VO 类型。文件：`schemas/suggestion.py:37`
3. **推送无超时配置**：tenacity `AsyncRetrying` 未设 `timeout` 参数，赛狐 API 长时间无响应不会自动中断。建议加 `stop=stop_after_attempt(3) | stop_after_delay(60)` 或等效配置。文件：`purchase.py:84`
4. **清理 `error` 状态 dead spec** ｜ 用户已选 A 方案
   - 现状：`suggestion.status` 的 `error` 值在 CheckConstraint 与排序映射定义，但全代码库无写入路径，是 over-design 遗留；当前失败语义全部通过 item 级 `push_status='push_failed'` + 头表 `partial` 表达，已经够用
   - 修复动作（用户已选 A 方案）：
     - 写一条 Alembic migration 修改 CheckConstraint 删除 `'error'`
     - 删除 `models/suggestion.py:30` CheckConstraint 中的 `error`
     - 删除 `api/suggestion.py:40` `SUGGESTION_STATUS_SORT_ORDER` 中的 `"error": 4`
     - 同步更新 `specs/001-saihu-replenishment/data-model.md:319` 文档
   - 类型：清洁度提升，零业务影响，列入打分后的待办

5. **`PUSH_MAX_ITEMS_PER_BATCH` 是 dead config** ｜ 第二轮 review 发现
   - 现状：`backend/app/config.py:58` 定义 `push_max_items_per_batch: int = 50`，`.env.example:56` 也有 `PUSH_MAX_ITEMS_PER_BATCH=50`，但**全代码库 grep 只在 config.py 自身命中**
   - 历史背景：根据 PROGRESS.md 第 3.6 节"全选跨页保持 + 推送上限放宽（原 50 条上限已移除）"，这是早期批量推送上限，业务逻辑里已经被移除，但配置项忘记同步删除
   - 修复动作：删除 `config.py:58` 和 `.env.example:56` 的 `PUSH_MAX_ITEMS_PER_BATCH`
   - 类型：清洁度提升，列入打分后的待办

6. **`push_auto_retry_times` 缺少 `validate_settings` 校验** ｜ 第二轮 review 发现
   - 现状：`config.py:57` 默认值 3，但 `validate_settings()`（`config.py:72-94`）不校验值的合法性（0 或负数会导致 tenacity `stop_after_attempt` 配置异常）
   - 修复动作：在 `validate_settings` 中添加 `if settings.push_auto_retry_times < 1: errors.append("PUSH_AUTO_RETRY_TIMES must be >= 1")`
   - 类型：防御性配置校验，列入打分后的待办

---

## 5. 与 M1 / M2 共性 / 差异问题

- **共性**：
  - 无入口级速率限制（M1/M2/M3 共性，P1 级别）
  - 无 CVE 扫描（共性）
  - 无安全 headers/CSRF 配置（共性）
  - JSONB 快照无 DB 级 immutable 约束（M2/M3 共性）
  - 无 OpenTelemetry（共性）
  - 无 ADR 文档（共性）
  - 无死信队列/熔断器/chaos test（共性）

- **M3 独有**：
  - ~~push-on-archived 未拦截~~ — **审计阶段已修复**（一行代码 + 2 个单测，全 156 测试通过）
  - `error` 状态孤立 — 用户已选 A 方案，列入打分后清理 P2
  - D9 首次有实际内容（push 错误分类和持久化），用户确认对小团队足够

---

## 6. P0/P1 候选清单交叉判定

### P0-2 公网假设覆盖（推送鉴权 + 参数校验）

- **判定**：✅ 已实现（审计阶段修复后）
- **证据**：
  - ✅ 所有端点均有 JWT 认证（`Depends(get_current_session)` × 6）
  - ✅ POST/PATCH 入参全走 Pydantic 校验
  - ✅ country_breakdown 值非负校验
  - ✅ push 端点状态前置校验已加（`suggestion.py:274-275`，审计阶段修复）
  - ✅ 操作人 audit log 用户确认 1-5 人内部工具不需要
- **结论**：经审计阶段一次即时修复后（push-on-archived），推送端点的鉴权与基础校验链路完整，公网暴露下的 P0-2 候选已实现

### P1-1 公网入口缺乏速率限制

- **判定**：❌ 未实现
- **证据**：全库 grep `rate_limit|throttle|slowapi` 仅命中 M1 范围的赛狐出站限流（`saihu/client.py:35`），无入口级限流
- **结论**：与 M1/M2 一致，推送端点可被重复轰炸。P1 优先级，建议引入 slowapi 对 /push 端点限流

---

## 7. 给用户的确认问题

✅ 全部 5 个疑点在第一轮 review 中已由用户澄清，详见 §8 用户澄清记录。

---

## 8. 用户澄清记录（2026-04-11 第一轮 review）

### #1 `error` 状态设计意图
- **疑问**：CheckConstraint 定义但全库无写入路径，是 spec 遗留还是有意放弃？
- **调查**：Claude 主控对全代码库做了 grep 验证：
  - `'error'` 在 suggestion.status 上下文里**仅在 CheckConstraint 出现**，无任何代码路径写入
  - 失败语义全部在 item 级（`suggestion_item.push_status='push_failed'`）
  - `_refresh_suggestion_counts` 把头表收敛为 draft/partial/pushed 三态
  - **spec narrative**（`specs/001-saihu-replenishment/spec.md:276`）只列了 4 个状态："suggestion: status (draft/partial/pushed/archived)"
  - **data-model.md**（`specs/001-saihu-replenishment/data-model.md:319`）的 SQL DDL 加了 `error`，与 narrative 不一致
- **结论**：`error` 是 over-design 遗留（dead spec）——某次设计时预留但实际实现选择了 item 级失败语义
- **用户决策**：选 **A 方案 — 删除 dead spec**
- **影响**：新增 P2-4 项（清理待办，审计阶段不执行代码改动）；D1 / D6 评分不变

### #2 push-on-archived 是否有意为之
- **疑问**：push 端点不拦截 archived 是设计意图还是遗漏？
- **调查**：Claude 主控做了不对称性分析：
  - `_archive_active`（`engine/runner.py:261-267`）只归档 draft/partial（不动 pushed）
  - PATCH 端点（`api/suggestion.py:172`）严格拒绝修改 archived
  - archive 端点（`api/suggestion.py:320-321`）拒绝重复归档
  - **push 端点（`api/suggestion.py:263-306`）完全不检查 sug.status**——不对称
  - 无任何文档/注释说明 push-on-archived 是有意为之
  - 业务推演：手动归档场景 + 自动归档场景 + archive-then-revert 场景，三者都不应该允许 push
- **结论**：**99% 是遗漏**——push 端点忘了状态前置校验
- **用户决策**：选 **C 方案 — 立即修复**
- **修复执行**：
  - `backend/app/api/suggestion.py:274-275` 添加状态前置校验：
    ```python
    if sug.status not in ("draft", "partial"):
        raise ConflictError(f"建议单状态为 {sug.status},不可推送")
    ```
  - `backend/tests/unit/test_suggestion_patch.py` 新增 2 个单测：
    - `test_suggestion_push_archived_rejected` — archived 抛 ConflictError
    - `test_suggestion_push_pushed_rejected` — pushed 抛 ConflictError（额外的幂等保护）
  - 全量 pytest：**156 passed**（原 154 + 新增 2），零回归
- **影响**：D6 维持 3（修复后状态机已封闭）；M3 P1 列表 -1 项；P0-2 候选判定从"⚠️ 部分实现"升级为"✅ 已实现"

### #3 推送操作人审计日志
- **疑问**：1-5 人内部工具是否需要 operator audit log？
- **用户回答**：**不需要**
- **影响**：从 P1 列表删除此项；M3 D3 / D5 评分不变

### #4 push 批量无上限
- **疑问**：`PushRequest.item_ids` 无 max_length 约束，是否需要重设上限？
- **用户回答**：**不需要**——业务有自然上界（单张建议单的条目数有限）
- **影响**：D8 评分不变；不新增 P2

### #5 D9 错误码 vs 前端需求
- **疑问**：API 错误码设计（SaihuAPIError code 透传）是否满足前端展示需求？
- **调查**：Claude 主控读取前端展示逻辑：
  - `frontend/src/views/SuggestionDetailView.vue:137` 直接展示 `item.push_error || '-'`，无映射
  - `frontend/src/views/SuggestionListView.vue:355` 直接展示 `task.error_msg`，无映射
  - 后端 `pushback/purchase.py:98-100` 抛错时格式化为 `f"{e.code}: {e.message}"`
  - 当前展示对小团队完全够用（中文消息可读），但对小白用户不够（无操作建议）
- **结论**：**1-5 人内部工具场景下当前展示足够**——不需要结构化错误码体系
- **用户决策**：（隐含）维持现状
- **影响**：D9 维持 2；从 M3 独有问题里移除"无结构化错误码"作为缺陷描述

### #6 D4 可部署性矩阵口径调整（第二轮 review）
- **疑问**：第一轮 review 时 M3 D4 标 N/A，理由是"无独立部署需求，属 M8 范围"。但用户在第二轮 review 时明确指出这违反"每个模块为自己的可部署性负责"的初衷
- **用户原话**："D4不是N/A 这个项目需要部署"
- **矩阵设计反思**：原 spec §3 把 M2/M3 的 D4 标 N/A 的依据是"没有独立的部署关注点"，但这种标准把责任全部推给 M8，违反评分卡的横向覆盖原则。只要项目要部署，每个模块就应该被评估其"部署就绪度"（借助共享基础设施也算在内）。
- **用户决策**：
  - M3 D4 从 N/A 改为实地评分
  - M2 retroactive 同步改为实地评分
  - spec §3 的 M2/M3 矩阵行更新（`·` → `✓`）
  - 未来 M4-M8 所有模块都按"实地评分"口径评 D4
- **M3 D4 新评分**：**3/4**——满足 Rubric 3 级（docker-compose + .env.example + 迁移 + 一键脚本 + 启动校验 + 资源限制），未满足 4 级缺 CI/CD + IaC + 蓝绿部署
- **M3 D4 独有缺口**（作为 P2-5 / P2-6 项列入待办）：
  - `PUSH_MAX_ITEMS_PER_BATCH` 是 dead config（定义但全库无引用）
  - `push_auto_retry_times` 缺少 `validate_settings` 校验（设 0/负数会导致 tenacity 异常）
- **影响**：
  - M3 计分格数从 8 → 9
  - M3 平均分从 2.50 → **2.56**
  - M2 需要 retroactive 更新（见 M2-engine.md）
  - spec §3 设计文档需同步更新
