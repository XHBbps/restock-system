# Code Review Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按优先级修复 2026-04-11 CodeRabbit review 发现的问题（1 个 latent runtime bug、7 文件 mojibake、3 前端运行时隐患、EOL 归一化），然后补跑 3 个被 rate limit 拦截的 review 切片，最后人工评审引擎 6 步。

**Architecture:**
- **Phase A — 逐项修复（按优先级 P0→P3 顺序）**：每个 Task 遵循「先写/先看失败证据 → 修复 → 验证通过 → 单独 commit」。
- **Phase B — 补跑 CodeRabbit 剩余切片**：等待 rate limit 冷却（≥30 min）后跑 `backend/tests` / `backend/alembic` / `deploy` 三片。
- **Phase C — 人工评审引擎 6 步**：离线读取 7 个文件，产出与 CodeRabbit 同格式的结构化清单（不依赖赛狐 API 可连通）。

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy async / Pydantic v2 / pytest / Vue 3 / TypeScript / Vitest / Git

**Recovery Source Commits:**
- `data.py` 洁净版：`497ba2526669f199a1f8a97e6577f3f63cb1071c`
- 后续需要重叠的代码改动（在洁净版之上逐个重放）：
  - `ff7c876` `fix: replace undefined _Out alias with SkuOverviewListOut`
  - `a7a7227` `chore(mypy): add dict type args and targeted overrides`
  - `3976204` `feat(api): add pagination params to GET /api/data/warehouses`
  - `43b0665` `feat(api): add pagination params to GET /api/data/shops`

---

## Phase A: 按优先级修复

### Task 1: C-1 — 修复 `monitor.py` SQL 字符串中的误嵌 Python import

**Severity:** Critical / P0（已 commit 到 HEAD，latent runtime bug）

**Files:**
- Modify: `backend/app/api/monitor.py:86-96`
- Test: `backend/tests/unit/test_monitor_api.py`

**Background:**
`get_api_calls` 函数的第二个 `text()` SQL 首行夹了 `from typing import Any`，任何调用 `/api/monitor/api-calls` 且有 API 日志数据的请求都会触发 PostgreSQL `syntax error`。现有 test 里 `rows` 永远是空数组，因此永远不会进 `if rows:` 分支，bug 被掩盖。

- [ ] **Step 1: 添加回归测试（先让它失败）**

在 `backend/tests/unit/test_monitor_api.py` 文件末尾追加：

```python
@pytest.mark.asyncio
async def test_get_api_calls_last_call_sql_has_no_embedded_python_import() -> None:
    """Regression for code review C-1.

    Ensure the "last call per endpoint" text() SQL does not accidentally contain
    a Python import statement inside the string literal. Triggers the `if rows:`
    branch by providing a non-empty first rows result.
    """
    db = _FakeDb([
        _RowsResult([("GET /foo", 10, 8, None)]),  # non-empty -> enters if-branch
        _RowsResult([]),                            # the buggy last_rows query
        _ScalarResult(0),                           # postal_compliance
    ])

    await get_api_calls(hours=24, db=db, _={})  # type: ignore[arg-type]

    # The second executed statement is the text() last_rows SELECT DISTINCT ON.
    last_rows_stmt = db.executed[1]
    sql_text = str(last_rows_stmt).lower()
    assert "from typing import any" not in sql_text, (
        "SQL literal must not contain embedded Python import statement"
    )
    assert "select distinct on" in sql_text
```

- [ ] **Step 2: 跑新测试确认 FAIL**

```bash
cd backend
pytest tests/unit/test_monitor_api.py::test_get_api_calls_last_call_sql_has_no_embedded_python_import -v
```

Expected: FAIL，断言 `assert "from typing import any" not in sql_text` 失败（因为当前 SQL 字面量里就有这行）。

- [ ] **Step 3: 修复 `monitor.py` SQL 字面量**

Edit `backend/app/api/monitor.py`，将第 86-96 行替换为：

```python
            await db.execute(
                text(
                    """
                    SELECT DISTINCT ON (endpoint)
                        endpoint, saihu_code, saihu_msg, error_type
                    FROM api_call_log
                    WHERE endpoint = ANY(:endpoints) AND called_at >= :since
                    ORDER BY endpoint, called_at DESC
                    """
                ),
                {"endpoints": endpoint_names, "since": since},
            )
```

（关键：删掉 `from typing import Any` 那一行 + 它上面的空行。`typing.Any` 的 import 在文件顶部已存在，不需要重复。）

- [ ] **Step 4: 跑测试确认 PASS**

```bash
cd backend
pytest tests/unit/test_monitor_api.py -v
```

Expected: 所有 test_monitor_api 测试通过。

- [ ] **Step 5: 跑全量单元测试确保无回归**

```bash
cd backend
pytest tests/unit -q
```

Expected: 全绿。

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/monitor.py backend/tests/unit/test_monitor_api.py
git commit -m "fix(monitor): remove erroneous Python import from text() SQL literal

Regression: the 'last call per endpoint' text() SQL inside get_api_calls
had a stray 'from typing import Any' line inside the string, which would
raise PostgreSQL syntax error whenever the endpoint had any api_call_log
rows. Add regression test exercising the non-empty rows branch."
```

---

### Task 2: C-2a — 恢复 `backend/app/api/data.py` 的中文 docstring 与注释

**Severity:** Critical / P0

**Files:**
- Modify: `backend/app/api/data.py`
- Reference: `git show 497ba252:backend/app/api/data.py`（洁净源）

**Background:**
整个 `data.py` 的中文 docstring、section 注释、字段描述全部 mojibake（GBK-as-UTF8）。根本原因：commit `ff7c876` 在某次编辑时编辑器/系统编码配置错误，把 UTF-8 文件以 GBK 读取后又以 "UTF-8" 重写。后续 3 个 commit（`a7a7227`、`3976204`、`43b0665`）是在 mojibake 版本之上继续加代码的。

**Strategy:** 参考现有 `docs/superpowers/plans/2026-04-10-fix-suggestion-encoding.md` 的模式：**先回到洁净 commit 的版本，再把 4 个后续 commit 的纯代码改动重放上去**。

- [ ] **Step 1: 记录当前 mojibake 证据**

```bash
cd /e/Ai_project/restock_system
head -13 backend/app/api/data.py
```

Expected output 包含 `澶栭儴鏁版嵁婧愯娴` 等 mojibake 字符，确认当前状态确实损坏。

- [ ] **Step 2: 从洁净 commit 恢复整个文件**

```bash
git checkout 497ba252 -- backend/app/api/data.py
```

- [ ] **Step 3: 验证 docstring 已恢复为正确中文**

```bash
head -14 backend/app/api/data.py
```

Expected output:
```python
"""外部数据源观测 API。

READ-ONLY。所有端点从本地同步落库的表查询,返回与赛狐接口
基本一致的 camelCase 结构,供采购员排查"同步进来的数据是否正确"。

覆盖的 7 个资源:
- 订单列表 + 订单详情(order_header / order_item / order_detail)
- 库存明细(inventory_snapshot_latest JOIN warehouse)
- 其他出库(in_transit_record + in_transit_item)
- 仓库列表(warehouse)
- 店铺列表(shop)
- 在线产品信息(product_listing)
"""
```

- [ ] **Step 4: 查看 `ff7c876` 的代码变更并重放**

```bash
git show ff7c876 -- backend/app/api/data.py
```

这个 commit 的语义是：把对 `_Out` 别名的引用替换为 `SkuOverviewListOut`，并重排了几个 `await db.execute(...).scalars().all()` 的括号以通过 lint。

在当前 `data.py`（已是洁净版本）中定位 `list_sku_overview` 函数，按照 diff 的 `+` 行做相应替换：

1. 查找 `return _Out(items=[], ...)` → 改为 `return SkuOverviewListOut(items=[], ...)`
2. 查找 `return _Out(items=items, ...)` → 改为 `return SkuOverviewListOut(items=items, ...)`
3. 按 diff 调整 `await db.execute(...)` 的括号闭合位置（通常是把 `.scalars().all()` 拆到下一行）
4. 如果 `_Out` 别名在 schema 文件里没定义，该 commit 应该也在 `backend/app/schemas/data.py` 或等价处添加了 `SkuOverviewListOut` 导入 — 检查顶部 import。

- [ ] **Step 5: 查看 `a7a7227` 的代码变更并重放**

```bash
git show a7a7227 -- backend/app/api/data.py
```

这个 commit 给 dict annotation 加显式类型参数。定位 diff 中每处 `dict:` 或 `dict =` → 改为 `dict[str, Any]`（或 diff 里指定的具体类型）。

- [ ] **Step 6: 查看 `3976204` 的代码变更并重放**

```bash
git show 3976204 -- backend/app/api/data.py
```

这个 commit 给 `GET /api/data/warehouses` 加 `page` / `page_size` Query 参数。定位 `list_warehouses` 或同等函数，按 diff 添加 Query 参数和分页逻辑（`offset((page-1)*page_size).limit(page_size)` + 返回 `total`）。

- [ ] **Step 7: 查看 `43b0665` 的代码变更并重放**

```bash
git show 43b0665 -- backend/app/api/data.py
```

这个 commit 给 `GET /api/data/shops` 加同样的分页参数。定位 `list_shops` 并重复 Step 6 的模式。

- [ ] **Step 8: 确认没有 mojibake 残留**

```bash
grep -nP '[\x{e2ec}-\x{ffff}]' backend/app/api/data.py || echo "no high surrogate mojibake"
# 以及人工 grep 几个典型乱码字符
grep -n '澶栭儴\|鎺ュ彛\|缁撴瀯\|閲囪喘\|鏌ヨ\|璁㈠崟\|搴撳瓨\|浠撳簱\|搴楅摵\|鍦ㄧ嚎\|浜у搧\|淇℃伅' backend/app/api/data.py || echo "no mojibake"
```

Expected: 输出 `no mojibake`（如果 `grep` 到任何行，说明还有遗漏需补修）。

- [ ] **Step 9: 跑后端完整测试确认未破坏功能**

```bash
cd backend
pytest tests/unit -q
```

Expected: 全绿，尤其是 `test_data_order_detail_visibility.py`、`test_data_warehouses_api.py` 这些覆盖 data.py 的测试。

- [ ] **Step 10: 跑 mypy（项目启用）**

```bash
cd backend
mypy app/api/data.py
```

Expected: 无新增 error。若有，补全类型标注。

- [ ] **Step 11: Commit**

```bash
git add backend/app/api/data.py
git commit -m "fix(data): restore clean UTF-8 docstring and Chinese comments

The data.py module was corrupted from commit ff7c876 onward when an editor
wrote UTF-8 bytes through GBK codec. Restore from the last clean commit
(497ba252) and re-apply the legitimate code changes from ff7c876, a7a7227,
3976204, 43b0665 (all code-only, no comment edits were intended).

Fixes CodeRabbit review C-2."
```

---

### Task 3: C-2b — 修复 `docs/saihu_api/测试示例/` 下 6 个 md 文件的 mojibake

**Severity:** Critical / P0

**Files:**
- Modify: `docs/saihu_api/测试示例/02-warehouse-list.md`
- Modify: `docs/saihu_api/测试示例/03-warehouse-item-list.md`
- Modify: `docs/saihu_api/测试示例/04-out-records.md`
- Modify: `docs/saihu_api/测试示例/05-order-list.md`
- Modify: `docs/saihu_api/测试示例/06-order-detail.md`
- Modify: `docs/saihu_api/测试示例/07-purchase-create.md`

**Background:**
这 6 个文件的正文全部是英文，只有第 4 行 `- Source doc:` 引用了一个原始中文文件名，该文件名在诞生时（commit `614f9f8`）就已经是 mojibake。需要把 mojibake 文件名替换为对应的真实中文文件名。

**映射表**（从 `docs/saihu_api/` 实际存在的中文文件名推得）：

| mojibake md 文件 | 对应真实中文源文档 |
|---|---|
| `02-warehouse-list.md` | `查询仓库列表.md` |
| `03-warehouse-item-list.md` | `查询库存明细.md` |
| `04-out-records.md` | `其他出库列表页.md` |
| `05-order-list.md` | `订单列表.md` |
| `06-order-detail.md` | `订单详情.md` |
| `07-purchase-create.md` | `采购单创建.md` |

- [ ] **Step 1: 确认真实中文源文档都存在**

```bash
ls "docs/saihu_api/查询仓库列表.md" \
   "docs/saihu_api/查询库存明细.md" \
   "docs/saihu_api/其他出库列表页.md" \
   "docs/saihu_api/订单列表.md" \
   "docs/saihu_api/订单详情.md" \
   "docs/saihu_api/采购单创建.md"
```

Expected: 全部存在。若有缺失，从 git 历史找出对应文件名再映射。

- [ ] **Step 2: 批量修复 Source doc 字段**

逐文件用 Edit 工具精确替换第 4 行的 `- Source doc: ` 字段（**注意保留反引号**）：

`02-warehouse-list.md`:
```
- Source doc: `鏌ヨ浠撳簱鍒楄〃.md`  →  - Source doc: `查询仓库列表.md`
```

`03-warehouse-item-list.md`:
```
- Source doc: `鏌ヨ搴撳瓨鏄庣粏.md`  →  - Source doc: `查询库存明细.md`
```

`04-out-records.md`:
```
- Source doc: `鍏朵粬鍑哄簱鍒楄〃椤?md`  →  - Source doc: `其他出库列表页.md`
```

`05-order-list.md`:
```
- Source doc: `璁㈠崟鍒楄〃.md`  →  - Source doc: `订单列表.md`
```

`06-order-detail.md`:
```
- Source doc: `璁㈠崟璇︽儏.md`  →  - Source doc: `订单详情.md`
```

`07-purchase-create.md`:
```
- Source doc: `閲囪喘鍗曞垱寤?md`  →  - Source doc: `采购单创建.md`
```

> **注意**：每个文件的实际 mojibake 字符可能与上表的"左侧"不完全字对字一致，因为不同中文字符的 GBK→UTF-8 乱码后产生的字节序列不同。**以文件实际第 4 行内容为准**，使用 Read 先确认再 Edit。

- [ ] **Step 3: 验证所有 6 文件都已清理 mojibake**

```bash
grep -l '鏌ヨ\|鍒楄〃\|璁㈠崟\|搴撳瓨\|鍑哄簱\|閲囪喘\|鍒涘缓\|璇︽儏' docs/saihu_api/测试示例/*.md || echo "all md files clean"
```

Expected: `all md files clean`。

- [ ] **Step 4: Commit**

```bash
git add "docs/saihu_api/测试示例/"
git commit -m "docs(saihu): fix mojibake in Source doc references for test examples

The 6 test example files under docs/saihu_api/测试示例/ had garbled Chinese
file names in their Source doc field since they were first added in 614f9f8
(GBK-as-UTF8 mojibake). Replace with the real Chinese file names.

Fixes CodeRabbit review C-2 (docs scope)."
```

---

### Task 4: 新增 `.gitattributes` + 行尾归一化

**Severity:** Warning / P1

**Files:**
- Create: `.gitattributes`

**Background:**
仓库无 `.gitattributes`，`core.autocrlf=true`。`git diff` 展示 109 个文件被修改，但 `--ignore-all-space` 只有 89 文件、~200 行差异是纯 EOL 噪声。这批噪声污染了本次（以及未来）所有的 review / blame / merge。

- [ ] **Step 1: 创建 `.gitattributes`**

在仓库根创建 `.gitattributes`，内容：

```
# Default: detect text, normalize to LF on check-in
* text=auto eol=lf

# Force LF for Unix-native
*.sh text eol=lf
*.py text eol=lf
*.ts text eol=lf
*.tsx text eol=lf
*.vue text eol=lf
*.js text eol=lf
*.mjs text eol=lf
*.cjs text eol=lf
*.json text eol=lf
*.yaml text eol=lf
*.yml text eol=lf
*.md text eol=lf
*.scss text eol=lf
*.css text eol=lf
*.html text eol=lf

# Force CRLF for Windows-native scripts
*.ps1 text eol=crlf
*.bat text eol=crlf
*.cmd text eol=crlf

# Binary (never normalize)
*.png binary
*.jpg binary
*.jpeg binary
*.gif binary
*.ico binary
*.svg text eol=lf
*.pdf binary
*.zip binary
*.woff binary
*.woff2 binary
```

- [ ] **Step 2: 执行 `git add --renormalize .` 归一化**

```bash
git add --renormalize .
```

这会把所有被 `core.autocrlf` 处理过的文件重新 stage，使得 index 与 .gitattributes 规则一致。

- [ ] **Step 3: 查看受影响的文件**

```bash
git diff --stat --cached | tail -20
```

预期：看到一批文件显示被"修改"（但实际只是 EOL 变化）。

- [ ] **Step 4: 验证归一化后，非空白 diff 为零**

```bash
git diff --cached --stat --ignore-all-space | tail -5
```

Expected: 总行数变化 ≈ 0（或很小），因为 renormalize 本质就是 EOL 归一。

- [ ] **Step 5: 独立 commit（与功能改动严格隔离）**

```bash
git commit -m "chore(eol): add .gitattributes and normalize line endings

Repo previously had no .gitattributes and relied on core.autocrlf, causing
EOL drift between Windows and WSL environments. Declare explicit LF for
source files (Python/TS/Vue/SCSS/MD/...), CRLF for Windows scripts (*.ps1),
then run 'git add --renormalize .' once to align index with the new rules.

This is an EOL-only change — no semantic code modifications."
```

- [ ] **Step 6: 验证后续 `git status` 更干净**

```bash
git status --short | wc -l
```

Expected: 数量显著下降（应从 ~173 降到约 60-80，剩下的是真正的未提交功能代码）。

---

### Task 5: W-1/W-2/W-3 — 前端三个防御性修复

**Severity:** Warning / P1

**Files:**
- Modify: `frontend/src/views/SyncConsoleView.vue:153-159`
- Modify: `frontend/src/views/data/DataWarehousesView.vue:201-209`
- Modify: `frontend/src/views/PerformanceMonitorView.vue:164-179`

**Background:**
三个独立的防御性空数组/空对象处理，CodeRabbit 判定为 Warning。体量小，合并为一个 commit。

- [ ] **Step 1: 修复 W-1 — `SyncConsoleView.vue` heroAction 空守卫**

Edit `frontend/src/views/SyncConsoleView.vue` 行 153-159：

Before:
```ts
const heroAction = computed(() => {
  const action = manualSyncActions[0]
  return {
    action,
    ...getActionMeta(action),
  }
})
```

After:
```ts
const heroAction = computed(() => {
  if (manualSyncActions.length === 0) return null
  const action = manualSyncActions[0]
  return {
    action,
    ...getActionMeta(action),
  }
})
```

然后定位模板里引用 `heroAction` 的地方（`grep -n heroAction frontend/src/views/SyncConsoleView.vue`），给相应 DOM 节点加 `v-if="heroAction"` 守卫。

- [ ] **Step 2: 修复 W-2 — `DataWarehousesView.vue` reload 加 catch**

Edit `frontend/src/views/data/DataWarehousesView.vue` 行 201-209：

Before:
```ts
async function reload(): Promise<void> {
  loading.value = true
  try {
    const resp = await listDataWarehouses()
    rows.value = resp.items
  } finally {
    loading.value = false
  }
}
```

After（与同文件 `refresh()` 的错误处理风格一致）:
```ts
async function reload(): Promise<void> {
  loading.value = true
  try {
    const resp = await listDataWarehouses()
    rows.value = resp.items
  } catch {
    ElMessage.error('加载仓库列表失败')
  } finally {
    loading.value = false
  }
}
```

检查 `ElMessage` 已在文件顶部 import；若没有：`import { ElMessage } from 'element-plus'`。

- [ ] **Step 3: 修复 W-3 — `PerformanceMonitorView.vue` 空数组守卫**

Edit `frontend/src/views/PerformanceMonitorView.vue` 行 164-179，在 `.map(([label, values]) => {` 回调最前面加早返：

Before（简化版）:
```ts
.map(([label, values]) => {
  const sorted = [...values].sort((left, right) => left - right)
  const total = values.reduce((sum, value) => sum + value, 0)
  const p95Index = getPercentileIndex(sorted.length, 0.95)
  return {
    label,
    count: values.length,
    avgMs: (total / values.length).toFixed(2),
    p95Ms: sorted[p95Index].toFixed(2),
    maxMs: sorted[sorted.length - 1].toFixed(2),
  }
})
.sort(...)
```

After:
```ts
.map(([label, values]) => {
  if (values.length === 0) return null
  const sorted = [...values].sort((left, right) => left - right)
  const total = values.reduce((sum, value) => sum + value, 0)
  const p95Index = getPercentileIndex(sorted.length, 0.95)
  return {
    label,
    count: values.length,
    avgMs: (total / values.length).toFixed(2),
    p95Ms: sorted[p95Index].toFixed(2),
    maxMs: sorted[sorted.length - 1].toFixed(2),
  }
})
.filter((item): item is ResourceAggregateRow => item !== null)
.sort(...)
```

如果 `ResourceAggregateRow` 类型在本文件内不存在，改用就地推断：`.filter((item): item is NonNullable<typeof item> => item !== null)`。

- [ ] **Step 4: 跑 vue-tsc 类型检查**

```bash
cd frontend
npx vue-tsc --noEmit
```

Expected: 无 error。

- [ ] **Step 5: 跑 vite 构建**

```bash
cd frontend
npx vite build
```

Expected: 构建成功。

- [ ] **Step 6: 跑已有前端单测（顺便确认没回归）**

```bash
cd frontend
npm run test
```

Expected: 全绿。

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/SyncConsoleView.vue \
        frontend/src/views/data/DataWarehousesView.vue \
        frontend/src/views/PerformanceMonitorView.vue
git commit -m "fix(frontend): add defensive guards for empty arrays and missing error handling

- SyncConsoleView: guard heroAction against empty manualSyncActions
- DataWarehousesView: add catch + ElMessage.error to reload() to match
  the sibling refresh() pattern
- PerformanceMonitorView: skip aggregation rows with empty values array
  to avoid toFixed on undefined

Fixes CodeRabbit review W-1, W-2, W-3."
```

---

### Task 6: .gitignore 追加 `frontend/coverage/` 与 `pytest-cache-files-*`

**Severity:** Warning / P2

**Files:**
- Modify: `.gitignore`

**Background:**
- `frontend/coverage/` 是 Vitest 运行产出的 2.6MB HTML/JSON 覆盖率报告，不应入库
- `backend/pytest-cache-files-*` 是 pytest 6.x 的临时缓存目录（每次 run 生成新的随机后缀）

- [ ] **Step 1: 查看当前 .gitignore 相关段**

```bash
grep -n 'coverage\|pytest' .gitignore
```

- [ ] **Step 2: 追加两条规则**

Edit `.gitignore`，在合适的位置（通常在 frontend / backend 段下）添加：

```
# Vitest coverage output
frontend/coverage/

# pytest 6.x temp cache dirs with random suffix
backend/pytest-cache-files-*/
```

- [ ] **Step 3: 验证 `git status` 不再列出 coverage 目录**

```bash
git status --short | grep -E 'coverage|pytest-cache' || echo "clean"
```

Expected: `clean`。

- [ ] **Step 4: Commit**

```bash
git add .gitignore
git commit -m "chore(gitignore): exclude Vitest coverage and pytest temp cache dirs

- frontend/coverage/ (Vitest HTML/JSON report, 2.6MB generated)
- backend/pytest-cache-files-*/ (pytest 6.x random-suffix temp caches)"
```

---

### Task 7: I-1 — 删除 `AppLayout.vue` 重复 position 声明

**Severity:** Info / P3

**Files:**
- Modify: `frontend/src/components/AppLayout.vue:222-223`

- [ ] **Step 1: Edit 删除多余行**

Before:
```scss
.sidebar {
  position: relative;
  position: sticky;
  top: 0;
```

After:
```scss
.sidebar {
  position: sticky;
  top: 0;
```

- [ ] **Step 2: 构建确认**

```bash
cd frontend
npx vite build
```

Expected: 构建成功。

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/AppLayout.vue
git commit -m "style(AppLayout): remove redundant position: relative declaration

Immediately overridden by position: sticky. Fixes CodeRabbit review I-1."
```

---

## Phase B: 补跑 CodeRabbit 被 rate limit 拦截的 3 个切片

**Prerequisite:** Phase A 全部完成后，距离首次 rate limit 触发至少 30 分钟。首次被拦截时间约 `2026-04-11 03:43 UTC`，所以 ≥ `04:13 UTC` 之后再跑。

**Environment:** WSL（Ubuntu 24.04），`coderabbit` 在 `$HOME/.local/bin/`。

- [ ] **Step 1: 进入 WSL 并确认 coderabbit 可用**

```bash
wsl
export PATH="$HOME/.local/bin:$PATH"
cd /mnt/e/Ai_project/restock_system
coderabbit --version    # 期望 0.4.1
coderabbit auth status  # 期望 Logged in
```

- [ ] **Step 2: 跑 backend/tests 切片**

```bash
coderabbit review --plain -t uncommitted --dir backend/tests > /tmp/cr-tests.txt 2>&1
tail -20 /tmp/cr-tests.txt
```

Expected: 出现 `Review completed: N findings ✔` 或空结果。如果还被 rate limit，等 5 分钟重试。

- [ ] **Step 3: 跑 backend/alembic 切片**

```bash
coderabbit review --plain -t uncommitted --dir backend/alembic > /tmp/cr-alembic.txt 2>&1
tail -20 /tmp/cr-alembic.txt
```

- [ ] **Step 4: 跑 deploy 切片**

```bash
coderabbit review --plain -t uncommitted --dir deploy > /tmp/cr-deploy.txt 2>&1
tail -20 /tmp/cr-deploy.txt
```

- [ ] **Step 5: 把 3 份结果合并回 review 报告**

把 `/tmp/cr-{tests,alembic,deploy}.txt` 的 findings 按严重度分档追加到 `docs/superpowers/plans/2026-04-11-code-review-fixes.md` 的「Phase B 结果」小节，或者单独产出一份 `docs/reports/2026-04-11-code-review-addendum.md`。格式与 Phase A 的 Critical/Warning/Info 清单一致，每条含：**文件:行号 · 问题原因 · 如何修复 · 影响评估**。

- [ ] **Step 6: 将新发现按优先级补入 Phase A 或创建后续 task**

若 Phase B 发现新的 Critical/Warning，**不要直接在本 plan 里修**，而是：
1. 在本 plan 文件末尾追加「Phase B Findings」章节记录原始结果
2. 若需要立即修复，创建一个新的 follow-up plan：`docs/superpowers/plans/2026-04-11-code-review-fixes-phase-b.md`
3. 避免污染本 plan 的 Task 1-7 checkbox 状态

---

## Phase C: 人工评审引擎 6 步（不依赖赛狐 API）

**Background:**
赛狐 API 受白名单限制无法在本地联调，但引擎 6 步是纯 DB + 计算层（依 `AGENTS.md §6.5` 后端约定："引擎 step 不调外部 API"），所以可以完全离线评审。本 Phase 的目标是**产出与 CodeRabbit 同格式的结构化发现清单**，不做实际修改（修改进入后续 plan）。

**Scope:**
- `backend/app/engine/runner.py`（267 行）
- `backend/app/engine/step1_velocity.py`（112 行）
- `backend/app/engine/step2_sale_days.py`（141 行）
- `backend/app/engine/step3_country_qty.py`（34 行）
- `backend/app/engine/step4_total.py`（76 行）
- `backend/app/engine/step5_warehouse_split.py`（220 行）
- `backend/app/engine/step6_timing.py`（109 行）
- 辅助：`backend/app/engine/calc_engine_job.py`、`backend/app/engine/zipcode_matcher.py`

**评审维度**（每个文件都过一遍，对照 `AGENTS.md §6.5` 后端约定与 `docs/Project_Architecture_Blueprint.md` 引擎章节）：

1. **纯度**：是否调用了外部 API？是否跨越了"纯 DB + 计算"的边界？
2. **并发安全**：是否正确使用了 `pg_advisory_xact_lock(7429001)`？是否有未 await 的协程？
3. **事务边界**：长查询是否会跨事务？是否有 N+1 查询？
4. **数学正确性**：velocity 平滑、在途加权、仓库切分、到货时间计算，是否有除零 / 浮点比较 / 边界（库存 0、销量 0）错误？
5. **时区**：是否都走 `app/core/timezone.py` 的 `now_beijing()` / UTC 统一入口？
6. **错误处理**：是否用 `BusinessError` 子类而非裸 `raise`？
7. **类型标注**：SQLAlchemy 2.0 async 返回值是否被正确 `await` 和断言？

- [ ] **Step 1: 建立评审工作区**

创建 `docs/reports/2026-04-11-engine-manual-review.md` 骨架：

```markdown
# 引擎 6 步人工评审（2026-04-11）

> 评审人：Claude + 用户
> 评审范围：backend/app/engine/
> 评审基准：AGENTS.md §6.5 + Project_Architecture_Blueprint.md 引擎章节

## 执行摘要
- 总文件数：9
- Critical: 0 / Warning: 0 / Info: 0（待填）

## 按文件清单

### runner.py
### step1_velocity.py
### step2_sale_days.py
### step3_country_qty.py
### step4_total.py
### step5_warehouse_split.py
### step6_timing.py
### calc_engine_job.py
### zipcode_matcher.py
```

- [ ] **Step 2: 阅读 `runner.py` 并补充发现**

通读全文，对照 7 个评审维度逐条检查。写入 `runner.py` 章节。**凡是发现问题的地方，引用 `runner.py:N` 行号**。如果没有问题，写 "未发现问题（已对照 7 维度）"。

- [ ] **Step 3: 逐一评审 step1..step6**

对 `step1_velocity.py` ~ `step6_timing.py` 重复 Step 2 的流程。

重点关注每一步的典型陷阱：
- **step1_velocity**：平滑窗口边界、异常值过滤、无销售日处理
- **step2_sale_days**：对 `last_sale_date` 的空值处理、时区
- **step3_country_qty**：国别拆分权重、四舍五入是否造成总量不守恒
- **step4_total**：总量汇总是否正确聚合
- **step5_warehouse_split**：仓库切分的加权算法、并列权重的 tie-breaking
- **step6_timing**：到货时间推算、运输时长参数来源

- [ ] **Step 4: 评审 `calc_engine_job.py` 与 `zipcode_matcher.py`**

- [ ] **Step 5: 交叉验证**

对照 `docs/Project_Architecture_Blueprint.md` 的"引擎 6 步流水线表"，确认：
- 每一步的输入/输出是否与文档描述一致
- 签名与文档描述是否一致
- 是否有文档未记录的 side effect

若发现代码与文档不一致，**以代码为准**（按 `AGENTS.md §9.4` 原则），并在评审报告末尾加"文档同步建议"章节。

- [ ] **Step 6: 补充测试覆盖盘点**

扫描 `backend/tests/unit/test_engine_step*.py`，记录每一步的覆盖程度：

```bash
ls backend/tests/unit/test_engine_step*.py
grep -c '^def test_' backend/tests/unit/test_engine_step*.py
```

在报告里标注：每一步有多少单测、是否覆盖边界场景（空库存、负销量、异常权重等）。

- [ ] **Step 7: 汇总严重度并写执行摘要**

把所有 findings 按 Critical/Warning/Info 计数，更新报告顶部的执行摘要。每个 Critical/Warning 都要有明确的"如何修复"建议。

- [ ] **Step 8: Commit 评审报告**

```bash
git add docs/reports/2026-04-11-engine-manual-review.md
git commit -m "docs(review): add manual review report for engine 6-step pipeline

Offline review not dependent on Saihu API connectivity. Covers runner,
step1-step6, calc_engine_job, zipcode_matcher against 7 review dimensions
from AGENTS.md §6.5."
```

- [ ] **Step 9: 若发现 Critical/Warning，创建 follow-up 修复 plan**

若 Phase C 发现任何 Critical 或 Warning，**不在本 plan 修**，而是产出新 plan：
`docs/superpowers/plans/2026-04-11-engine-review-fixes.md`

并在新 plan 里按本文 Phase A 的 Task 模板（TDD + 单独 commit）组织每个修复项。

---

## 最终自检清单

完成 Phase A/B/C 后：

- [ ] 所有 Task 1-7 的 commit 是否都已提交？
- [ ] `pytest backend/tests/unit -q` 全绿？
- [ ] `cd frontend && npx vue-tsc --noEmit && npx vite build` 通过？
- [ ] `git status --short` 里剩余的未提交文件，是否都确实属于功能开发（而非本 plan 遗留）？
- [ ] `docs/PROGRESS.md` 的"最近更新"日期是否需要同步为 `2026-04-11`（按 `AGENTS.md §9` 触发映射表判断：本次修复不新增 API/view/migration/job，属于内部修复，可不更新，但若有疑问在 PR 描述里写明）？
- [ ] 所有 commit 消息是否符合 `AGENTS.md §8` 前缀规范（feat/fix/refactor/docs/test/chore/style）？

---

## 与既有规范的关系

- **符合 `CLAUDE.md`**：每个 commit 都最小化改动，不顺手重构
- **符合 `AGENTS.md §6.3` 代码原则**：复用现有 `ElMessage` / `getActionMeta` 等工具
- **符合 `AGENTS.md §7` 测试门槛**：每个 commit 前都跑了 pytest / vue-tsc / vite build
- **符合 `AGENTS.md §8` Git 规范**：前缀 + 中英双语说明 + 单独 commit
- **不触发 `AGENTS.md §9.1` 文档映射**：本 plan 不新增/删除 API、view、job、migration、env var，无需同步 `docs/PROGRESS.md` 或 `Project_Architecture_Blueprint.md`（除非 Phase C 发现结构性 bug 后的 follow-up 修复触发）

---

## 风险与假设

| 风险 | 缓解措施 |
|---|---|
| Task 2 重放 4 个 commit 的代码改动时漏掉某处修改 | Step 8 强制 grep + Step 9 跑全量 pytest，漏修改会被 test 抓到 |
| Task 4 的 `renormalize` 意外触及 binary 文件 | .gitattributes 明确声明 `*.png/jpg/... binary`；Step 4 检查 `--cached --stat --ignore-all-space` |
| Task 5 的前端修改破坏现有业务流 | Step 5/6 的 vue-tsc + vite build + vitest 三重校验 |
| Phase B 仍然被 rate limit | 等更长时间（1 小时）再试；若持续被限，降级为人工 review 对应目录 |
| Phase C 评审范围比预计大 | 每个文件都很小（34-267 行），9 个文件加起来 ~1100 行，一次性完成 |
