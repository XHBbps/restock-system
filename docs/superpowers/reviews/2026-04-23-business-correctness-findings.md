# Business Correctness Audit — 2026-04-23

> 聚焦 step1-6 引擎公式、时区、空集合、EU 映射、幂等性的窄向审查。覆盖 2026-04-21 audit 未触及的维度。

## 范围

- `backend/app/engine/*`（6 step + runner + context）
- `backend/app/core/country_mapping.py` / `restock_regions.py` / `timezone.py`
- `backend/app/api/config.py` — `patch_global` + `patch_generation_toggle`

## 方法

静态代码阅读 + 对比现有 test 是否覆盖边界。

---

## Findings

### Critical (0 / 必须立即修)

无。

---

### Important (2 / 建议近期修)

- **[TZ-01] step6_timing 独立入口使用 `date.today()` 而非北京时间**
  - 证据：`backend/app/engine/step6_timing.py:82,106`
    ```python
    effective_today = today or date.today()
    ```
    出现在 `compute_urgency_for_sku` 和 `step6_timing` 两处。
  - 影响：`runner.py` 调用时明确传入 `today = now_beijing().date()`，生产路径正确。但 `step6_timing(...)` 作为独立函数对外暴露，若未来被其他调用方调用（或在测试/脚本中直接调用而不传 `today`），会拿系统本地时区的日期，在 UTC+0 服务器上与北京时间最多差 8 小时，可能导致 `purchase_date` 偏差最多 ±1 天，urgent 判断错误。
  - 建议：将默认值改为 `today or now_beijing().date()`，或在函数签名中去掉默认值强制调用方显式传入。

- **[SYNC-01] `order_list.sync_order_header` 在 `purchaseDate` 缺失时 fallback 为 `now_beijing()`**
  - 证据：`backend/app/sync/order_list.py:135`
    ```python
    purchase_date = parse_saihu_time(raw.get("purchaseDate"), marketplace_id_raw) or now_beijing()
    ```
  - 影响：若赛狐 API 返回的订单缺少 `purchaseDate`（异常响应或字段改名），该订单会以当前同步时刻存储，并落入 step1 的 30 天滑动窗口，错误地贡献当日动销，抬高 velocity，进而虚增采购量。这不是引擎本身的 bug，而是上游入库的边界处理。
  - 建议：对缺失 `purchaseDate` 的订单记录结构化警告日志并**跳过写入**（`return 0`），或在 step1 的 `load_velocity_inputs` 中增加对异常未来/极远过去日期的过滤（如 `purchase_date > end_dt - 2*WINDOW_DAYS`）。

---

### Minor (2 / 可选修)

- **[STEP4-01] `compute_total` 中 `velocity_for_sku` 未与 `country_qty_for_sku` 取交集**
  - 证据：`backend/app/engine/step4_total.py:46-51` — `sum_velocity = sum(velocity_for_sku.values())`。Runner 传入的是 `velocity.get(sku, {})`（全国家 velocity，不受 restock_regions 过滤），而 `country_qty_for_sku` 已按白名单过滤。
  - 影响：这是**设计意图**（已在 runner.py:84-85 注释说明 "Σvelocity 须覆盖所有国家"），测试 `test_run_engine_velocity_unaffected_by_restock_regions` 也覆盖了该场景。此条记录为"明确设计"，见 Ack 节。但 `step4.py` 内部无注释解释为何 velocity 覆盖非白名单国家，可增加一行注释防止误删。
  - 建议：在 `compute_total` 或 `step4_total.py` 头部加注释，明确 `velocity_for_sku` 应为全国家聚合（不含白名单过滤）。

- **[STEP2-01] `load_oversea_inventory` 未过滤 `commodity_skus` 不在 sku_list 的边界**
  - 证据：`backend/app/engine/step2_sale_days.py:39-42` — `if commodity_skus is not None: stmt = stmt.where(...)` 为空列表时不过滤，直接查全表。
  - 影响：当 `commodity_skus=[]` 时（理论上 runner 在 `not sku_list` 时已早返），step2 会全表扫描 `inventory_snapshot_latest`，返回无用数据。runner 在传入 `[]` 前已通过 `if not sku_list: return None` 保护，当前路径安全，但防御性弱。
  - 建议：在 `load_oversea_inventory` / `load_in_transit` 开头加 `if commodity_skus is not None and not commodity_skus: return {}` 短路保护。

---

### Ack（明确不修）

1. **[TZ-02] 跨时区 marketplace 的 purchase_date 归日期**
   - 分析：`parse_saihu_time` 已将各站点时区（US/PST、JP/JST 等）转为 `Asia/Shanghai` 存储；`load_velocity_inputs` 用 `func.timezone("Asia/Shanghai", purchase_date)` 在 DB 侧再转一次提取日期，两道转换均正确。PostgreSQL 的 `TIMESTAMPTZ` 列在存储时已绝对化，`func.timezone` 转换无歧义。无跨午夜归日期错误风险。

2. **[EMPTY-01] `restock_regions=[]` vs `restock_regions=None` 语义**
   - 分析：`resolve_allowed_restock_regions` 对两者均返回 `None`（"不过滤"），runner.py:93-99 用 `if allowed_countries is not None` 判断，语义一致。`normalize_restock_regions(None)` 返回 `[]`，进而 `resolve` 返回 `None`，行为正确。

3. **[EMPTY-02] `eu_countries=[]` 时 `apply_eu_mapping` 退化为恒等**
   - 分析：`apply_eu_mapping(country, set())` 当 `country not in set()` 时原样返回，已有测试 `test_apply_eu_mapping_empty_eu_set_is_identity`。行为正确，无需修。

4. **[EMPTY-03] 某 SKU 无任何 order 时 velocity 不在返回 dict 中**
   - 分析：`aggregate_velocity_from_items` 只对出现在 `daily` 中的 (sku, country) 对生成 velocity；全无有效 order 的 SKU 不会进入 velocity dict，runner 中 `velocity.get(sku, {})` 返回空字典，`sum_velocity=0`，`buffer_qty=0`，`purchase_qty = sum_qty + 0 - local + safety_qty`，符合业务预期。

5. **[EMPTY-04] `total_qty=0` 且 `purchase_qty=0` 时 runner 早退跳过**
   - 分析：`runner.py:127` — `if purchase_qty <= 0 and restock_total <= 0: continue`，双零条件下不插入，语义正确。

6. **[STEP1-01] refund > shipped 时记 0**
   - 分析：`eff = max(int(shipped or 0) - int(refund or 0), 0)`，已有测试 `test_aggregate_refund_subtracted` 覆盖 `refund > shipped → 0` 场景。

7. **[STEP2-02] velocity=0 时 sale_days 除零保护**
   - 分析：`compute_sale_days` 中 `if v <= 0: continue`，不产生除零，已有测试覆盖。

8. **[STEP2-03] total=0 时 sale_days=0**
   - 分析：stock.total=0 且 v>0，`sale_days = 0/v = 0`，语义正确（无库存即库存耗尽时间为 0）。

9. **[STEP6-01] `min()` 空序列崩溃**
   - 分析：`compute_purchase_date` 中已有 `if not valid: return None` 保护，在 `min(valid)` 之前 guard，无崩溃风险，已有测试 `test_step6_no_purchase_date_when_no_sale_days` 覆盖。

10. **[EU-01] `apply_eu_mapping(None, eu_countries)` 返回 None**
    - 分析：`apply_eu_mapping` 第一行 `if country is None: return None`，行为正确，测试 `test_apply_eu_mapping_none_input_returns_none` 覆盖。

11. **[EU-02] `original_country_code` 在 step1 聚合时被误用**
    - 分析：step1 `load_velocity_inputs` 直接读 `OrderHeader.country_code`（已是 EU 映射后的值），不读 `original_country_code`，聚合按已映射国家进行，正确。

12. **[IDEMPOTENT-01] `generation_toggle` 并发翻转保护**
    - 分析：`patch_generation_toggle` 使用 `select(...).with_for_update()`（`api/config.py:308`），会话级行锁防止并发双写，行为正确。

13. **[IDEMPOTENT-02] `retention_purge` 连跑 2 次幂等性**
    - 分析：`purge_task_run` / `purge_inventory_history` 基于时间条件 DELETE，第 2 次匹配不到行，rowcount=0，无副作用。`purge_exports` 有 `WHERE file_purged_at IS NULL` 过滤，第 2 次无新行，幂等。`purge_stuck_generating` 有 `WHERE generation_status='generating'` 过滤，第 2 次已标 failed，幂等。

14. **[IDEMPOTENT-03] `run_engine` advisory lock 串行化**
    - 分析：`SELECT pg_advisory_xact_lock(:key)` 在事务开始时获取，ENGINE_RUN_ADVISORY_LOCK_KEY=7429001 稳定（有测试覆盖），串行化有效。

15. **[HIST-01] 历史 `purchase_qty < 0` 已修复**
    - 分析：migration `20260422_1000` 已执行 `UPDATE suggestion_item SET purchase_qty = 0 WHERE purchase_qty < 0`，并加 `CheckConstraint`；engine 侧 `max(0, ...)` 双重保护。已修复，无遗留。

16. **[HIST-02] 历史 `generation_status='generating'` 卡死**
    - 分析：`purge_stuck_generating` 标记超过 `retention_stuck_generating_hours`（默认 1 小时）的 generating 行为 failed，由 `retention_purge_job` 每日 04:00 Cron 触发，覆盖 OOM/崩溃场景。

---

## 总结

引擎 step1-6 的核心业务公式（velocity 加权、sale_days 除零保护、country_qty 向上取整、purchase_qty clamping、warehouse fallback_even、purchase_date min() 保护）均正确实现且有测试覆盖。时区处理采用 PostgreSQL TIMESTAMPTZ + `func.timezone("Asia/Shanghai", ...)` 双重转换，EU 映射各同步入口行为一致，幂等性机制（advisory lock、with_for_update、幂等 DELETE 条件）完整。

最值得关注的 2 点：**[TZ-01]** `step6_timing` 独立入口的 `date.today()` 回退在未来被直接调用时会引入时区偏差；**[SYNC-01]** 赛狐 API 返回 `purchaseDate` 缺失时以当前时刻写入，可能污染 velocity 计算。两者在当前生产路径下均已被上游调用方传参规避，但防御性不足，建议近期补强。
