# 补货系统全链路 Review 报告

> 审查日期: 2026-04-12
> 审查范围: 后端引擎链路 (Step 1-6 + Runner)、数据同步层、任务队列、推送模块、API 层、前端、部署
> 测试基线: 163 单元测试全部通过 (3.12s)
> 审查方法: A(链路驱动) + B(分层静态)

---

## 一、链路正确性审查 (A: 引擎 Pipeline)

### 链路概览

```
赛狐 API → Sync Jobs → DB → Engine Runner → 6 Steps → Suggestion → Push → 赛狐采购单
                                  ↓
                   Step1 Velocity → Step2 SaleDays → Step3 CountryQty
                         → Step4 Total → Step5 WarehouseSplit → Step6 Timing
```

### 测试场景矩阵

| # | 场景 | 期望行为 | 代码验证结果 | 结论 |
|---|------|----------|-------------|------|
| S1 | 标准补货 (有销量+有库存+有仓库) | 6 步正常产出 suggestion | runner.py 全链路逻辑 ✓，E2E test ✓ | **PASS** |
| S2 | 零销量 SKU (velocity=0) | country_qty=0, 跳过该 SKU | step3:26-27 `if v<=0: continue` ✓ | **PASS** |
| S3 | 国内库存 > 需求 | total_qty 被 clamp 到 sum_qty | step4:74 `if raw < sum_qty: raw = sum_qty` — 国内不参与扣减,invariant 正确 | **PASS (by design)** |
| S4 | 无海外仓库匹配 | fallback even 或 no_warehouse | step5:204-210 ✓ | **PASS** |
| S5 | between 邮编运算符 | 区间匹配 → 正确分仓 | zipcode_matcher 测试 ✓ (14 个测试) | **PASS** |
| S6 | 在途库存计算 | pushed 未归档建议的 country_breakdown | step2:69-78 ✓，90 天窗口 | **PASS** (但有 P2 项) |
| S7 | 缺少 commodity_id | push_blocker 标记 | runner:168-170 ✓ | **PASS** |
| S8 | 全部 country_qty=0 (库存充足) | total_qty=0, SKU 被跳过 | runner:130-131 `if total_qty<=0: continue` ✓ | **PASS** |
| S9 | 浮点精度边界 (velocity 恰好整除) | 一致的取整行为 | **步骤间取整策略不一致** | **ISSUE P0-2** |

---

## 二、修复清单

### P0 — 数据正确性（影响计算结果）

#### ~~P0-1: Step4 total_qty 国内库存扣减~~ → **By Design (已确认)**

**文件**: `backend/app/engine/step4_total.py:74-76`
**业务确认**: 国内库存不参与扣减。当前 invariant `if raw < sum_qty: raw = sum_qty` 是正确行为——国内库存仅用于抵消 buffer 部分，不影响各国实际补货需求。
**行动**: 在代码中添加注释说明业务意图，标记为 closed。

---

#### P0-2: 引擎步骤间取整策略不一致

**文件**: 多文件
**现象**:
| 步骤 | 取整方式 | 文件:行 |
|------|---------|---------|
| Step3 country_qty | `math.ceil()` (向上取整) | step3_country_qty.py:33 |
| Step4 total_qty | `round()` (银行家舍入) | step4_total.py:76 |
| Step5 仓分配 | `round()` + 末仓兜底 | step5_warehouse_split.py:191 |
| Step6 ship_offset | `round()` (银行家舍入) | step6_timing.py:95 |

**影响**:
- Step3 用 `ceil` 得到 country_qty=3，但 Step4 用 `round` 可能得到 total=2（当 buffer_qty 为负贡献时），触发 invariant 把 total 拉回 3
- `round(2.5)=2`（银行家舍入到偶数），可能导致采购量比预期少 1 件
- Step6 的 `round(0.5)=0` 可能导致发货日期偏移 1 天

**建议修复**: 统一使用 `math.ceil()` 用于数量计算（宁多勿少的补货原则），`round()` 仅用于非关键的日期偏移。

---

#### P0-3: SuggestionItemPatch 缺少值域校验

**文件**: `backend/app/schemas/suggestion.py:64-71`
**现象**: `country_breakdown` 和 `warehouse_breakdown` 的 dict 值没有非负校验。用户可以 PATCH 负数进去。
```python
country_breakdown: dict[str, int] | None = None      # ← 值可以是 -100
warehouse_breakdown: dict[str, dict[str, int]] | None = None  # ← 同上
```
**影响**: 负数的 country_breakdown 会导致 sum(breakdown) > total_qty 校验误判，推送到赛狐会产生负数采购量。
**建议修复**: 添加 Pydantic validator:
```python
@model_validator(mode="after")
def _values_non_negative(self):
    if self.country_breakdown:
        for k, v in self.country_breakdown.items():
            if v < 0:
                raise ValueError(f"country_breakdown[{k}] 不可为负")
    # warehouse_breakdown 同理
    return self
```

---

#### P0-4: 推送失败时可覆盖已成功的 push_status

**文件**: `backend/app/pushback/purchase.py:129-137`
**现象**: 推送成功路径有 TOCTOU 保护（line 118: `push_status != "pushed"`），但失败路径没有：
```python
# 成功 (有保护 ✓)
.where(SuggestionItem.push_status != "pushed")

# 失败 (无保护 ✗)
.where(SuggestionItem.id.in_(item_ids))  # ← 无状态检查
.values(push_status="push_failed", ...)
```
**影响**: 并发场景下，如果 A 线程推送成功写入 "pushed"，B 线程（同批次重试）推送失败后会覆盖为 "push_failed"，丢失成功状态。
**建议修复**: 失败路径添加同样的 guard:
```python
.where(SuggestionItem.push_status.not_in(("pushed",)))
```

---

### P1 — 健壮性（并发安全 / 错误恢复）

#### P1-1: GlobalConfig 无正值校验

**文件**: `backend/app/engine/runner.py:63`
**现象**: `config.target_days`、`config.buffer_days`、`config.lead_time_days` 直接使用，无正值断言。
**影响**: 如果配置表被误改为 0 或负数：`target_days=0` → Step3 所有 country_qty=0 → 无建议单产出，静默失败。
**建议修复**: runner.py 加载 config 后添加校验:
```python
if config.target_days <= 0:
    raise ValueError(f"target_days must be > 0, got {config.target_days}")
```

---

#### P1-2: enqueue_task 递归重试无深度限制

**文件**: `backend/app/tasks/queue.py:79-86`
**现象**: UniqueViolation 后查不到活跃任务时递归调用自身，无深度限制。
**影响**: 极端竞争下（多线程同时入队 + 完成 + 入队）可能导致栈溢出。概率极低但属于隐患。
**建议修复**: 添加重试次数参数:
```python
async def enqueue_task(..., _retry_depth: int = 0) -> tuple[int, bool]:
    ...
    if existing_id is None:
        if _retry_depth >= 2:
            raise RuntimeError("enqueue_task: 去重竞态重试耗尽")
        return await enqueue_task(..., _retry_depth=_retry_depth + 1)
```

---

#### P1-3: 同步层 delete-then-insert 模式有数据丢失风险

**文件**: `backend/app/sync/order_list.py:146-147`，`backend/app/sync/out_records.py:115-134`
**现象**: 更新订单明细时先 DELETE 所有旧 items 再 INSERT 新 items。
**影响**: 如果 INSERT 阶段失败（网络抖动、内存不足），已经 DELETE 的旧数据不可恢复（因为中间有 commit）。
**建议修复**:
- 方案 A: 把 delete + insert 包在同一个事务内（不做中间 commit）
- 方案 B: 改用 UPSERT (on_conflict_do_update)，避免先删后增

---

#### P1-4: 增量同步窗口使用预计算的 `now`

**文件**: `backend/app/sync/order_list.py:76-84`
**现象**: `_compute_window()` 使用调用前的 `now` 作为窗口终点，但实际数据拉取可能持续数分钟。同步期间更新的订单直到下一轮才能被捕获。
**影响**: 5 分钟 overlap 可以覆盖大部分情况，但如果某次同步特别慢（>5min），会出现数据缺口。
**建议修复**: 将窗口终点改为同步开始时的 `now`（当前已是如此）+ 确保 overlap 大于单次最长同步耗时。可以把 overlap 改为可配置参数。

---

#### P1-5: 同步中间 commit 导致部分数据提交

**文件**: `backend/app/sync/inventory.py:40-41`，`backend/app/sync/out_records.py:43-44`
**现象**: 每 50-100 条记录做一次 `db.commit()`，如果同步中途异常，已 commit 的部分数据在 DB 中但 sync_state 不会标记 success。
**影响**: 下次增量同步的起始时间点可能在已 commit 数据之前，导致重复处理（UPSERT 保证了幂等，所以不会出错，但会浪费时间）。
**风险评估**: 低风险——UPSERT 保证幂等。但 sync_state 的 last_success_at 不准确。
**建议修复**: 记录已处理的最后一条记录时间戳，而不是依赖 sync 开始时间。

---

#### P1-6: Token 刷新后的重试缺少抖动 (jitter)

**文件**: `backend/app/saihu/client.py:89-94`
**现象**: Auth 过期后的重试 `await asyncio.sleep(0.5)` 是固定延迟。
**影响**: 如果多个并发请求同时遇到 token 过期，全部在 0.5s 后同时重试，形成 thundering herd。
**建议修复**: 添加随机抖动:
```python
await asyncio.sleep(0.3 + random.random() * 0.4)  # 0.3-0.7s
```

---

#### P1-7: parse_purchase_date 无容错

**文件**: `backend/app/engine/step6_timing.py:32-36`
**现象**: `date.fromisoformat(raw)` 对非标准格式直接抛 ValueError。
**影响**: 如果 DB 中存储了非 ISO 格式的日期字符串，`has_urgent_purchase` 调用会崩溃。
**建议修复**: 添加 try-except 返回 today（保守策略：格式错误视为紧急）。

---

#### P1-8: Reaper 多实例无互斥

**文件**: `backend/app/tasks/reaper.py:59-75`
**现象**: Reaper 在 worker 和 scheduler 两个容器冗余运行（设计如此），UPDATE 语句本身是原子的。
**风险评估**: **低风险**——PostgreSQL 的 UPDATE+WHERE 是原子操作，多实例同时执行只会有一个真正更新行。RETURNING 保证不会重复报告。
**当前状态**: 可以接受。但建议在日志中标注 reaper 实例 ID 以便排查。

---

### P2 — 工程质量（可观测性 / 测试 / 代码规范）

#### P2-1: 引擎边界场景无日志

**文件**: 引擎全链路
**现象**: 以下情况静默发生，无任何日志:
- Step1: velocity=0 的 SKU 被跳过
- Step3: country_qty 被 clamp 到 0
- Step4: total_qty 被 invariant 调高
- Step5: 分配模式 fallback_even 或 no_warehouse
**建议修复**: 在关键分支添加 `logger.info()`，尤其是 Step4 invariant 触发和 Step5 fallback。

---

#### P2-2: 前端测试覆盖率过低

**现象**: 前端 8 个测试文件，覆盖率阈值仅 2%。核心页面（SuggestionListView、SuggestionDetailView）无任何测试。
**影响**: 建议单编辑、推送流程的前端逻辑无回归保护。
**建议修复**: 优先补充:
1. SuggestionDetailView 的编辑 + 保存测试
2. TaskProgress 的错误重试测试
3. API 层 mock 测试（error handling）

---

#### P2-3: 后端测试覆盖率阈值偏低 (55%)

**现象**: `.coveragerc` 设置 `fail_under = 55`。当前通过但未实际量化覆盖率。
**建议**: 提升至 70%，重点补充:
1. Step4 浮点精度边界测试
2. Step6 missing sale_days 路径测试
3. 推送失败路径的 push_status 测试
4. 同步层异常恢复测试

---

#### P2-4: 在途库存 90 天 cutoff 硬编码

**文件**: `backend/app/engine/step2_sale_days.py:67`
**现象**: `cutoff = now_beijing() - timedelta(days=90)` 不可配置。
**影响**: 如果物流异常超 90 天未到货，在途库存被遗漏，可能导致重复采购。
**建议修复**: 移到 GlobalConfig 作为可配置参数 `in_transit_cutoff_days`。

---

#### P2-5: 零数量 allocation_mode 标记为 "matched" 而非 "skipped"

**文件**: `backend/app/engine/step5_warehouse_split.py:150-157`
**现象**: 当 `country_qty <= 0` 时，返回 `allocation_mode="matched"`，语义不准确。
**影响**: 前端展示和调试时容易混淆——"已匹配"但仓分配为空。
**建议修复**: 改为 `allocation_mode="skipped"` 或 `"zero_qty"`。

---

#### P2-6: zipcode_matcher 数值类型 "=" 比较使用浮点相等

**文件**: `backend/app/engine/zipcode_matcher.py:82`
**现象**: `l_num == r_num` 直接比较两个 float。
**影响**: IEEE 754 浮点精度问题（`0.1+0.2 != 0.3`）。对邮编场景影响小（通常是整数比较），但代码不健壮。
**建议修复**: 对 number 类型的 "=" 使用整数比较 `int(l_num) == int(r_num)` 或 epsilon 比较。

---

#### P2-7: purchase.py 发送 total_qty=0 的条目

**文件**: `backend/app/pushback/purchase.py:74`
**现象**: 构造 saihu_items 时不校验 `it.total_qty > 0`。
**影响**: 可能向赛狐发送数量为 0 的采购条目，取决于赛狐 API 的校验行为（可能报 40014 参数异常）。
**建议修复**: 添加过滤: `saihu_items = [... for it in items if it.total_qty > 0]`

---

#### P2-8: api_call_log 写入失败静默丢弃

**文件**: `backend/app/saihu/client.py:249-254`
**现象**: 审计日志写入异常被 catch 后仅 warning，不影响业务流程。
**风险评估**: 设计合理（审计不应阻塞业务），但应有监控指标统计丢失率。
**建议修复**: 添加 Prometheus/statsd 计数器或结构化日志 field `log_write_failed_count`。

---

#### P2-9: Alembic 降级风险文档不完整

**文件**: `backend/alembic/versions/20260411_1500_*.py`
**现象**: 注释提到 "downgrade 前必须手动清理 between 行"，但无具体操作步骤。
**建议修复**: 在 runbook.md 中添加降级操作手册。

---

#### P2-10: Docker Compose 缺少持久化卷备份策略文档

**文件**: `deploy/docker-compose.yml`
**现象**: PostgreSQL 数据卷 `pgdata` 已配置，但备份恢复文档不完整。
**建议修复**: 在 deployment.md 中补充 `pg_backup.sh` 的定时执行配置（cron）。

---

### P3 — 优化建议（性能 / 可维护性）

#### P3-1: Step5 订单查询可加索引优化

**文件**: `backend/app/engine/step5_warehouse_split.py:89-106`
**现象**: 30 天窗口内的三表 JOIN 查询（OrderItem + OrderHeader + OrderDetail）可能随数据量增长变慢。
**建议**: 确保 `OrderHeader(purchase_date, order_status)` 和 `OrderDetail(shop_id, amazon_order_id)` 有复合索引。

---

#### P3-2: 引擎 Runner 可添加 dry-run 模式

**现象**: 当前引擎运行必然写入 DB（归档旧建议 + 创建新建议）。调试时无法仅看计算结果。
**建议**: 添加 `dry_run=True` 参数，跳过 `_persist_suggestion`，返回计算结果 dict。

---

#### P3-3: 前端可引入 Playwright E2E 测试

**现象**: 前端仅有单元测试，无 UI 集成测试。
**建议**: 使用 Playwright 对 docker-compose dev 环境跑 E2E（登录 → 建议单列表 → 编辑 → 推送流程）。

---

#### P3-4: 同步层可添加数据新鲜度告警

**现象**: 如果某个 sync job 连续失败，引擎仍然基于陈旧数据计算，用户无感知。
**建议**: 在引擎 runner 开始时检查关键 sync_state 的 last_success_at，如果超过阈值（如 24h），在 suggestion 上标注 warning 字段。

---

#### P3-5: rate_limit.py 可改为有限缓存

**文件**: `backend/app/saihu/rate_limit.py:11`
**现象**: `_LIMITERS` dict 是全局的，endpoint 数量是固定的（~7 个），所以不会真正泄漏。
**风险评估**: **低风险**——实际 endpoint 数量有限。但代码风格上建议改为 `functools.lru_cache` 或添加注释说明有界性。

---

#### P3-6: 密钥轮换 Runbook 缺失

**现象**: JWT_SECRET 和 SAIHU_CLIENT_SECRET 的轮换流程未文档化。
**建议**: 在 runbook.md 中补充密钥轮换步骤（停机窗口、双密钥过渡期）。

---

## 三、分层 Review 总评 (B: 静态审查)

### 架构评分

| 维度 | 评分 | 说明 |
|------|------|------|
| **链路完整度** | 9/10 | 从同步到计算到推送全链路打通，仅 P0-1 的国内库存逻辑需确认业务意图 |
| **计算正确性** | 7/10 | 核心公式正确，但取整不一致(P0-2)和 PATCH 校验缺失(P0-3)需修复 |
| **并发安全** | 8/10 | Advisory lock + TOCTOU 保护到位，仅推送失败路径(P0-4)有缺口 |
| **错误恢复** | 7/10 | 同步层 UPSERT 保证幂等，但 delete-then-insert 和中间 commit 有风险 |
| **可观测性** | 6/10 | structlog + api_call_log 框架好，但引擎边界日志缺失 |
| **测试覆盖** | 7/10 | 后端 163 测试覆盖引擎主路径，但前端和边界覆盖不足 |
| **部署就绪** | 9/10 | Docker Compose + 健康检查 + 回滚脚本完整 |
| **代码质量** | 8/10 | 分层清晰、复用良好、命名规范。少数硬编码常量待提取 |

### 总评

这是一个工程成熟度较高的系统。核心链路从数据获取到补货建议生成的 6 步引擎设计清晰、职责分离。主要需要修复的是 4 个 P0 级别的数据正确性问题——它们不会导致系统崩溃，但会导致计算结果偏离预期。P1 级别的健壮性问题是防御性编程的缺失，在当前 1-5 人使用场景下出现概率低，但值得加固。

---

## 四、用户决策记录 + 修复路线图

### 用户决策

| 项 | 决策 | 备注 |
|---|------|------|
| P0-1 | ✅ By Design | 国内不参与扣减，invariant 正确，加注释 |
| P0-2 | ✅ 修复 | 统一 ceil 用于数量，round 仅用于日期偏移 |
| P0-3 | ✅ 修复 | 添加 model_validator 校验非负 |
| P0-4 | ✅ 修复 | 失败路径添加 push_status guard |
| P1-1 | ✅ 修复 | GlobalConfig 正值校验 |
| P1-2 | ✅ 修复 | 递归深度限制（风险极低但修改量小） |
| P1-3 | ✅ 方案 B | 改用 UPSERT 替代 delete-then-insert |
| P1-4 | ✅ 接受 | overlap 改为可配置 |
| P1-5 | ✅ 接受 | 记录已处理最后时间戳 |
| P1-6 | ✅ 修复 | 添加随机 jitter |
| P1-7 | ✅ 修复 | 容错返回 today |
| P1-8 | ✅ 标注 | 日志标注 reaper 实例 ID |
| P2-1 | ✅ 接受 | 引擎边界日志 |
| P2-2 | ✅ 补充 | 前端测试 |
| P2-3 | ✅ 补充 | 后端覆盖率 |
| P2-4 | ✅ 保持 90 天 | 加注释说明理由，暂不改为可配置 |
| P2-5~P2-10 | ✅ 接受 | 全部按建议修复 |
| P3-* | ✅ 接受 | 全部按建议排入 |

### 修复路线图

```
Phase 1 (立即 — 数据正确性):
  ├── P0-1: Step4 添加业务意图注释 (5min)
  ├── P0-2: 统一取整策略 ceil (30min)
  ├── P0-3: SuggestionItemPatch 非负校验 (20min)
  ├── P0-4: 推送失败路径 push_status guard (10min)
  └── P1-1: GlobalConfig 正值校验 (10min)

Phase 2 (短期 — 健壮性):
  ├── P1-2: enqueue_task 递归深度限制 (10min)
  ├── P1-3: 同步层改 UPSERT (评估 + 实施)
  ├── P1-4: overlap 可配置 (15min)
  ├── P1-5: 同步层时间戳追踪 (20min)
  ├── P1-6: Token 重试 jitter (5min)
  ├── P1-7: parse_purchase_date 容错 (10min)
  └── P1-8: Reaper 实例 ID 标注 (5min)

Phase 3 (中期 — 工程质量):
  ├── P2-1: 引擎边界日志 (30min)
  ├── P2-2: 前端测试补充
  ├── P2-3: 后端覆盖率提升至 70%
  ├── P2-4: 在途 90 天 cutoff 注释 (5min)
  ├── P2-5: allocation_mode 语义修正 (5min)
  ├── P2-6: zipcode 浮点比较修复 (10min)
  ├── P2-7: push 零数量过滤 (5min)
  ├── P2-8~P2-10: 文档补充
  └── P3-*: 优化项
```
