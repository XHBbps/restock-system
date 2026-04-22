# Agent A — 后端深度审计

> Stage 1 / Agent A（主会话手动执行，因 agent 2 次 API 断连失败）
> 问题总数：14 条 / Critical: 2 / Important: 7 / Minor: 5

---

## Q1 — 核心链路正确性

### 问题 #1 — `compute_total` 可返回负数，DB 列无 CheckConstraint

- 严重度：**Critical**
- 位置：`backend/app/engine/step4_total.py:55-66` + `backend/app/models/suggestion.py:77-102,124`
- 现状：`purchase_qty = sum_qty + buffer_qty - local_total + safety_qty` 无 clamp。当 `local_total > sum_qty + buffer_qty + safety_qty`（本地库存过剩）时返回负整数。`SuggestionItem.purchase_qty` Mapped 为 `Integer, nullable=False, default=0`，`__table_args__` 只有枚举 CheckConstraint，**没有 `purchase_qty >= 0`**。持久化后前端会展示负数；Session-context 提到的 `ef427ea` 仅加了 API 层 `SuggestionItemPatch` 的 `ge=0`，runtime engine 写入路径未覆盖。
- 建议：`compute_total` 末尾 `return max(0, int(purchase_qty))`；同时在 `suggestion_item` 表加 `CheckConstraint("purchase_qty >= 0", name="purchase_qty_non_negative")`，alembic 迁移里先做 `UPDATE suggestion_item SET purchase_qty = 0 WHERE purchase_qty < 0` 修复现有脏数据再加约束。
- 工作量：S（代码 + 迁移 + 测试各 1 条 unit 边界）

### 问题 #2 — `docs_enabled()` 在生产仍可被 env 开启

- 严重度：**Critical**
- 位置：`backend/app/config.py:24,69-72`
- 现状：
  ```python
  app_docs_enabled: bool | None = None
  def docs_enabled(self) -> bool:
      if self.app_docs_enabled is not None:
          return self.app_docs_enabled       # ← env override 优先于 app_env 检查
      return self.app_env != "production"
  ```
  pydantic-settings 会把 `APP_DOCS_ENABLED=true` env 解析成 `True`，于是 production 也返回 `True`。dev 容器在 `deploy/docker-compose.dev.yml` 中显式设 `APP_DOCS_ENABLED: ${APP_DOCS_ENABLED:-true}`，测试继承了这个 env → `test_docs_disabled_by_default_in_production` 失败（Stage 0 唯一真实业务失败）。生产安全视角：如果 prod env 被误配成 `APP_DOCS_ENABLED=true`，`/docs` 和 `/openapi.json` 会对外暴露。
- 建议：要么让 production 强制忽略 env override —
  ```python
  def docs_enabled(self) -> bool:
      if self.app_env == "production":
          return False
      if self.app_docs_enabled is not None:
          return self.app_docs_enabled
      return True
  ```
  要么在 `validate_settings` 里对 production + `app_docs_enabled=True` 组合显式报错。测试端也顺便 `monkeypatch.delenv("APP_DOCS_ENABLED", raising=False)` 确保再次独立。
- 工作量：S

### 问题 #3 — EU 映射覆盖完整 ✅ 非问题，记录确认

- 严重度：Minor（信息项，非待办）
- 位置：`backend/app/sync/{inventory,order_list,out_records,product_listing}.py` + `backend/app/core/country_mapping.py`
- 现状：4 个 sync 入口全部调用 `apply_eu_mapping(..., eu_countries or set())` 且启动时 `load_eu_countries` 一次复用，符合 `country_mapping.py` 文档约定。`warehouse.py` 不调用 EU 映射也是 by design（session-context 决策 #2）。
- 建议：无需修改；此条仅记录审计已验证，避免后续 reviewer 重复查。
- 工作量：—

### 问题 #4 — 引擎 advisory lock key 是 magic number 无注释

- 严重度：Minor
- 位置：`backend/app/engine/runner.py:32,40`
- 现状：`ENGINE_RUN_ADVISORY_LOCK_KEY = 7429001`（txn 级 `pg_advisory_xact_lock`）保证引擎串行执行逻辑正确，但 `7429001` 来历不明。如果将来加另一种 advisory lock，很难判断有没有冲突。
- 建议：改成集中的 `backend/app/core/locks.py` 模块，用 Enum/常量块统一声明所有 advisory lock key，附注释说明用途；文档建议使用 `pg_advisory_xact_lock(classid, objid)` 双参数形式，第一个参数编码模块、第二个参数编码具体资源。
- 工作量：S

---

## Q2 — 后端技术债

### 问题 #5 — `api/suggestion.py` 单文件 399 行，承担多个职责

- 严重度：Important
- 位置：`backend/app/api/suggestion.py`
- 现状：含 list / current / detail / patch / archive / delete 全部 endpoint + 5 个 helper + 2 个 scalar subquery factory + 排序工具。逻辑分散但耦合于一个 router。Stage 0 mypy 5 条连续错误也集中在此文件（sort_map 类型声明）。
- 建议：拆 `api/suggestion/` 包：
  - `__init__.py`：APIRouter + include_router
  - `list_endpoint.py`：`list_suggestions` + `_apply_suggestion_sort` + sort_map + 快照 subquery
  - `detail.py`：`get_current_suggestion` / `get_suggestion` / `_build_detail` / `_enrich_item`
  - `mutation.py`：`patch_item` / `archive_suggestion` / `delete_suggestion` / `_resolve_effective_lead_time_days`
  - `common.py`：`_derive_display_status` / `_snapshot_counts_for_suggestion`
  
  保留原路径向前兼容需求低，拆包即可。
- 工作量：M

### 问题 #6 — `api/suggestion.py:44-54` 排序 dict 类型声明不协变，5 条 mypy dict_item 错误

- 严重度：Important
- 位置：`backend/app/api/suggestion.py:45`
- 现状：
  ```python
  sort_map: dict[str, tuple[ColumnElement[object], ...]] = {
      "id": (Suggestion.id,),               # InstrumentedAttribute[int]
      "created_at": (Suggestion.created_at,),
      ...
  }
  ```
  SQLAlchemy 的 `InstrumentedAttribute[int]` 运行时是 `ColumnElement` 子类，但 mypy 类型体系下不协变于 `ColumnElement[object]`。真实运行 OK（也有充分测试覆盖），是类型**声明**问题不是**代码**问题。
- 建议：改为 `dict[str, tuple[ColumnElement[Any], ...]]` 或 `Mapping[str, Sequence[Any]]`；也可以 import `Any` 后直接 `dict[str, tuple[Any, ...]]`。不要用 `# type: ignore`，宜留类型信息。
- 工作量：S

### 问题 #7 — `api/monitor.py:107,116-117` 把 SQLAlchemy Row 当 ORM 模型存字典

- 严重度：Important
- 位置：`backend/app/api/monitor.py:85-107,115-117`
- 现状：
  ```python
  last_call_per_endpoint: dict[str, ApiCallLog] = {}   # 类型标错
  ...
  last_rows = (await db.execute(text("..."))).all()
  for r in last_rows:
      last_call_per_endpoint[r[0]] = r  # type: ignore[assignment]
  ...
  last = last_call_per_endpoint.get(endpoint)
  last_status = "success" if last and last[1] == 0 else "failed"    # Row tuple indexing
  last_error = (last[2] if last else None) if last_status == "failed" else None
  ```
  实际存的是 `Row[tuple[endpoint, status, error_msg, called_at]]` tuple，不是 `ApiCallLog` ORM 实例。`type: ignore[assignment]` 掩盖了根本问题，后续 `last[1]` `last[2]` 下标访问触发 mypy 的 `Value of type "ApiCallLog" is not indexable`。
- 建议：显式 tuple 类型：`last_call_per_endpoint: dict[str, tuple[str, int, str | None, datetime]] = {}`；删除 `type: ignore`；下标访问改具名 `last.endpoint` / `last.status`（如果用 ORM）或保持 tuple 索引但注解正确。
- 工作量：S

### 问题 #8 — mypy 其余 ~40 条错误多为 SQLAlchemy 2.x 类型存根缺失，建议精准 ignore

- 严重度：Important
- 位置：全项目；主要热点 `app/tasks/worker.py:195,232`、`app/tasks/jobs/daily_archive.py:41,54`（`Result.rowcount` 缺属性）、`app/sync/order_list.py:158`（`ReturningInsert.on_conflict_do_update` 缺属性）、`app/tasks/scheduler.py:7-9` / `app/tasks/queue.py:12`（apscheduler / asyncpg 缺 stubs）
- 现状：这些都不是代码缺陷，是 SQLAlchemy 2.x + asyncpg + apscheduler 的静态类型定义未完整。但项目 CI 如果跑 mypy strict 会全红。
- 建议：分类处置 —
  - SQLAlchemy `Result.rowcount` / `ReturningInsert.on_conflict_do_update`：加 `# type: ignore[attr-defined]`（精准到行）
  - 第三方库缺 stubs（apscheduler/asyncpg）：`pyproject.toml` 的 `[[tool.mypy.overrides]]` 加 `module = ["apscheduler.*", "asyncpg.*"]` + `ignore_missing_imports = true`
  - `step6_timing.py:111` `sale_days_for_sku` 类型：调用点把 `dict[str, float | None]` 传给期望 `dict[str, float]` 的函数 — 改函数签名接受 `Mapping[str, float | int | None]`（与现有 `has_urgent_sale_days` 一致），或在调用点过滤 None
- 工作量：M（一次性清扫）

### 问题 #9 — `api/monitor.py:85-105` 使用原生 `text()` SQL

- 严重度：Minor
- 位置：`backend/app/api/monitor.py:85-105`
- 现状：用 `text()` 写原始 SQL 查询调用日志聚合，`:endpoints` / `:since` 已参数化（无注入风险）。但相对 SQLAlchemy Core 表达方式，后续维护者难读，ORDER BY 列名硬编码。
- 建议：改写为 SQLAlchemy Core（`select` + `over()` / `row_number()` 实现 "每 endpoint 取最近一条"），或抽成 CTE 辅助函数。不紧急。
- 工作量：M

### 问题 #10 — `SuggestionItem.patch_item` 的 updates dict 用 `dict[str, Any]` 缺乏字段级类型

- 严重度：Minor
- 位置：`backend/app/api/suggestion.py:237`
- 现状：`updates: dict[str, Any] = {}` 聚合可变字段，最后 `update(SuggestionItem).values(**updates)`。pydantic `SuggestionItemPatch` 已做字段校验，runtime 没问题。但字段名 typo（比如把 `purchase_date` 写成 `purchase_dates`）在 mypy 阶段抓不到。
- 建议：改用 `TypedDict`（`SuggestionItemUpdate(TypedDict, total=False)`），或直接 `.values(**patch.model_dump(exclude_unset=True))` + 少数特殊字段的推导另处理（`allocation_snapshot` / `urgent`）。
- 工作量：S

### 问题 #11 — 引擎公式数据结构三层 dict 嵌套，可读性差

- 严重度：Minor
- 位置：`backend/app/engine/step3_country_qty.py`、`step4_total.py`、`runner.py` 全链路
- 现状：`velocity: dict[str, dict[str, float]]`（sku→country→value）、`inventory: dict[str, dict[str, dict[str, int]]]`（sku→country→{total/available/reserved}→int）等嵌套 3-4 层字典作为公式输入输出。功能正常但阅读时需要在大脑中持续维护 key 层级。
- 建议：用 `dataclass` 包装（比如 `VelocityByCountry`、`CountryInventory`），或至少用 `TypedDict` 为每层命名。不是紧急重构，但下次改公式时顺手做。
- 工作量：M

---

## Q3 — 后端死代码 / 清理

### 问题 #12 — 已删字段残留引用 ✅ 无

- 严重度：Minor（信息项）
- 位置：全项目
- 现状：`grep include_tax|calc_enabled|voided` 在 `backend/app/**` 全部 0 实质匹配。`voided` 唯一 hit 在 `api/suggestion.py:157` 的 `_derive_display_status` docstring 里解释历史含义（作为 `archived_trigger` 的历史值说明），属于文档保留。
- 建议：无需动作；此条记录审计已验证。
- 工作量：—

### 问题 #13 — `list_suggestions` 的 `total_snapshot_count_sq` 冗余但清晰

- 严重度：Minor
- 位置：`backend/app/api/suggestion.py:93,97,99`
- 现状：`total_snapshot_count_sq = procurement_snapshot_count_sq + restock_snapshot_count_sq` 这个合并值只在两处使用（`pending` / `exported` 分支）。两处都是 `total_snapshot_count_sq == 0` 和 `> 0`。非死代码但也可以内联 `(proc + restock) == 0`。保留它更清晰，可忽略。
- 建议：保持现状；未来若只用单类型判定，记得一并删这行。
- 工作量：—

### 问题 #14 — `app/saihu/**` / `app/tasks/worker.py` 覆盖率 0-36% 不代表死代码

- 严重度：Minor（信息项）
- 位置：`app/saihu/client.py`（0%）、`app/tasks/worker.py`（36%）、`app/tasks/reaper.py`（33%）、`app/tasks/scheduler.py`（47%）
- 现状：Stage 0 coverage < 50% 清单大部分是后台任务 loop（需要容器运行才覆盖）+ 第三方 API wrapper（需要 mock 层）。非死代码。
- 建议：Agent C 决定是否补 mock 测试；Agent A 不把它作为死代码上报。
- 工作量：—
