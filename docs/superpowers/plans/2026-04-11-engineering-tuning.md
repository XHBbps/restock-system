# 工程化调优 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复死代码清理引入的 bug、清零 ruff lint 告警、提升覆盖率阈值、修正 CLAUDE.md、优化 CI 流水线。

**Architecture:** 6 个独立 Task，按优先级排序。Task 1 修复关键 bug，Task 2-3 修 lint，Task 4 调阈值，Task 5 修文档，Task 6 优化 CI。

**Tech Stack:** ruff, pytest-cov, vitest/v8, GitHub Actions

---

## Task 1: 修复 `_Out` 未定义 bug（关键）

**Files:**
- Modify: `backend/app/api/data.py`

之前清理死代码时删掉了 `from app.schemas.data import SkuOverviewListOut as _Out`，但 `_Out` 仍在第 708 行和第 762 行被使用。这会导致运行时 NameError。

- [ ] **Step 1: 将 `_Out` 替换为 `SkuOverviewListOut`**

`SkuOverviewListOut` 已在文件顶部导入（用于函数签名 `response_model=SkuOverviewListOut`）。将 `data.py` 中所有 `_Out(` 替换为 `SkuOverviewListOut(`。

共 2 处：
- 第 708 行: `return _Out(items=[], ...)` → `return SkuOverviewListOut(items=[], ...)`
- 第 762 行: `return _Out(items=items, ...)` → `return SkuOverviewListOut(items=items, ...)`

- [ ] **Step 2: 验证 ruff 不再报 F821**

Run: `cd backend && python -m ruff check app/api/data.py --select F821`
Expected: 无输出（0 errors）

- [ ] **Step 3: 验证 mypy 通过**

Run: `cd backend && python -m mypy app/api/data.py --config-file=pyproject.toml`
Expected: Success

- [ ] **Step 4: 提交**

```bash
git add backend/app/api/data.py
git commit -m "fix: replace undefined _Out alias with SkuOverviewListOut"
```

---

## Task 2: 修复中文字符 lint 告警（RUF001/RUF002/RUF003）

**Files:**
- Modify: `backend/pyproject.toml`

共 8 个告警，全部是中文字符串/注释/docstring 中的全角标点（`，` `：` `＄`）。这些在中文语境中是正确的，应在 ruff 配置中全局忽略。

- [ ] **Step 1: 在 ruff 的 ignore 列表中添加 RUF001/RUF002/RUF003**

在 `backend/pyproject.toml` 的 `[tool.ruff.lint]` 的 `ignore` 列表中追加三条规则：

将：
```toml
ignore = [
    "E501",  # 行长由 black 管
    "B008",  # FastAPI Depends() 用法
]
```

替换为：
```toml
ignore = [
    "E501",    # 行长由 formatter 管
    "B008",    # FastAPI Depends() 用法
    "RUF001",  # 中文字符串中的全角标点
    "RUF002",  # 中文 docstring 中的全角标点
    "RUF003",  # 中文注释中的全角标点
]
```

- [ ] **Step 2: 验证 RUF00x 告警消失**

Run: `cd backend && python -m ruff check . --select RUF001,RUF002,RUF003`
Expected: 无输出（0 errors）

- [ ] **Step 3: 提交**

```bash
git add backend/pyproject.toml
git commit -m "chore: ignore fullwidth punctuation lint rules for Chinese strings"
```

---

## Task 3: 修复剩余 ruff 告警（SIM102 + SIM105）

**Files:**
- Modify: `backend/app/api/suggestion.py`
- Modify: `backend/app/tasks/scheduler.py`

### Step 3.1: 合并嵌套 if（SIM102）

- [ ] **修改 `backend/app/api/suggestion.py`**

将（约第 200-202 行）：
```python
    if patch.total_qty is not None and patch.country_breakdown is not None:
        if sum(patch.country_breakdown.values()) != patch.total_qty:
            raise ValidationFailed("country_breakdown 之和与 total_qty 不一致")
```

替换为：
```python
    if (
        patch.total_qty is not None
        and patch.country_breakdown is not None
        and sum(patch.country_breakdown.values()) != patch.total_qty
    ):
        raise ValidationFailed("country_breakdown 之和与 total_qty 不一致")
```

### Step 3.2: 使用 contextlib.suppress（SIM105）

- [ ] **修改 `backend/app/tasks/scheduler.py`**

首先在文件顶部的 import 区域添加：
```python
import contextlib
```

然后将（约第 128-131 行）：
```python
            try:
                scheduler.remove_job("trigger_calc_engine")
            except Exception:
                pass
```

替换为：
```python
            with contextlib.suppress(Exception):
                scheduler.remove_job("trigger_calc_engine")
```

### Step 3.3: 验证 ruff 清零

- [ ] **运行全量 ruff 检查**

Run: `cd backend && python -m ruff check .`
Expected: `All checks passed!`（0 errors）

- [ ] **提交**

```bash
git add backend/app/api/suggestion.py backend/app/tasks/scheduler.py
git commit -m "fix: resolve remaining ruff warnings (SIM102, SIM105)"
```

---

## Task 4: 提升覆盖率阈值

**Files:**
- Modify: `backend/.coveragerc`
- Modify: `frontend/vitest.config.ts`

### Step 4.1: 后端阈值 50 → 55

- [ ] **先验证当前覆盖率**

Run: `cd backend && python -m pytest --cov --cov-config=.coveragerc --cov-report=term-missing -p no:cacheprovider 2>&1 | grep "^TOTAL"`
Expected: 总覆盖率约 57-58%，确认 ≥ 55

- [ ] **修改 `backend/.coveragerc`**

将 `fail_under = 50` 改为 `fail_under = 55`

- [ ] **再次运行验证阈值通过**

Run: `cd backend && python -m pytest --cov --cov-config=.coveragerc --cov-report=term-missing -p no:cacheprovider 2>&1 | tail -3`
Expected: `Required test coverage of 55.0% reached.`

### Step 4.2: 前端阈值 2 → 5

- [ ] **先验证当前覆盖率**

Run: `cd frontend && npm run test:coverage 2>&1 | grep -i "statements"`
Expected: 确认 statements 覆盖率 ≥ 5%

如果当前覆盖率 < 5%，将阈值设为当前值向下取整（最低 2，不降级）。

- [ ] **修改 `frontend/vitest.config.ts`**

将 `statements: 2,` 改为 `statements: 5,`

- [ ] **再次运行验证阈值通过**

Run: `cd frontend && npm run test:coverage`
Expected: 全部测试 pass，覆盖率 ≥ 5%

### Step 4.3: 提交

- [ ] **提交**

```bash
git add backend/.coveragerc frontend/vitest.config.ts
git commit -m "chore: raise coverage thresholds (backend 55%, frontend statements 5%)"
```

---

## Task 5: 修正 CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

当前 `CLAUDE.md` 中 Commands 部分写的是 `cd src; pytest; ruff check .`，但项目没有 `src/` 目录，测试在 `backend/` 下。

- [ ] **Step 1: 修正 Commands 部分**

将：
```markdown
## Commands

cd src; pytest; ruff check .
```

替换为：
```markdown
## Commands

cd backend && pytest && ruff check .
```

- [ ] **Step 2: 修正 Project Structure 部分**

将：
```markdown
## Project Structure

```text
backend/
frontend/
tests/
```
```

替换为：
```markdown
## Project Structure

```text
backend/        # Python 后端 (FastAPI)
frontend/       # Vue 3 前端
deploy/         # Docker / 部署脚本
docs/           # 文档与计划
```
```

（`tests/` 目录不存在于项目根目录，测试在 `backend/tests/` 中）

- [ ] **Step 3: 提交**

```bash
git add CLAUDE.md
git commit -m "docs: fix incorrect commands and project structure in CLAUDE.md"
```

---

## Task 6: CI 流水线优化

**Files:**
- Modify: `.github/workflows/ci.yml`

### Step 6.1: 添加 pip 缓存

- [ ] **在 backend job 的 setup-python step 中添加缓存**

将：
```yaml
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
```

替换为：
```yaml
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: backend/pyproject.toml
```

### Step 6.2: 验证 YAML 合法

- [ ] **验证**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML OK')"`
Expected: `YAML OK`

### Step 6.3: 提交

- [ ] **提交**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add pip cache to speed up backend CI"
```

---

## Task 7: 最终全量验证

- [ ] **后端全量检查**

Run: `cd backend && python -m ruff check . && python -m mypy app && python -m pytest --cov --cov-config=.coveragerc --cov-report=term-missing -p no:cacheprovider`
Expected: ruff 0 errors, mypy Success, 全部测试 pass, 覆盖率 ≥ 55%

- [ ] **前端全量检查**

Run: `cd frontend && npm run build && npm run test:coverage`
Expected: build 成功, 全部测试 pass, 覆盖率 ≥ 5%

- [ ] **CI YAML 验证**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('OK')"`
Expected: `OK`
