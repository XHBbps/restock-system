# 2026-04-21 Stage 0 自动化扫描 Inventory

> 本文档是 Stage 1 五个 subagent 的共同起点。所有数字都来自 `.audit-logs/` 下的原始日志，复核请直接查 raw log。

---

## 执行摘要

> **2026-04-22 修订**：Stage 0 末尾的 3 个环境卡点已全部修复（详见文末 "Stage 0 环境修复记录"），现在下表展示的是**修复后**的真实数字。

| 维度 | 结果 | 判定 |
|---|---|---|
| 后端 ruff | 0 errors | ✅ |
| 后端 mypy | **51 errors / 12 files / 107 files checked** | ⚠️ |
| 后端 pytest（unit + integration） | **309 passed, 1 failed**（74.79s） | ⚠️ 1 个真实业务失败（见下） |
| 后端 coverage | **74% overall**（1395 lines uncovered / 5317 total） | ℹ️ |
| 前端 vue-tsc | 0 errors | ✅ |
| 前端 eslint | **2 errors**（同一文件同一行） | ⚠️ |
| 前端 vite build | 构建成功（9.70s），**2 个 chunk 超 500KB 警告** | ⚠️ |
| 未跟踪文件 | 3 项（1 项 65 MB 可执行文件） | ⚠️ |
| DB pg_stat_statements | **未启用** — 无法获取慢查询 | ℹ️ |

**唯一真实测试失败**：`tests/unit/test_runtime_settings.py::test_docs_disabled_by_default_in_production`
- 断言 `settings.docs_enabled() is False`（设 `APP_ENV=production` 后），实际返回 True
- 根因：测试只 `monkeypatch.setenv("APP_ENV", ...)`，但未 clear `APP_DOCS_ENABLED`；dev 容器继承 `APP_DOCS_ENABLED=true`，Pydantic Settings 优先读 env → `docs_enabled()` 返回 True
- **给 Agent A 的 Stage 1 任务**：要么在测试里 `monkeypatch.delenv("APP_DOCS_ENABLED")`，要么让 `docs_enabled()` 在 production 时忽略 env override

**总体判定**：
1. 代码 lint/build/test 层健康（ruff 0 / vue-tsc 0 / 309 passing / 74% coverage）
2. 类型检查有 51 个 mypy error，多集中在 SQLAlchemy 2.x ORM 使用模式（`Result[Any].rowcount` / `on_conflict_do_update` 等），大部分是静态类型存根缺失而非代码缺陷；`api/suggestion.py:46-50` 和 `api/monitor.py:116-117` 是真缺陷
3. 前端 bundle 两个大 chunk（element-plus 906 KB / charts 557 KB）已知，Agent D 做性能取舍
4. 根目录 cloudflared 65 MB 未跟踪 exe 未进 .gitignore，潜在误提交风险

---

## 后端

### ruff
- **0 errors** ✅（raw: `.audit-logs/ruff.log`）
- 跑在 dev 容器内：`docker exec restock-dev-backend ruff check . --cache-dir /tmp/ruff_cache`

### mypy
- **51 errors in 12 files (checked 107 source files)**
- raw: `.audit-logs/mypy.log` 未写成功（stdout 被 pipe 压缩），但分组结果见 `.audit-logs/` 补跑命令
- **热点（按类别聚合）**：
  | 类别 | 位置示例 | 次数 |
  |---|---|---|
  | `Result[Any]` 无 `rowcount` 属性（SQLAlchemy 2.x typing 缺失） | `app/tasks/worker.py:195, 232`、`app/tasks/jobs/daily_archive.py:41, 54` | ≥4 |
  | `ReturningInsert[tuple[int]]` 无 `on_conflict_do_update`（PG dialect-only） | `app/sync/order_list.py:158` | 1 |
  | `api/suggestion.py:46-50` 排序 dict 字段类型不统一（`InstrumentedAttribute` vs `ColumnElement`） | `app/api/suggestion.py:46-50` | 5（连续行） |
  | `ApiCallLog` 不可索引（返回模型当 dict 用） | `app/api/monitor.py:116, 117` | 2 |
  | `apscheduler.*` 缺 library stubs | `app/tasks/scheduler.py:7-9`、`app/tasks/queue.py:12` | 4 |
  | `marketplace_to_country` 传入 `object`（应 `str | None`） | `app/sync/order_detail.py:236` | 1 |
  | `dict(Sequence[Row[...]])` 类型不兼容 | `app/sync/inventory.py:66` | 1 |
  | `step6_timing.py` 传入 `dict[str, float \| None]`，被调方期望 `dict[str, float]` | `app/engine/step6_timing.py:111` | 1 |
  | `scheduler.py:126` Union[None] 上调 `.isoformat` | `app/tasks/scheduler.py:126` | 1 |
- **Agent A 重点**：`api/suggestion.py:46-50` 的排序字典类型问题是显式的应用代码问题；`Result.rowcount` 和 `on_conflict_do_update` 是 SQLAlchemy 2.x 静态类型误报，可用 `cast`/`# type: ignore[attr-defined]` 精准豁免，不是应用 bug。

### pytest（unit + integration，修复后）
- **309 passed, 1 failed**（74.79s；raw: `.audit-logs/pytest-full-cov.log`、`pytest-final.log`）
- **唯一失败**：`tests/unit/test_runtime_settings.py::test_docs_disabled_by_default_in_production`（见 "执行摘要" 的详细分析）
- Integration tests 全部通过：`test_engine_e2e`、`test_snapshot_api`、`test_suggestion_delete_with_snapshot`、`test_config_api`、`test_export_e2e`、`test_generation_toggle_api`、`test_health` — 无业务缺陷

### coverage
- **TOTAL: 74%**（5317 statements, 1395 missed；raw: `.audit-logs/pytest-full-cov.log`）
- Coverage ≥ 90% 的核心模块：`app/engine/step*.py`、`app/core/country_mapping.py`、`app/api/suggestion.py`（部分） 、`app/models/*`（100%）
- Coverage < 50% 的模块（Agent C 关注）：
  - `app/tasks/worker.py`: 36%
  - `app/tasks/reaper.py`: 33%
  - `app/sync/shop.py`: 33%
  - `app/sync/warehouse.py`: 42%
  - `app/tasks/jobs/daily_archive.py`: 42%
  - `app/tasks/scheduler.py`: 47%
  - `app/tasks/jobs/dashboard_snapshot.py`: 55%
  - `app/sync/order_list.py`: 62%
  - `app/saihu/**`: 0%（全部 Saihu API 客户端都未被 test 覆盖）
- **CI 侧**：`backend/.github/workflows/*.yml` 是否 provision 了 `replenish_test` 实例并 pass，需 Agent C 在 Stage 1 交叉验证。

### 后端 tests/ 目录（host 侧）
- `backend/tests/unit/`：15+ 测试文件
- `backend/tests/integration/`：`test_config_api`、`test_engine_e2e`、`test_export_e2e`、`test_generation_toggle_api`、`test_health`、`test_snapshot_api`、`test_suggestion_delete_with_snapshot`
- **注意**：`backend/Dockerfile` **不 COPY tests/ 进 image**，dev `docker-compose` 也不挂载 tests —— 所以本地容器无法直接跑 pytest，需要 `docker cp` 或单独的 test image。

---

## 前端

### vue-tsc
- **0 errors** ✅（raw: `.audit-logs/vue-tsc.log`，exit 0）

### ESLint
- **2 errors, 0 warnings**（exit 1，raw: `.audit-logs/eslint.log`）
- 文件：`frontend/src/views/__tests__/DataInventoryView.test.ts:61`
  - 第 47 列 / 第 51 列：`Unnecessary escape character: \"  no-useless-escape`
- **Agent B 重点**：前端生产代码是干净的，错误只在一个 test 文件里，一分钟修复。

### vite build
- **构建成功**，built in 9.70s（raw: `.audit-logs/vite-build.log`）
- **chunk > 500 KB 警告**：
  | chunk | minified | gzip |
  |---|---|---|
  | `charts-B1g5hBak.js` | **557.23 KB** | 188.66 KB |
  | `element-plus-DtZvwgbY.js` | **906.54 KB** | 293.74 KB |
  | framework-Bf3I-589.js | 125.49 KB | 46.75 KB |
  | index-B1MqI-ja.js | 55.77 KB | 21.21 KB |
- 所有业务页面 chunk 都 < 20 KB（已按路由懒加载）
- **Agent D 重点**：两大依赖是主要 bundle 体积来源；是否按需引入、或 manualChunks 分拆。

### ts-prune
- **未安装** — `frontend/package.json` 无 ts-prune 依赖，`node_modules/.bin/ts-prune` 不存在
- **Agent B**：如果要做前端死代码审计，考虑先 `pnpm/npm add -D ts-prune` 再跑一轮。

---

## 垃圾/死代码/仓库整洁

### 未跟踪文件（`git status --porcelain`）
| 项 | 大小 | 建议 |
|---|---|---|
| `Ai_project.lnk` | 722 B | Windows 快捷方式，加 `.gitignore`（`*.lnk`） |
| `cloudflared-windows-amd64.exe` | **65 MB** | 本地隧道工具，加 `.gitignore`；**严禁意外 commit** |
| `docs/reviews/` | 目录 | 里面有 `2026-04-19-full-audit.md`（上一次 audit），与 `docs/superpowers/reviews/` 路径冲突，Agent E 判定归并或删除 |

### 工作区大文件/大目录（> 1 MB，排除 node_modules/.git/dist）
| 路径 | 大小 | 属于什么 | Agent E 建议 |
|---|---|---|---|
| `.mypy_cache/` | 60 MB | 根目录 mypy 缓存 | 非代码，应在 `.gitignore` 并删除本地 |
| `backend/.mypy_cache/` | 20 MB | 后端 mypy 缓存 | 同上 |
| `deploy/data/pg-dev/` | 121 MB | dev 数据库持久化 | 已 gitignore，提醒勿误 push |
| `deploy/data/pg-local/` | 73 MB | 另一套 local PG 目录 | 可能已废弃，Agent E 确认 |
| `frontend/.vite/` | 9 MB | vite 依赖预构建缓存 | 已 gitignore |
| `deploy/data/exports/` | 212 KB | Excel 导出累积 | 小但会增长，Agent A/E 评估清理策略（Session hint #1） |
| `backend/backend/` | 124 KB | `.test_exports/` pytest 产物（Session hint #2） | 已 gitignore，宿主机累积 |
| `cloudflared-windows-amd64.exe` | 65 MB | 见上 | |
| `.mypy_cache/3.12/cache.db` 等大 entries | — | mypy cache 子文件 | |

### root 目录 `.gitignore` 已确认覆盖：`node_modules/`、`dist/`、`.venv/`、`__pycache__/`
### 未覆盖的建议：`*.lnk`、`cloudflared*`、`.mypy_cache/`、根目录级缓存

---

## DB 统计

### 表行数 top 20（dev DB）
```
inventory_snapshot_history     | 2964
suggestion_item                |  450
task_run                       |  427
suggestion_snapshot_item       |  349
excel_export_log               |   19
permission                     |   18
suggestion_snapshot            |    9
sync_state                     |    9
suggestion                     |    2
access_token_cache             |    0
order_detail_fetch_log         |    0
sys_user                       |    0
role_permission                |    0
sku_config                     |    0
product_listing                |    0
warehouse                      |    0
alembic_version                |    0
login_attempt                  |    0
in_transit_item                |    0
role                           |    0
```
- Dev DB 数据体量非常小（最大表 2964 行）
- **Agent D 注意**：生产量级未知，Stage 0 的表大小**不能代表生产**；如需估算索引收益，得另接生产库或基于业务预期 TPS 推演。

### 慢查询
- **未采集** — `pg_stat_statements` 未启用（`SELECT extname FROM pg_extension;` 只有 `plpgsql`）。
- **Agent D 建议**：如果后续要做真正的性能 review，dev PG 需 `CREATE EXTENSION pg_stat_statements;` 并在 `postgresql.conf` 加 `shared_preload_libraries`。

---

## Stage 1 agent 输入索引

> 下面是各 agent 进入 Stage 1 时应首先读的本清单章节 + 对应 raw log。

### Agent A（后端核心 + 后端技术债 + 后端死代码）
- 读本清单：**后端** 全部章节
- raw：`.audit-logs/ruff.log`、`.audit-logs/pytest.log`
- mypy 分组数据：本文 **后端 / mypy / 热点表**（已在本清单内完整列出）
- **独立关注**：
  - `api/suggestion.py:46-50` 排序 dict 类型（真实缺陷）
  - 19 条 pytest 失败是否只是环境问题（无需重测业务逻辑）
  - 集成测试链路修复（独立 test DB）

### Agent B（前端 UX + 死代码）
- 读本清单：**前端** 全部章节
- raw：`.audit-logs/eslint.log`、`.audit-logs/vite-build.log`
- **Agent B 范围外**：framework-* / charts-* / element-plus-* 大小问题归 Agent D

### Agent C（功能完整度 + 测试缺口）
- 读本清单：**后端 / pytest**、**后端 / tests/ 目录** 章节
- 重点：CI 是否真跑 integration tests（对照 `.github/workflows/*.yml`）
- 重点：`backend/tests/integration/` 下各文件覆盖的功能链路是否和 `specs/`、`docs/PROGRESS.md` 对齐

### Agent D（性能）
- 读本清单：**前端 / vite build**、**DB 统计** 全部章节
- 重点：element-plus 906 KB / charts 557 KB 的拆分策略
- 重点：pg_stat_statements 未启用 —— 是否要求 Agent D 先在 dev 开启再跑

### Agent E（部署 + 垃圾文件）
- 读本清单：**垃圾/死代码/仓库整洁** 全部章节
- raw：`.audit-logs/` 无对应 log（靠 git status / du 直出）
- 重点：
  - `.gitignore` 补充清单（`*.lnk` / `cloudflared*` / 根目录 `.mypy_cache/`）
  - `deploy/data/pg-local/` 是否已废弃
  - `docs/reviews/` vs `docs/superpowers/reviews/` 路径治理

---

## Stage 0 执行环境注记

- **宿主**：Windows 11，Git Bash（路径需要 `MSYS_NO_PATHCONV=1` 防 `/app` 被翻译成 `C:\Program Files\Git\app`）
- **容器**：`restock-dev-backend` 非 root `app` 用户运行，`/app` 下不可写 —— 所有 ruff/mypy/pytest 缓存必须写 `/tmp`
- **容器 image 不带 tests/**：需 `docker cp backend/tests restock-dev-backend:/tmp/tests` 再跑
- **pytest 入口**：`/install/bin/pytest`（不是 `python -m pytest`，容器默认 python 找不到）
- **pytest rootdir**：pytest 从 target 向上找 config 文件，`/tmp/tests` 找不到 `/app/pyproject.toml`，**必须 `-c /app/pyproject.toml`** 否则 `asyncio_mode` 回退到 STRICT
- **test DB**：`TEST_DATABASE_URL=postgresql+asyncpg://postgres:${DB_PASSWORD}@db:5432/replenish_test`（必须 `replenish_test`，不能用 `replenish`，否则 conftest `pytest.exit()`）
- **coverage 入口**：`COVERAGE_FILE=/tmp/.coverage`（`/app` 下 `app` 用户不可写）

### Stage 1 agent 推荐 pytest 命令

```bash
docker cp backend/tests restock-dev-backend:/tmp/tests
docker exec restock-dev-backend bash -c "
  cd /tmp && \
  TEST_DATABASE_URL='postgresql+asyncpg://postgres:local_check_db_password@db:5432/replenish_test' \
  COVERAGE_FILE=/tmp/.coverage \
  PYTHONPATH=/app:/install/lib/python3.11/site-packages \
  /install/bin/pytest -c /app/pyproject.toml -o cache_dir=/tmp/pytest_cache \
    tests --cov=app --cov-report=term -q --no-header
"
```

三个关键点缺一不可：
- `cd /tmp`：**必须**。`test_export_e2e.py:28` 用了相对路径 `Path("backend/.test_exports")`，cwd=/app 时会 `PermissionError`（这是测试代码 bug，详见下面 "修复过程中发现的真实测试代码 bug"）
- `-c /app/pyproject.toml`：**必须**。pytest rootdir discovery 从 target 路径往上找，`/tmp/tests` 不会发现 `/app/pyproject.toml`，`asyncio_mode=auto` 失效
- `-o cache_dir=/tmp/pytest_cache`：**必须**。pytest 默认写 `.pytest_cache` 到当前 rootdir，非 root `app` 用户写 `/app/.pytest_cache` 失败，pyproject 的 `filterwarnings=error` 把 warning 升成 error

宿主是 Windows Git Bash 时在最前面加 `MSYS_NO_PATHCONV=1` 防 `/app` 被翻译。

---

## Stage 0 环境修复记录（2026-04-22）

Stage 0 首轮扫描发现 3 个卡点导致测试/覆盖率采不到真实数字，逐一定位 + 修复：

### 卡点 1：`asyncio_mode = "auto"` 没生效 → 19 条 async unit test 以 "async def functions are not natively supported" 失败

**根因**：`backend/Dockerfile` runtime stage 只 COPY `app/ alembic/ alembic.ini`，**没 COPY `pyproject.toml`**；容器内 `/app/pyproject.toml` 不存在，`pytest --asyncio-mode` 回退到 STRICT。包依赖实际已装（`pytest==9.0.3` / `pytest-asyncio==1.3.0` / `anyio==4.12.1` 在 requirements.lock）。

**修复**：`backend/Dockerfile` 第 48 行下增加 `COPY --chown=app:app pyproject.toml ./`，重建 backend/worker/scheduler 镜像。

### 卡点 2：`replenish_test` 独立库缺失 → Integration tests 全被拒

**根因**：`backend/tests/integration/conftest.py:24-29` 明确 `pytest.exit` 阻止在 `replenish` 主库上跑，要求 `replenish_test` 独立库。

**修复**：`docker exec restock-dev-db psql -U postgres -c "CREATE DATABASE replenish_test;"` —— 库本已存在但空表；conftest 的 `_setup_db` autouse fixture 会自动 `Base.metadata.create_all()` + `drop_all()`，无需 alembic。

### 卡点 3：coverage sqlite 无法写入 → InternalError

**根因**：容器以非 root `app` 用户运行，`/app` 属 root，coverage 默认写 `.coverage` 在 cwd（`/app`）下被拒。

**修复**：运行时设置 `COVERAGE_FILE=/tmp/.coverage` env var 绕过，不改 pyproject.toml（保持 CI 其他环境不受影响）。

### 修复验证

两次 end-to-end clean run（drop+create `replenish_test` 后立刻跑）结果完全一致：

| run | 命令 | 结果 | 备注 |
|---|---|---|---|
| A：hack 路径 | `docker cp pyproject.toml → /tmp/` + `cd /tmp && pytest tests` | **309 passed / 1 failed / 74% / 74.79s** | 首轮诊断过程中用的路径 |
| B：长期路径 | Dockerfile baked pyproject + `cd /tmp && pytest -c /app/pyproject.toml tests` | **309 passed / 1 failed / 74% / 8:17** | 推荐路径，容器重建后永久可重复 |

唯一剩下的失败是真实业务缺陷 `test_docs_disabled_by_default_in_production`（详见执行摘要，归 Agent A）。

**run B 耗时长（8:17 vs 74.79s）的原因**：
- 刚重启容器，数据库连接池冷启动
- `_setup_db` autouse fixture 每条 integration test 都 `create_all` + `drop_all`（28 个 integration tests × 上下 schema 数十张表 × asyncpg NullPool 每次新建连接）
- `/app/pyproject.toml` 存在后，pytest 的 `filterwarnings=error` 真正生效（之前无 config 时一些 warning 被静默），可能让额外的 sqlalchemy/asyncio warning 路径被检查
- **这是 Stage 1 Agent D 可关注的性能线索**：integration test 链路可能通过 session-scoped engine + transaction rollback 模式把耗时从分钟级压到秒级

### 中途观察到的 flakiness（非真 flakiness，已定位）

首次 end-to-end 尝试（`pytest /tmp/tests` 而不是 `cd /tmp && pytest tests`）得到 **299 passed / 11 failed / 73% / 9:02**，多出的 10 个失败全部是 `PermissionError`，经诊断：
- `backend/tests/integration/test_export_e2e.py:28` + `test_snapshot_api.py` 链路上用 `Path("backend/.test_exports").resolve()` **相对路径**
- cwd=/app 时 resolve 成 `/app/backend/.test_exports`，`/app/backend` 不存在且 `/app` 不可写 → 失败
- cwd=/tmp 时 resolve 成 `/tmp/backend/.test_exports`，/tmp 可写 → 通过

这同时解释了 host 侧那个莫名的 `backend/backend/.test_exports/` 目录（Stage 0 "垃圾文件" 章节里的 124 KB）—— 是 host 测试产物累积。改为 `tmp_path` fixture 会一并消除垃圾和 flakiness。

### 修复过程中发现的真实测试代码 bug（Agent A 在 Stage 1 修）

**`backend/tests/integration/test_export_e2e.py:28`** 使用相对路径 `Path("backend/.test_exports").resolve()`，resolve 结果依赖 pytest cwd：
- cwd=repo root（host 跑）→ `<repo>/backend/.test_exports`（就是目前 host 侧那个 124 KB 的奇怪目录 `backend/backend/.test_exports/`，Stage 0 "垃圾文件" 段落里有提）
- cwd=/app（容器内默认）→ `/app/backend/.test_exports`，`/app/backend` 不存在且 `/app` 对非 root `app` 用户不可写 → `PermissionError`
- cwd=/tmp（Stage 0 修复命令）→ `/tmp/backend/.test_exports`，/tmp 可写 → 通过

**建议修复**：改用 `tmp_path` pytest fixture（或 `tmpdir_factory`），不要用相对路径。会同时消除 host 侧 `backend/backend/.test_exports/` 的累积垃圾。

### 遗留非本 Stage 0 范围但值得未来清理的观察
- 前端 `DataInventoryView.test.ts:61` 的 2 个 `no-useless-escape` eslint 错误（Agent B 一分钟修）
- 根目录 `cloudflared-windows-amd64.exe`（65 MB）未进 .gitignore（Agent E）
- Dockerfile 改动已生效但 `docker-compose.dev.yml` 未加 tests/ 卷挂载 —— Stage 1 agent 跑 pytest 仍需 `docker cp backend/tests /tmp/tests`（可在 Stage 3 fix 加一行 mount）
