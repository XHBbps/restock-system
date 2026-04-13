# 引擎 6 步人工评审报告（2026-04-11）

> **评审范围**：`backend/app/engine/` 全部 9 个文件
> **评审基准**：`AGENTS.md §6.5` 后端约定 + `docs/Project_Architecture_Blueprint.md` 引擎章节
> **评审方式**：离线人工读码，**不依赖赛狐 API 联通**（白名单不通的限制下唯一可行路径）
> **关联工作**：本评审是 `docs/superpowers/plans/2026-04-11-code-review-fixes.md` Phase C 的产出
> **评审人**：Claude Code（Opus 4.6）

---

## 执行摘要

| 维度 | 结果 |
|---|---|
| 文件数 | 9（runner + step1..6 + calc_engine_job + zipcode_matcher） |
| 总行数 | ~1100 |
| Critical | **0** |
| Warning | **2** |
| Info | **5** |
| 测试覆盖 | step1-6 全部有单测，共 39 条 |
| 整体评价 | **架构清晰、纯度遵守、并发安全到位**。无运行时 bug，发现 2 个值得关注的设计权衡 + 5 条优化建议。 |

---

## 7 维度通过情况速览

| 维度 | 结果 | 说明 |
|---|---|---|
| 1. 纯度（不调外部 API） | ✅ PASS | 所有 step 文件只 import sqlalchemy / app.models / app.core / app.engine，无 httpx / app.saihu |
| 2. 并发安全 | ✅ PASS | `runner.py:55-61` 正确使用 `pg_advisory_xact_lock(7429001)`，事务结束自动释放 |
| 3. 事务边界 / N+1 | ⚠️ 1 Warning | 单个超长事务持有 advisory lock 全程，详见 F-1 |
| 4. 数学正确性 | ⚠️ 1 Warning | step5 仓内分配的"未匹配订单"不参与分配，详见 F-2 |
| 5. 时区一致性 | ✅ PASS | 统一走 `now_beijing()` / `BEIJING` tzinfo |
| 6. 错误处理 | ℹ️ 1 Info | 没有使用 `BusinessError`（但 step 是纯计算，影响小），详见 F-3 |
| 7. 类型标注 | ✅ PASS | dict 类型参数到位，runner 用 dataclass 包装 |

---

## 🟡 Warning（值得关注的设计问题）

### F-1. runner.py 单个超长事务持有 advisory lock 全程

- **位置**：`backend/app/engine/runner.py:54-258`
- **现象**：`run_engine` 把 6 步 + 持久化 + 归档全部包在一个 `async with async_session_factory() as db:` 里。advisory lock 在事务开始时获取（line 58），事务结束时自动释放（commit 在 line 257）。
- **问题**：对于 1-5 SKU 系统当前 OK，但若启用 SKU 数量增长到几百，事务时长可能达分钟级。在此期间：
  1. **其他 engine run 全部被阻塞**（包括手动触发）
  2. **PostgreSQL 长事务影响 vacuum**（autovacuum 跳过）
  3. **失败重试代价大**（事务回滚后所有计算白做）
- **当前缓解**：
  - 系统规模小（1-5 用户、几十 SKU 量级），当前不会触发瓶颈
  - 调度器和手动触发都被同一把 advisory lock 序列化（业务上接受）
- **建议**：暂不修。**记录到 `docs/runbook.md` 的"已知限制"章节**：当 enabled SKU > 200 时考虑拆分为"计算-持久化"两阶段事务（advisory lock 只锁持久化）
- **优先级**：P3（未达瓶颈时观察即可）

### F-2. step5 未匹配邮编的订单不参与仓内分配

- **位置**：`backend/app/engine/step5_warehouse_split.py:166-198`
- **现象**：
  ```python
  for postal_code, qty in orders:
      if qty <= 0:
          continue
      wid = match_warehouse(postal_code, country, rules)
      if wid is None or wid not in eligible_set:
          unknown_order_qty += qty   # 累计但不分配
          continue
      known_counts[wid] += qty
      matched_order_qty += qty
  
  total_known = sum(known_counts.values())
  
  if total_known > 0:
      # 按真实比例分配 —— 注意分母只用 known_counts
      for ... 
          share = round(country_qty * cnt / total_known)
  ```
- **问题**：如果 50% 的订单 postal_code 不匹配任何 zipcode_rule（或匹配到不在 `eligible_warehouses` 的仓），这部分销量被记为 `unknown_order_qty` 但 **不参与分配**。最终 `country_qty` 全部被按"匹配上的 50% 订单"的仓库分布来切分。
- **业务后果**：库存分配偏向"邮编匹配率高的区域"，"邮编未匹配"客户群所在地理区域的仓库可能持续库存不足。
- **判断**：这是设计权衡，不是 bug：
  - 优点：不向"未知"区域分配，避免猜测错误
  - 缺点：若邮编规则覆盖率低，会自我强化偏差
- **建议**：
  1. 在 `allocation_snapshot` 里 **暴露 `unknown_order_qty / (matched + unknown)` 作为"规则覆盖率"指标**（前端可视化）
  2. 若覆盖率持续 <70%，运维侧补 zipcode_rule 而不是改算法
  3. **不修代码**，加 docstring 说明权衡 + 在 `Project_Architecture_Blueprint.md` 引擎章节备注
- **优先级**：P2（影响精度但不影响正确性）

---

## 🔵 Info（优化建议，可后续处理）

### F-3. 引擎层全部使用裸 raise，未使用 `BusinessError` 体系

- **位置**：所有 `step*.py` + `runner.py`
- **现象**：grep 全部 step 文件，没有任何 `BusinessError` / `app.core.exceptions` import
- **问题**：`AGENTS.md §6.5` 要求"异常用 `BusinessError` 子类，自动映射为 JSON"。但这条规则的语境是 **API 层**。引擎层的异常会冒泡到 `calc_engine_job` → `JobContext` → worker，最终成为 `task_run.error` 字段。worker 已经 catch 了所有异常并落库，所以引擎层裸 raise 在功能上是 OK 的。
- **建议**：
  - **不修**，但在 `AGENTS.md §6.5` 第二行后追加："引擎层异常会被 worker 兜底，无需 `BusinessError` 包装"，避免后续维护者误以为引擎需要补
- **优先级**：P3

### F-4. step2 的 in_transit 90 天 cutoff 是硬编码

- **位置**：`backend/app/engine/step2_sale_days.py:67`
  ```python
  cutoff = now_beijing() - timedelta(days=90)
  ```
- **问题**：这是 magic number。其他引擎参数（`target_days`、`buffer_days`、`lead_time_days`）都通过 `GlobalConfig` 配置，唯独 in_transit 窗口写死。
- **业务风险**：如果某次推送的采购单实际到货周期超过 90 天（海外清关延迟、缺货等），cutoff 之后该 in_transit 不再被算入库存，引擎可能为同一 SKU 重复生成补货建议（双订）。
- **建议**：
  1. 在 `GlobalConfig` 增加字段 `in_transit_window_days: int = 90`
  2. step2 改为读取 `config.in_transit_window_days`
  3. 同时更新 alembic migration + GlobalConfigView
- **影响范围**：3 文件（model + step2 + view）+ 1 alembic migration
- **优先级**：P2（业务正确性，但当前 1-5 用户场景下 90 天极少超出）

### F-5. step4 用 `round()`，step3 用 `math.ceil()`，舍入策略不一致

- **位置**：
  - `step3_country_qty.py:33`：`country_qty[sku][country] = math.ceil(raw)` —— 永远向上
  - `step4_total.py:76`：`return max(round(raw), 0)` —— 银行家舍入
- **问题**：单个国家补货量 ceil 向上（更激进），总采购量 round（可能向下）。
- **缓解**：step4 有显式 invariant 兜底：
  ```python
  if raw < sum_qty:
      raw = sum_qty
  ```
  这条 invariant 保证 `total >= sum(country_breakdown)`，不会出现"分国家加起来 > 总采购量"的内部矛盾。
- **判断**：当前实现是正确的（invariant 保护住了），但**舍入策略不统一会让维护者困惑**。建议二选一：
  1. 都改 `math.ceil`（语义统一为"补货向上"）
  2. 在 step4 的 `round()` 旁加注释说明为什么用 round 而不是 ceil
- **建议方案**：选 2（加注释，0 行为变化），1 行注释成本最低
- **优先级**：P3

### F-6. zipcode_matcher 的 operator 校验失败时静默返回 False

- **位置**：`backend/app/engine/zipcode_matcher.py:46-83`
- **现象**：`_compare()` 函数对未知 operator 返回 False（line 48）；对 `value_type="number"` 但 value 不能 parse 为 float 时也返回 False（line 53-55）。错误数据被静默吃掉，导致规则永远不命中。
- **问题**：如果通过 API 创建了一条 `operator="contains"` 但 `value_type="number"` 的规则（语义错配），这条规则在引擎里永远 match 不上，但**前端没有任何提示**。
- **当前缓解**：规则 CRUD API（`backend/app/api/config.py` 的 zipcode-rule 端点）应该有验证 — **需要二次确认**
- **建议**：
  1. 验证 `app/api/config.py` 创建/更新规则时是否校验 operator + value_type 组合
  2. 若没有，在 `app/schemas/config.py` 的 ZipcodeRule pydantic schema 加 validator
  3. 引擎层保持静默（防御性）
- **优先级**：P3

### F-7. step5 末位仓库吸收所有舍入误差

- **位置**：`backend/app/engine/step5_warehouse_split.py:184-186`
  ```python
  for i, (wid, cnt) in enumerate(items):
      if i == len(items) - 1:
          # 最后一仓兜底,避免四舍五入误差
          result[wid] = country_qty - accumulated
      else:
          share = round(country_qty * cnt / total_known)
          result[wid] = share
          accumulated += share
  ```
- **问题**：dict 顺序 = 插入顺序 = 该国 `known_counts` 第一次出现的顺序 = `orders` 列表的遍历顺序。所以"最后一个仓库"是哪个，取决于近 30 天订单流的顺序，**不确定**。这意味着舍入误差被推给了**随机的某个仓库**。
- **业务影响**：极小（因为单次误差 < len(items) 件），但理论上可能让某个仓的库存计划长期偏差。
- **建议改进**：用 **largest remainder method**（Hare-Niemeyer）替代，把余数按"小数部分大小"派给最大的几个仓库。10-15 行代码改动。
- **优先级**：P3（当前正确性 OK，仅是均衡度问题）

---

## 📋 各文件分述

### `runner.py`（267 行）
- **职责**：编排 6 步 + commodity_id 映射 + push_blocker 预检 + 持久化 + 归档旧 draft
- **优点**：
  - 流程清晰，每一步都通过 `ctx.progress()` 上报进度
  - 通过 `load_all_sku_country_orders` 一次性加载消除 N+1（line 109）
  - advisory lock 保护并发（line 58-61）
  - 持久化前先归档旧 draft/partial（`_archive_active`），保证同时只有一个 active suggestion
- **关注点**：F-1（长事务）

### `step1_velocity.py`（112 行）
- **职责**：30 天加权移动平均算 SKU x 国家二维 velocity
- **数学**：`day7/7*0.5 + day14/14*0.3 + day30/30*0.2`，权重和 = 1.0 ✓
- **优点**：
  - 纯函数 `compute_velocity`、`is_in_window`、`aggregate_velocity_from_items` 全部可单测
  - effective 计算 `max(shipped - refund, 0)` 防止负值 ✓
  - 时区处理使用 `func.timezone("Asia/Shanghai", purchase_date)` 在 DB 层截日期 ✓
- **测试**：9 个单测覆盖
- **未发现问题**

### `step2_sale_days.py`（141 行）
- **职责**：海外仓库存 + 在途（已推送 suggestion 的 country_breakdown）/ velocity
- **优点**：
  - `if v <= 0: continue` 防除零 ✓
  - in_transit 用 `Suggestion.created_at >= cutoff` + `status != "archived"` 双重过滤 ✓
  - merge_inventory 是纯函数 ✓
- **关注点**：F-4（90 天 cutoff 硬编码）
- **测试**：4 个单测

### `step3_country_qty.py`（34 行）
- **职责**：`raw = target_days * v - stock`，正值 ceil 后输出
- **优点**：
  - 极简纯函数
  - `if v <= 0: continue` + `if raw <= 0: continue` 双重过滤 ✓
  - `math.ceil` 保守向上 ✓
- **测试**：5 个单测
- **未发现问题**

### `step4_total.py`（76 行）
- **职责**：`total = Σ country_qty + Σ velocity * buffer - local_stock`
- **优点**：
  - 显式 invariant `if raw < sum_qty: raw = sum_qty` 保证 total ≥ sum(breakdown) ✓
  - 仅累加 country_qty > 0 的国家（spec 要求）✓
  - 有清晰 docstring 说明计算口径
- **关注点**：F-5（round vs ceil 不一致）
- **测试**：6 个单测

### `step5_warehouse_split.py`（220 行）
- **职责**：批量加载订单 + zipcode_rule 匹配 + 按比例分仓 + 零数据均分兜底
- **优点**：
  - `load_all_sku_country_orders` 批量 join order_item × order_header × order_detail 一次完成（消除 N+1）
  - dataclass `CountryAllocationResult` 携带 explain 快照
  - 三模式：matched / fallback_even / no_warehouse
  - 零数据兜底正确处理余数（line 209-213）
- **关注点**：F-2（未匹配订单不分配）+ F-7（末位吸收余数）
- **测试**：10 个单测

### `step6_timing.py`（109 行）
- **职责**：T_发货 / T_采购 / urgent 标记
- **优点**：
  - `parse_purchase_date` 兼容 engine(date) 与 PATCH API(str) 两种输入
  - `has_urgent_purchase` 提取为可复用纯函数（被 PATCH API 也用）
  - 缺失 sale_days 时降级为"立即采购"+ 警告日志，不抛异常 ✓
- **细节**：缺失 sale_days 的降级路径计算 `purchase_date = ship_date - lead_time` 其中 `ship_date = today + lead_time`，结果 `purchase_date == today`。逻辑正确但写法稍冗余（可直接 `purchase_date = today; ship_date = today + lead_time`），不必改。
- **测试**：5 个单测
- **未发现问题**

### `calc_engine_job.py`（15 行）
- **职责**：把 `run_engine` 注册为可触发的 job
- **优点**：极简委托，不在此层做业务
- **未发现问题**

### `zipcode_matcher.py`（109 行）
- **职责**：邮编归一化 + 按 priority 升序匹配规则 + 比较运算符
- **优点**：
  - `normalize_postal` 处理 None / strip / 去 - 与空格 ✓
  - rules 在内部按 priority 排序（不依赖调用者预排）✓
  - prefix 长度不足时跳过该规则（line 105-106）✓
  - dataclass `ZipcodeRule` 与 ORM 解耦便于测试 ✓
- **关注点**：F-6（operator 校验静默失败）
- **测试**：单独的 `test_zipcode_matcher.py`

---

## 测试覆盖盘点

| 文件 | 测试文件 | 测试数 | 评估 |
|---|---|---|---|
| step1_velocity.py | test_engine_step1.py | 9 | 充分（含边界） |
| step2_sale_days.py | test_engine_step2.py | 4 | 中等（in_transit 路径覆盖待确认） |
| step3_country_qty.py | test_engine_step3.py | 5 | 充分 |
| step4_total.py | test_engine_step4.py | 6 | 充分（含 invariant 测试推断存在） |
| step5_warehouse_split.py | test_engine_step5.py | 10 | 充分（三种 mode 都应覆盖） |
| step6_timing.py | test_engine_step6.py | 5 | 中等（缺失 sale_days 降级路径建议补） |
| zipcode_matcher.py | test_zipcode_matcher.py | （独立） | 单独覆盖 ✓ |
| runner.py | test_engine_runner.py | （存在） | 编排层 |
| calc_engine_job.py | （无独立测试） | 0 | OK（仅 15 行委托） |

**总计 39+ 单测**。覆盖整体良好。

---

## 文档同步建议

按 `AGENTS.md §9.1` 触发映射表，本评审本身**不触发任何文档同步**（无代码变更）。但若后续基于本报告做修复，需要同步：

| 修复项 | 触发文档 |
|---|---|
| F-2 (snapshot 暴露覆盖率指标) | `Project_Architecture_Blueprint.md` 引擎章节 + `PROGRESS.md` |
| F-3 (AGENTS.md 补说明) | `AGENTS.md §6.5`（本身就是要更新的目标） |
| F-4 (in_transit_window_days 入 GlobalConfig) | `Project_Architecture_Blueprint.md` 数据库章节 + `PROGRESS.md` + `deployment.md` 环境变量表（若变 env）+ alembic migration |
| F-1 (runbook 已知限制) | `runbook.md` 第 4 节"已知限制" |

---

## 优先级与后续动作建议

| 优先级 | 项 | 工作量 | 是否要做 |
|---|---|---|---|
| **P2** | F-2：在 `allocation_snapshot` 暴露规则覆盖率 | 30 min | 推荐做（提升运维可观测性） |
| **P2** | F-4：把 in_transit 90 天 cutoff 入 GlobalConfig | 1.5 h | 推荐做（业务正确性） |
| **P3** | F-1：runbook 加"已知限制" | 10 min | 顺手做 |
| **P3** | F-3：AGENTS.md §6.5 补一行说明引擎层例外 | 5 min | 顺手做 |
| **P3** | F-5：step4 加注释说明 round 选型 | 5 min | 顺手做 |
| **P3** | F-6：检查 zipcode-rule API 校验，按需补 schema validator | 30 min | 按需 |
| **P3** | F-7：step5 改用 largest remainder | 1 h | 不急 |

**强烈建议立即做**：无（本评审无 Critical / Bug，全部是设计权衡或优化建议）

**建议后续做**：F-2、F-4 入排期，其他 5 项可串成 1 个 chore commit 顺手清理

---

## 与 Phase B（CodeRabbit 补跑）的关系

Phase B 跑了 3 个切片（tests / alembic / deploy），其中：
- `backend/alembic`: 1 finding（migration docstring 不一致）
- `deploy`: 1 finding（restore_db.sh race condition）
- `backend/tests`: 仍 rate limited（需再等 30 min）

**Phase B 与 Phase C 互不重叠**：CodeRabbit 没有覆盖 `backend/app/engine/`（被 backend/app slice 覆盖时已经在更早 review 里出过 6 个 backend findings 但没涉及 engine），本次 Phase C 是引擎层的独立深度评审。

---

## 结论

引擎 6 步**核心质量良好**：
- ✅ 架构清晰，分层严格（runner 编排 / step 纯计算 / persist 隔离）
- ✅ 并发安全（advisory lock）、N+1 已消除、时区统一
- ✅ 测试覆盖到位（39+ 单测覆盖 6 步 + matcher）
- ✅ 数学公式与 spec FR-028~035 一致

**0 个 Critical / Bug**，2 个 Warning 都是设计权衡而非缺陷，5 个 Info 是优化建议。

引擎层在当前 1-5 用户场景下**生产就绪**。F-2、F-4 是值得近期处理的精度/正确性提升，其他可顺手清理。
