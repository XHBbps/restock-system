# M2 补货引擎 评分

> 评估日期：2026-04-11
> 评估人：subagent (claude-sonnet-4-6)
> 范围：6 步流水线 + advisory lock + 快照机制
> 主战场维度：D1 / D6
> 横向参照：M1 赛狐集成（已封板，平均分 2.63/4）

---

## 1. 证据采集摘要

### 1.1 阅读的文件
- `backend/app/engine/runner.py` — 268 行
- `backend/app/engine/calc_engine_job.py` — 15 行
- `backend/app/engine/step1_velocity.py` — 113 行
- `backend/app/engine/step2_sale_days.py` — 142 行
- `backend/app/engine/step3_country_qty.py` — 34 行
- `backend/app/engine/step4_total.py` — 77 行
- `backend/app/engine/step5_warehouse_split.py` — 221 行
- `backend/app/engine/step6_timing.py` — 110 行
- `backend/app/engine/zipcode_matcher.py` — 110 行
- `backend/app/engine/__init__.py` — 1 行（空）
- `backend/app/models/suggestion.py` — 116 行
- `backend/app/tasks/worker.py` — 229 行
- `backend/tests/unit/test_engine_step1.py` — 93 行（9 个测试）
- `backend/tests/unit/test_engine_step2.py` — 58 行（4 个测试）
- `backend/tests/unit/test_engine_step3.py` — 55 行（5 个测试）
- `backend/tests/unit/test_engine_step4.py` — 89 行（6 个测试）
- `backend/tests/unit/test_engine_step5.py` — 204 行（9 个测试）
- `backend/tests/unit/test_engine_step6.py` — 69 行（5 个测试）
- `backend/tests/unit/test_zipcode_matcher.py` — 138 行（12 个测试）
- `backend/tests/unit/test_engine_runner.py` — 230 行（7 个测试）

### 1.2 测试运行结果
```
57 tests collected, 57 passed, 0 failed, 0 skipped (0.85s)
分布：step1=9, step2=4, step3=5, step4=6, step5=10, step6=5, zipcode_matcher=12, runner=7
```

### 1.3 关键 grep 结果摘录

- **advisory lock 覆盖范围**：`runner.py:58-60` — `text("SELECT pg_advisory_xact_lock(:key)")` 是 `run_engine` 进入事务后的第一个操作。`calc_engine_job.py` 是唯一入口；`sync.py:run_engine_now` 通过任务队列 enqueue，所有路径均经过 `run_engine`。锁在同一事务内通过 `pg_advisory_xact_lock`（事务级），事务结束自动释放。锁覆盖 100%。
- **JSONB 快照**：`runner.py:177-183` — `velocity_snapshot`、`sale_days_snapshot`、`country_breakdown` 在 INSERT 时写入，`runner.py:244-248` — `global_config_snapshot` 在建议单头部写入。快照仅在 INSERT 时写入，ORM 没有提供运行时更新快照字段的 API（`suggestion.py` API 层 PATCH 不包含快照字段）。事实上不可变，但**无数据库约束**（如 DB 触发器或列级 immutable check）强制保护。
- **raw SQL**：`runner.py:59` — 只有 1 处 `text("SELECT pg_advisory_xact_lock(:key)")`，参数化传入（无拼接风险）。所有其他 DB 操作均为 ORM。`worker.py` 有多处 raw SQL 但属于 M4 范围，引擎层本身无问题。
- **load_in_transit**：`step2_sale_days.py:49-91` — 查询 `push_status='pushed' AND status != 'archived' AND created_at >= now()-90天`，基于 `country_breakdown` 聚合，防止重复建议。90 天截止窗口在 `timedelta(days=90)` 实现。**注**：本机制（"已订未收"虚拟在途）与系统中另一张 `in_transit_record` 表（"已发未到"实际出库单，由 `sync/out_records.py` 写入、供前端出库页 `DataOutRecordsView` 查看）是**两个完全不同的概念**——前者是采购单已推送但赛狐未生成出库单，后者是赛狐已生成出库单但货物未到达海外仓。两者在数据流时间线上是上下游关系，不存在重叠计算风险（详见 §7 #1 用户澄清）。
- **引擎入口**：单一入口 `runner.py:50 run_engine()`，由 `calc_engine_job.py:8 @register("calc_engine")` 注册。API 层 `sync.py:100` 通过 `enqueue_task("calc_engine",...)` 触发，不直接调用 runner。
- **step 间日志**：`runner.py:88-201` — `ctx.progress(current_step=...)` 在每个步骤开始时调用，`total_steps=7` 在 Step 1 声明，每 20 条 SKU 更新一次进度。6 步全覆盖（Steps 1-6 全部有 progress 回调）。

---

## 2. 维度评分

### D1 功能完整性
- **得分**：3/4
- **判据匹配**：
  - ✅ 满足 Rubric 2 级：主链路端到端完整（Step 1→6 → persist），6 个 step 文件全部实现，邮编路由覆盖"已知比例/零数据均分/无仓空返"三种模式。
  - ✅ 满足 Rubric 3 级：边界场景已处理：空 SKU 列表（`runner.py:77-86`）早退出、零销量 SKU 跳过（`step3_country_qty.py:24`）、本地库存为 None（`step4_total.py:66`）、sale_days 缺失时 t_purchase 退化为今天（`step6_timing.py:84-94`）、无仓库时返回 `no_warehouse`（`step5_warehouse_split.py:201-209`）、push_blocker 预检（`runner.py:169`）。
  - ❌ 未满足 Rubric 4 级：无集成测试（runner 的完整 end-to-end 路径仅有 mock DB 测试，不含真实 DB 场景）；`load_in_transit` 无单测覆盖（`step2_sale_days.py:49-91` 的异步 DB 路径没有对应测试）；无契约测试守护 Step 公式接口。
- **支撑证据**：
  - `backend/app/engine/runner.py:77-86` — 无 SKU 场景早退出
  - `backend/app/engine/step6_timing.py:84-94` — sale_days 缺失即时采购语义
  - `backend/app/engine/step5_warehouse_split.py:201-208` — no_warehouse 兜底
  - `backend/tests/unit/test_engine_runner.py:165-186` — runner 无 SKU 路径的 mock DB 测试
- **未达上一级的差距**：缺少完整引擎集成测试（真实 DB session 覆盖 happy path + 并发场景）；`load_in_transit` 90 天截止逻辑无专项单测。
- **对照 M1 [3] 的标尺**：M1 因为"无集成/契约测试守护核心路径（分页终止、retry 次数、token 刷新）"而止步于 3。M2 同样因为"无集成测试守护引擎完整路径"而止步于 3。两者同级，标尺一致。
- **疑点**：✅ 已澄清（见 §7 #1）——`in_transit_record` 表与 `load_in_transit` 函数是**两个独立机制**（前者是出库页数据源，后者是引擎去重），不存在重叠计算风险，subagent 初评中的"两套在途机制"描述是误读，已纠正。

### D2 代码质量
- **得分**：3/4
- **判据匹配**：
  - ✅ 满足 Rubric 2 级：57 个引擎相关单测全部通过；每个 step 的计算函数均暴露为纯函数（`compute_velocity`、`aggregate_velocity_from_items`、`merge_inventory`、`compute_sale_days`、`compute_country_qty`、`compute_total`、`explain_country_qty_split`、`compute_timing_for_sku` 等），可独立测试。
  - ✅ 满足 Rubric 3 级：命名清晰（`load_in_transit`、`merge_inventory`、`explain_country_qty_split` 语义明确）；无大型 if/else（`zipcode_matcher._compare` 最长约 20 行，逻辑清晰）；模块级 docstring 带公式引用（FR-028/030/031/032/033/034）；step 文件每个都在 100-220 行以内；type hints 全覆盖；`step5_warehouse_split.py` 用 `@dataclass CountryAllocationResult` 结构化返回，无魔术字典。
  - ❌ 未满足 Rubric 4 级：无集成测试（runner 的全链路 DB 路径）；无 mutation/property test；`load_in_transit`（step2）的异步路径未被测试；无 mypy/ruff 运行结果可验证为 0 warning（未运行，无法确认）。
- **支撑证据**：
  - `backend/app/engine/step1_velocity.py:29-34` — `compute_velocity` 纯函数，有公式注释
  - `backend/app/engine/step5_warehouse_split.py:27-32` — `CountryAllocationResult` dataclass
  - `backend/app/engine/zipcode_matcher.py:1-9` — FR-034/034a 公式引用 docstring
  - `backend/tests/unit/test_engine_step1.py` 到 `test_zipcode_matcher.py` — 57 个测试全 pass
- **未达上一级的差距**：无集成测试；`load_in_transit` 等异步 DB 函数缺乏 mock 单测；未能确认 mypy 0 warning。
- **对照 M1 [2] 的标尺**：M1 因为"`SaihuClient`/`TokenManager` 核心方法无单测，覆盖率不足 70%"而打 2 分。M2 纯函数覆盖率明显高于 M1（所有计算 step 的核心逻辑均有专项单测，runner 也有 mock 路径测试），D2 评 3 分。

### D3 安全性 ◦（低权重）
- **得分**：2/4
- **判据匹配**：
  - ✅ 满足 Rubric 2 级（并发安全视角）：`pg_advisory_xact_lock(7429001)` 阻止并发引擎覆盖，覆盖唯一引擎入口 `run_engine`；唯一的 raw SQL 为 advisory lock 且参数化传入（无拼接）；JSONB 快照字段在代码层仅在 INSERT 时写入。
  - ❌ 未满足 Rubric 3 级：JSONB 快照无 DB 级不可变约束（无触发器/列约束强制阻止事后更新）；`velocity_snapshot`/`sale_days_snapshot` 列在数据库层仍可被任何拥有 DB 权限的语句覆盖；无 CVE 扫描（与 M1 共性问题）。
- **支撑证据**：
  - `backend/app/engine/runner.py:58-60` — advisory lock 参数化 text
  - `backend/app/models/suggestion.py:94-95` — velocity_snapshot/sale_days_snapshot 无 immutability 约束
  - `backend/app/api/suggestion.py:215` — API PATCH 层确实未暴露快照字段（code-level 保护），但无 DB 约束
- **未达上一级的差距**：快照字段无 DB 级不可变约束；无 CVE 扫描；无依赖审计流水线。
- **对照 M1 [2] 的标尺**：M1 因为"代码层无代理/出口 IP 接入点、无 CVE 扫描、access_token 作为 URL query 参数传输"而打 2 分。M2 无外部 API 调用面，并发安全通过 advisory lock 解决，但 JSONB 快照无 DB 约束保护，与 M1 同级打 2 分。

### D4 可部署性
- **得分**：N/A
- **理由**：补货引擎无独立部署需求，作为 worker job 运行；部署属于 M4 任务队列 / M8 部署的范围。

### D5 可观测性
- **得分**：3/4
- **判据匹配**：
  - ✅ 满足 Rubric 2 级：structlog JSON 日志（`get_logger` from `app.core.logging`）；`step6_timing.py:85` 有 `logger.warning("step6_sale_days_missing_treated_as_immediate_purchase")` 结构化日志。
  - ✅ 满足 Rubric 3 级：每个 step 开始时调用 `ctx.progress(current_step=...)` 更新 `task_run` 表的 `current_step`/`step_detail`/`total_steps`（`runner.py:88-201`），进度可追溯；计算结果全量以 JSONB 快照形式持久化（`velocity_snapshot`、`sale_days_snapshot`、`global_config_snapshot`、`allocation_snapshot`）；每 20 条 SKU 更新进度（`runner.py:191-192`）；step6 缺失 sale_days 时有告警日志记录。
  - ❌ 未满足 Rubric 4 级：无 OpenTelemetry；无 Prometheus /metrics；无 Grafana 看板；无 SLO/SLI；步骤耗时未记录（仅有步骤名称，无 duration）。
- **支撑证据**：
  - `backend/app/engine/runner.py:88-91` — `ctx.progress(current_step="Step 1: 计算 velocity", total_steps=7)`
  - `backend/app/engine/runner.py:182-183` — `velocity_snapshot`/`sale_days_snapshot` 快照写入
  - `backend/app/engine/step6_timing.py:85-88` — `logger.warning("step6_sale_days_missing_treated_as_immediate_purchase")`
- **未达上一级的差距**：无每步耗时 (duration) 记录；无 /metrics 指标端点；无外部告警接入。
- **对照 M1 [3] 的标尺**：M1 因为有"api_call_log、/api/monitor/saihu-calls 聚合端点、rate_limit 命中记录"而打 3 分。M2 通过 task_run progress + JSONB 快照达到 3 级，且 JSONB 快照提供了 M1 中没有的"计算状态完整保存"能力，但同样缺 OpenTelemetry/Prometheus，止步于 3 分，标尺一致。

### D6 可靠性 ⚠️ 主战场
- **得分**：3/4
- **判据匹配**：
  - ✅ 满足 Rubric 2 级：`pg_advisory_xact_lock` 保证并发安全（`runner.py:58-60`）；`_persist_suggestion` 在同一事务内先归档再 INSERT（`runner.py:241-258`），原子性由 PostgreSQL 事务保证；`load_in_transit` 90 天窗口防止无限累积在途量（`step2_sale_days.py:67`）；worker 的 `_mark_failed` 确保引擎异常时 task_run 落 failed 状态（`worker.py:149-151`）。
  - ✅ 满足 Rubric 3 级：
    - advisory lock 覆盖唯一引擎入口（单一事务内锁定，防竞争）；
    - 建议单写入前先归档 draft/partial（`runner.py:261-267`），防止孤儿建议单残留；
    - in_transit 去重：基于 `push_status='pushed' AND status!='archived'` 的精确过滤；
    - JSONB 快照在代码层不可变（API PATCH 层 `suggestion.py:215` 不暴露快照字段）；
    - push_blocker 预检（`runner.py:168-170`）防止无效建议入库后阻塞推送；
    - worker 异常捕获 (`worker.py:149-151`) 将引擎崩溃映射为 `task_run.status='failed'`。
  - ❌ 未满足 Rubric 4 级：无熔断器；无死信队列（失败任务不自动重入队，`worker.py:8` 注释明确）；无 chaos test/故障注入；快照字段无数据库约束保护（理论上可被 DB 直连覆盖）；引擎中途失败后旧建议单已归档但新建议单不存在（事务回滚保证一致性，**用户已确认这是预期行为**——见 §7 #2，恢复策略为手动重新触发），但缺少集成测试覆盖此路径。
- **支撑证据**：
  - `backend/app/engine/runner.py:58-60` — advisory lock（唯一入口保护）
  - `backend/app/engine/runner.py:261-267` — `_archive_active` 原子归档
  - `backend/app/engine/step2_sale_days.py:67` — `cutoff = now_beijing() - timedelta(days=90)`
  - `backend/app/tasks/worker.py:149-151` — `except Exception: _mark_failed`
  - `backend/app/models/suggestion.py:29-34` — status CheckConstraint（状态机由 DB 约束）
- **未达上一级的差距**：无死信队列（失败任务无自动重试机制）；快照字段缺 DB 级不可变约束；无对"引擎事务回滚后建议单状态"的集成测试验证。
- **对照 M1 [3] 的标尺**：M1 因为有"tenacity 指数退避、token single-flight、permanent/transient 错误分类"而打 3 分，未达 4 级是因为"无熔断、无死信队列、无 chaos test"。M2 在并发控制和状态机设计上与 M1 同级：有 advisory lock、原子归档、worker 失败捕获，但同样缺熔断和死信队列，评 3 分，标尺一致。

### D7 可维护性
- **得分**：3/4
- **判据匹配**：
  - ✅ 满足 Rubric 2 级：`AGENTS.md`/`CLAUDE.md` 存在且完整；架构蓝图 `Project_Architecture_Blueprint.md` 第 3.1 节有 6 步流水线完整表格（含公式）。
  - ✅ 满足 Rubric 3 级：
    - 模块边界清晰：step1-6 各文件职责单一，纯函数与 async DB 函数分离；
    - 每个 step 文件 docstring 带 FR 编号（FR-028 到 FR-035）；
    - 非显然逻辑有注释（`step4_total.py:73-75` — invariant 注释；`step6_timing.py:83-94` — sale_days 缺失语义注释；`runner.py:44-47` — advisory lock 设计意图）；
    - 架构蓝图中 6 步流水线公式完整文档化；
    - `AGENTS.md`/文档同步协议存在。
  - ❌ 未满足 Rubric 4 级：无 ADR（邮编路由算法选择、in_transit 去重机制等无 ADR 记录）；无自动化文档生成；onboarding 时间未量化。
- **支撑证据**：
  - `backend/app/engine/step1_velocity.py:1-14` — FR-028 公式 docstring
  - `backend/app/engine/step4_total.py:51-53,73-75` — 不变量注释
  - `backend/app/engine/runner.py:44-47` — advisory lock 设计意图注释
  - `docs/Project_Architecture_Blueprint.md:100-113` — 6 步流水线表格
- **未达上一级的差距**：无 ADR（核心算法决策无历史记录）；无自动化文档生成。
- **对照 M1 [3] 的标尺**：M1 因为有"client/endpoints/sync 分层清晰、模块级 docstring、非显然逻辑注释"而打 3，未达 4 是"无 ADR"。M2 同样：分层清晰（step 职责单一）、文档完整、注释充分，但无 ADR，评 3 分，标尺一致。

### D8 性能与容量
- **得分**：2/4
- **判据匹配**：
  - ✅ 满足 Rubric 2 级：
    - 无 N+1：`load_all_sku_country_orders` 一次性批量加载所有 SKU 近 30 天订单（`step5_warehouse_split.py:71-113`，注释明确"避免 NxM 次 N+1"）；step1/step2/step4 各自一次查询；
    - step 间数据传递为 Python dict（无大对象拷贝的额外序列化）；
    - `suggestion_item` 索引：`ix_suggestion_item_suggestion`、`ix_suggestion_item_sku`、`ix_suggestion_item_urgent`；
    - 规模估算：日均 <500 订单，全量计算对每个启用 SKU 仅内存操作，预期毫秒级完成。
  - ❌ 未满足 Rubric 3 级：无引擎 SLO 定义；无慢查询日志；无容量评估文档（SKU 规模上限未定义）；无资源限制（引擎无超时设置，长时间运行无熔断）；step5 `match_warehouse` 对每张订单逐规则线性扫描（但规则数量少，实际影响可忽略）。
- **支撑证据**：
  - `backend/app/engine/step5_warehouse_split.py:79` — 注释"避免 N+1（宪法 V）"
  - `backend/app/engine/runner.py:108-109` — `load_all_sku_country_orders` 批量加载
  - `backend/app/engine/step5_warehouse_split.py:99-113` — 单次批量查询替代 NxM
- **未达上一级的差距**：无 SLO；无引擎超时设置；无容量基线测试；step5 对每条订单仍有 O(R) 规则扫描（R=规则总数，低规模时无影响但无量化）。
- **对照 M1 [2] 的标尺**：M1 因为"无 SLO、无慢查询日志、无容量评估、api_call_log 无清理机制"而打 2 分。M2 同样：有防 N+1 设计，但无 SLO、无容量评估，评 2 分，标尺一致。

### D9 用户体验
- **得分**：N/A
- **理由**：补货引擎无直接 UI，不适用。

---

## 3. 模块得分
- **各维度分数**：D1=3 D2=3 D3=2 D5=3 D6=3 D7=3 D8=2
- **平均分（剔除 N/A，7 维度）**：(3+3+2+3+3+3+2) / 7 = 19 / 7 = **2.71 / 4**
- **主战场维度**：D1=3 D6=3

---

## 4. 本模块发现的关键问题

### 🔴 P0 阻塞
无。

### 🟡 P1 强烈建议
1. **JSONB 快照字段无 DB 级不可变约束**：`velocity_snapshot`/`sale_days_snapshot`/`global_config_snapshot` 在代码层仅靠 API 层不暴露字段来保护，无数据库触发器/列约束阻止直连覆盖。一旦有直连 DB 操作（运维排查等），快照可被静默覆盖，导致回溯失真。建议添加 PostgreSQL 触发器或在 ORM 层添加 `__setattr__` 保护。
2. **`load_in_transit` 无单测覆盖**：`step2_sale_days.py:49-91` 的异步 DB 路径（90 天截止窗口、`push_status='pushed'` 过滤逻辑）无任何测试，是 step2 中最复杂的去重逻辑，但无 mock 单测守护。
3. **引擎无执行超时**：`run_engine` 无超时机制。若某步 DB 查询卡住（如大表全扫），worker 租约到期会被 reaper 标记为失败，但在此之前任务一直 running，且无告警。建议在 worker 层对 calc_engine 任务类型设置最大执行时间。

### 🟢 P2 可延后
1. **step5 邮编匹配 O(R×N) 复杂度**：`match_warehouse` 对每条订单线性扫描所有规则。当前规模（规则 <50，订单 <500/日）无影响，但若规则数量增长应改为前缀树/分组索引。
2. **无 ADR 记录核心算法决策**：邮编路由策略（按比例 vs 均分）、in_transit 去重（建议单 country_breakdown 而非 out_record 聚合）的选型决策未以 ADR 形式记录，影响未来维护者理解。
3. **`calc_engine` 失败无自动重试**：worker 明确设计"不自动重入队"（`worker.py:8`），引擎失败需手动重触发。对于因瞬态 DB 故障导致的失败，需要人工干预，建议评估是否需要自动重试 1 次。
4. **`velocity_snapshot` / `sale_days_snapshot` 列定义与代码意图不一致** ｜ 用户已选清洁度加固方案
   - 现状：列定义为 `nullable=True`，但 `runner.py:182-183` 永远写入非空值；实地查询确认 728/728 条 suggestion_item 全部非空非空 dict（见 §7 #3）；`metrics.py:153` 的 `if not it.sale_days_snapshot` 防御检查实际为 dead code
   - 修复动作（用户已选 B 方案）：
     - 写一条 Alembic migration 把两列改为 `NOT NULL`
     - 删除 `metrics.py:153` 的防御检查
     - 加 ORM 层 `__init__` 默认值或断言避免将来再退化
   - 类型：技术债清洁度提升，零业务影响，不影响交付，列入打分后的待办

---

## 5. 与 M1 共性 / 差异问题

- **共性**：
  - 缺 CVE 扫描 / pip-audit（M1 和 M2 同为 P1）
  - 缺集成测试守护核心路径（M1 缺 client mock 测试；M2 缺 runner 全链路 DB 测试）
  - 缺 ADR（M1/M2 均无 ADR 历史）
  - 缺 OpenTelemetry / Prometheus /metrics（两者均止步于 D5=3）

- **差异**：
  - M2 独有：JSONB 快照字段无 DB 级不可变约束（M1 无此问题，M1 的快照类字段不存在）
  - M2 独有：引擎无执行超时（M1 的 saihu client 有 `httpx.timeout`，M2 的引擎计算无超时）
  - M2 独有：快照列 nullable 与代码意图不一致（用户已选清洁度加固，详见 P2-4）

---

## 6. 给用户的确认问题

✅ 全部 5 个疑点在第一轮 review 中已由用户澄清，详见 §7 用户澄清记录。

---

## 7. 用户澄清记录（2026-04-11 第一轮 review）

### #1 `in_transit_record` 表 vs `load_in_transit` 函数
- **疑问**：是否两套在途机制重叠？是否需要删除其中之一？
- **调查**：Claude 主控对全代码库做了 Grep 验证：
  - `InTransitRecord` 在 17 个文件中被引用，关键路径包括：`backend/app/sync/out_records.py`（sync job UPSERT 写入）、`backend/app/api/data.py`（GET `/api/data/out-records` 端点）、`frontend/src/views/data/DataOutRecordsView.vue`（前端"出库"页）、导航 `navigation.ts` 注册
  - 数据流：赛狐"在途中"出库单 → sync job → `in_transit_record` 表 → API 端点 → 前端出库页给用户看
- **结论**：两个机制是**完全不同的概念**，**不能删** `in_transit_record` 表
  - `in_transit_record`：**已发未到**（赛狐已生成出库单，货物在路上未到海外仓），用途是前端出库页给用户查看
  - `load_in_transit`：**已订未收**（采购单已推送给赛狐，赛狐还没生成出库单），用途是引擎去重避免对已推送的补货单重复建议
  - 在数据流时间线上是上下游关系，不存在重叠计算风险
- **影响**：subagent 初评对此误读，已纠正 §1.3、§2 D1 疑点、§5 共性差异；M2 D1/D6 评分**不变**

### #2 引擎事务回滚后的"无建议单"状态
- **疑问**：`_persist_suggestion` 中途失败后旧建议单已归档但新建议单不存在，是否需要补偿恢复？
- **用户回答**：**这是预期行为**——"无建议单可以留空，然后再手动触发"
- **影响**：D6 评分不变；§2 D6 描述加注澄清；不需要补偿机制

### #3 `velocity_snapshot` / `sale_days_snapshot` 字段 nullable
- **疑问**：是否存在 NULL 历史记录？`metrics.py:153` 的防御检查是否必要？
- **调查**：用户授权下，Claude 主控运行只读 SQL：
  ```sql
  SELECT
    count(*) FILTER (WHERE velocity_snapshot IS NULL) AS velocity_null,
    count(*) FILTER (WHERE sale_days_snapshot IS NULL) AS sale_days_null,
    count(*) FILTER (WHERE velocity_snapshot = '{}'::jsonb) AS velocity_empty,
    count(*) FILTER (WHERE sale_days_snapshot = '{}'::jsonb) AS sale_days_empty,
    count(*) AS total
  FROM suggestion_item
  ```
  结果：`total=728`、`velocity_null=0`、`sale_days_null=0`、`velocity_empty=0`、`sale_days_empty=0`
- **结论**：列定义与代码实际行为不一致——728 条记录全部非空，`metrics.py:153` 是 dead code
- **用户决策**：选 **B 加固方案**——写 migration 把列改为 NOT NULL + 删除 metrics.py 防御检查
- **影响**：新增 P2-4 记录此待办；不在 M2 审计阶段执行代码改动，列入打分后的待办清单

### #4 SKU 规模上限与 step1 全量加载性能
- **疑问**：`load_velocity_inputs` 无分页一次拉 30 天所有订单行，SKU 规模扩大到数千是否有问题？
- **用户回答**：**SKU 当前是百级别规模**
- **影响**：D8 评分不变；当前规模下 step1 全量加载完全够用，无 N+1，不构成 P1/P2 问题

### #5 Advisory lock 与手动触发并发
- **疑问**：调度器和手动触发并发时是否需要"检测到锁则跳过"？
- **用户回答**：**重复触发就跳过**
- **调查**：Claude 主控验证当前实现：
  - `enqueue_task` (`backend/app/tasks/queue.py:23-93`) 使用 `dedupe_key="calc_engine"` + 部分唯一索引（pending/running 状态下唯一）
  - 重复入队时进入 dedupe 分支，返回已存在的 task_id 并写入 SKIPPED 审计记录（`dedupe_key=f"{job_name}#skipped#{existing_id}"`）
  - 调度器和手动触发不会同时运行——第二个会被任务队列层直接跳过
  - Advisory lock 是**二道防线**（defense in depth），在单 worker 场景下永远不会被触发
- **结论**：用户期望的"重复触发跳过"**已经在任务队列层实现**，无需修改 advisory lock 逻辑
- **影响**：subagent 初评对此误读，已纠正；M2 D6 评分不变；无需代码改动
