# AGENTS.md

> **仓库范围**：`E:\Ai_project\restock_system` — 独立仓库，不是上层多项目工作区入口。
> **本文件性质**：长期稳定的协作规则和文档入口，**变动较少**。短期目标、当前进度、具体架构细节均在 `docs/` 下。
>
> 每次进入仓库先读本文件，再按"默认阅读顺序"继续。

---

## 1. 仓库定位

`restock_system` 是面向**小团队（1-5 用户）**的跨境电商海外仓补货管理系统，**对公网开放**（通过 Caddy + TLS）。从赛狐（Sellfox）同步业务数据，通过规则引擎计算各国采购/补货建议，并以 Excel 导出 + 不可变快照方式交付给业务人员。

**核心业务流**：

```
赛狐只读同步 → 补货建议计算（6 步引擎）→ 建议编辑 → Excel 导出 + 快照版本化
```

**规模约束**：

- **对公网开放**（需防爬 / 暴破 / DoS / 注入等外部攻击面）
- 用户数 1-5 人
- 单机 Docker Compose 部署
- 数据量可容纳于单库（无分库分表需求）
  - 订单表（最大）：保守估计 5 年 120,000 行（约 2000 行/月 × 60 月）
  - 其他表（商品 / 库存 / 建议单等）：同数量级或更小

---

## 2. 目录结构

```
restock_system/
├── backend/              # FastAPI 后端
├── frontend/             # Vue 3 + Vite 前端
├── deploy/               # Docker Compose / Caddy 部署配置
├── docs/                 # 项目文档（短期目标与当前事实所在位置）
├── scripts/              # 统一检查脚本（check.ps1 / check.sh）
├── .claude/skills/       # Speckit skills（本仓库内置）
├── .specify/             # Spec 工作流目录
├── .github/              # CI/CD workflows
├── CLAUDE.md             # 自动生成的技术栈摘要
└── AGENTS.md             # 本文件
```

---

## 3. 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11+ / FastAPI / SQLAlchemy 2.0 async / Alembic / Pydantic v2 |
| 前端 | Vue 3 / TypeScript 5 / Vite 6 / Pinia / Vue Router / Element Plus / ECharts |
| 调度 | APScheduler + 自研 TaskRun 队列（Worker / Reaper / Scheduler） |
| 外部集成 | 赛狐 API（httpx + aiolimiter + tenacity） |
| 数据库 | PostgreSQL 16（asyncpg） |
| 部署 | Docker Compose + Caddy + Nginx |
| 测试与质量 | pytest / ruff / black / mypy / Vitest 4 / ESLint / vue-tsc |

**技术栈变动频率**：低。若添加新的主要依赖或替换核心框架，属于架构变更，需更新本节 + `docs/Project_Architecture_Blueprint.md`。

---

## 4. 文档地图

**AGENTS.md 是长期协作规则，短期信息全部在 `docs/`**。

| 文档 | 定位 | 变动频率 |
|---|---|---|
| `AGENTS.md`（本文件） | 仓库协作入口，长期规则 | 低 |
| `CLAUDE.md` | 自动生成的技术栈摘要 | 低 |
| `docs/Project_Architecture_Blueprint.md` | 完整架构蓝图：分层、组件、ADR、扩展指南 | 中（架构演进时） |
| `docs/PROGRESS.md` | 已交付能力 + 近期重大变更 | 高（每次功能交付） |
| `docs/deployment.md` | 部署流程与环境变量 | 中（部署配置变更时） |
| `docs/runbook.md` | 故障排查与运维 | 中（新增排障场景时） |
| `docs/onboarding.md` | 新成员入门、本地开发 | 低（流程变化时） |
| `docs/saihu_api/` | 赛狐 API 参考资料（外部） | 低 |

---

## 5. 默认阅读顺序

1. **AGENTS.md**（本文件）— 协作规则、文档入口、同步协议
2. **`docs/PROGRESS.md`** — 当前事实进度和近期变更
3. **`docs/Project_Architecture_Blueprint.md`** — 若涉及架构层改动
4. **`docs/onboarding.md`** — 若需要本地启动或改目录结构
5. **`docs/saihu_api/*`** — 若涉及赛狐接口联调

---

## 6. 协作原则

### 6.1 核心原则

**需求不明确时，先澄清再动手。** 仓库已进入稳定化阶段，小改动也要避免误改现有流程。

### 6.2 输出原则

- **执行类任务**：直接说明改了什么、为什么改
- **方案类任务**：先给结论，再说明取舍
- **多方案**：最多 3 个，并明确推荐项
- **发现风险、口径冲突、文档失真**：直接指出

### 6.3 代码原则

- **最小化改动**：只改和当前任务直接相关的部分，不顺手大改
- **复用优先**：优先复用已有模块、工具函数、Pinia store、API 封装
- **中文展示**：面向用户的页面文案、状态文案、导出列名优先使用中文
- **字段分层**：内部模型和接口字段保持英文；界面展示、报表导出使用中文
- **保持现状一致**：遵循现有后端模块边界和前端页面结构，不擅自重构目录
- **不添加未经请求的功能**：只实现被要求的改动，不做推测性优化

### 6.4 前端约定

新建列表页/数据页必须遵循：

- 统一使用 `@/components/PageSectionCard` 作为页面容器
- 使用 `@/components/TablePaginationBar` 作为分页条
- 使用 `@/utils/format`、`@/utils/warehouse`、`@/utils/countries`、`@/utils/status`、`@/utils/tableSort` 等共享工具，不重复造轮子
- 数据加载模式：高增长列表页（订单、历史、商品、库存、出库记录等）优先使用**后端分页 + 后端筛选**；仅店铺、仓库等低增长基础页可保留轻量本地分页
- 筛选控件高度统一 32px（`PageSectionCard` 的 `section-actions` 已强制）

### 6.5 后端约定

- **API 层不写 SQL**，走 ORM 或业务函数
- **引擎 step 不调用外部 API**，保持纯 DB + 计算
- **Sync job 不做业务计算**，只做"抓取 → 落库"
- **长任务走 TaskRun 队列**，不在请求线程执行
- **异常用 `BusinessError` 子类**，自动映射为 JSON
- **日志用 `structlog.get_logger`**，`request_id` 自动绑定

---

## 7. 测试与校验

### 7.1 后端

```bash
cd backend
pytest                            # 全部测试（通过是最低门槛）
ruff check .                      # lint（按需）
mypy app                          # 类型检查（按需）
```

### 7.2 前端

```bash
cd frontend
npx vue-tsc --noEmit              # 类型检查
npx vite build                    # 生产构建（强校验）
npm run lint                      # eslint（按需）
npm run test                      # Vitest 单元测试（按需）
```

### 7.3 部署相关

涉及 `deploy/` 改动时，验证：

- `deploy/docker-compose.yml` 与 `.env.example` 变量一致
- `deploy/scripts/*.sh` 可执行性
- `deploy/Caddyfile` 反代规则正确

---

## 8. Git 规范

- **Commit 前缀**：`feat:` / `fix:` / `refactor:` / `docs:` / `test:` / `chore:`
- **Commit 消息**：前缀 + 简洁中文描述
- **分支命名**：`feature/<功能名>` / `fix/<问题>` / `refactor/<范围>`
- **提交粒度**：一个完整功能或一个完整修复对应一个 commit
- **禁止**：`--no-verify`、`-c commit.gpgsign=false`、`--force` 推送 main

---

## 9. 文档同步协议（强制）

> **核心原则**：AGENTS.md 是长期规则，短期事实在 `docs/`。代码变动后，**必须**通过本协议同步对应文档，否则任务不算完成。

### 9.1 触发映射表

代码变更后，按下表自检并更新对应文档：

| 代码变更类型 | 必须同步的文档 |
|---|---|
| **新增 / 删除 API 端点** | `docs/PROGRESS.md` 第 2 节已交付能力 + `Project_Architecture_Blueprint.md` 对应组件章节 |
| **新增 / 删除前端 view** | `docs/PROGRESS.md` 第 2 节 + 若改变导航结构，更新 `Project_Architecture_Blueprint.md` 目录结构 |
| **新增 / 删除后端 job** | `docs/PROGRESS.md` 第 2 节 + `Project_Architecture_Blueprint.md` 调度器章节 |
| **数据库 migration（新增/修改表或字段）** | `docs/PROGRESS.md` 第 3 节近期变更 + `Project_Architecture_Blueprint.md` 数据库章节 |
| **引擎 step 逻辑或签名变化** | `Project_Architecture_Blueprint.md` 6 步流水线表 + `docs/PROGRESS.md` 第 3 节 |
| **Docker service 增删 / 资源限制调整** | `docs/deployment.md` 目标架构 + `docs/runbook.md` 排障章节 |
| **新增 / 删除环境变量** | `docs/deployment.md` 环境变量表 + `docs/onboarding.md` 关键环境变量 |
| **健康检查逻辑变化** | `docs/runbook.md` 第 2 节 + `docs/deployment.md` 发布后检查 |
| **新增 / 删除共享 utils 或组件** | `docs/onboarding.md` 开发约定 + `Project_Architecture_Blueprint.md` 前端核心组件 |
| **赛狐 API 限流 / 重试策略变化** | `Project_Architecture_Blueprint.md` 赛狐集成层 + `docs/PROGRESS.md` 第 3 节 |
| **任务队列字段 / 调度策略变化** | `Project_Architecture_Blueprint.md` 任务队列系统 + `docs/runbook.md` 第 3 节 |
| **技术栈依赖新增 / 主要版本升级** | `AGENTS.md` 第 3 节技术栈 + `Project_Architecture_Blueprint.md` 技术栈 + `docs/onboarding.md` 环境要求 |
| **目录结构调整** | `AGENTS.md` 第 2 节 + `Project_Architecture_Blueprint.md` 目录 + `docs/onboarding.md` 项目结构 |
| **协作规则 / 代码约定变化** | `AGENTS.md` 第 6 节（同步更新本文件） |

### 9.2 关闭清单（每次任务完成前自检）

```
[ ] 代码改动是否触发 9.1 中的任何一条？
[ ] 若触发：相应文档是否已同步更新？
[ ] 若未同步：说明为什么不需要（例如仅内部重构无语义变化）或立即补写
[ ] 文档更新是否保持格式一致（表格、层级、UTF-8 编码）？
[ ] `docs/PROGRESS.md` 的"最近更新"日期是否同步为本次任务日期？
```

### 9.3 文档写作规范

- **只写已确认事实**，不写猜测或未来计划（未来计划放在 `docs/PROGRESS.md` 第 5 节"后续计划"）
- **保持 UTF-8 编码**，避免乱码（若 Edit/Write 工具无法匹配，先用 Read 确认当前编码状态再改）
- **引用代码时附带文件路径**（`backend/app/engine/runner.py:58`），方便检索
- **表格优先于长段落**，便于扫描
- **章节层级不超过 3 级**（`##` / `###` / `####`），避免过度嵌套
- **中文标点符号**：正文使用中文标点（`，。：；""''`），代码/命令保留英文标点

### 9.4 文档之间的关系

```
AGENTS.md                                (长期稳定)
    │
    ├──▶ docs/PROGRESS.md                 (已交付能力 + 近期变更)
    ├──▶ docs/Project_Architecture_Blueprint.md  (架构真理源)
    ├──▶ docs/deployment.md               (部署流程)
    ├──▶ docs/runbook.md                  (运维故障排查)
    └──▶ docs/onboarding.md               (新成员入门)
```

**优先级**：
- **冲突时**以代码实际行为为准
- 代码 vs 文档冲突 → 修复文档
- 文档 vs 文档冲突 → 以 `Project_Architecture_Blueprint.md` 为准，其次 `PROGRESS.md`
- 规则冲突 → 以用户**当前**指令为准（AGENTS.md 规则可被用户显式覆盖）

---

## 10. 复杂变更工作流

涉及架构级变更、新功能、复杂重构时，按以下工作流进行：

1. 先讨论设计，形成范围、取舍和验收口径
2. **用户审阅 spec 并确认**
3. 产出实施计划（如需落盘，使用当前任务明确指定的位置）
4. 按计划执行，保持每步可验证
5. **每步通过校验后才算验收**
6. **按第 9 节触发映射表同步文档**

其他常用 skill：

- `superpowers:systematic-debugging` — 遇到 bug 时先用这个确定根因
- `superpowers:verification-before-completion` — 声明"完成"前运行验证命令
- `superpowers:requesting-code-review` — 大功能或合并前自查

---

## 11. 仓库约束

- **生产环境默认关闭 OpenAPI 文档**（`APP_DOCS_ENABLED=false`）
- **数据库迁移不自动 downgrade**，依赖"恢复备份 + 回退应用版本"
- **赛狐数据只读同步**，不回写到赛狐（当前无推送场景，Plan A 后采购建议走 Excel 导出交付业务人员）
- **已导出的快照 JSONB 字段不可变**（`suggestion_snapshot` + `suggestion_snapshot_item` 的 `payload` / `country_breakdown` 等一经导出即冻结，版本递增）
- **引擎并发受 `pg_advisory_xact_lock(7429001)` 保护**，不要绕过
- **任务队列禁止跨 TaskRun 表直接修改状态**（可能破坏 worker 状态机）

---

## 附录 A：任务完成声明前的自检清单

```
功能完整性
[ ] 代码改动实现了用户请求的所有子项
[ ] 没有添加未请求的功能
[ ] 边界场景已考虑（null、空数组、权限、并发）

质量校验
[ ] 后端 pytest 通过（如有后端改动）
[ ] 前端 vue-tsc + vite build 通过（如有前端改动）
[ ] lint/format 按需通过

文档同步（参考第 9 节）
[ ] 触发映射表已逐行自检
[ ] 相关 docs/ 文档已同步或明确不需要更新
[ ] PROGRESS.md 日期已更新

提交规范
[ ] commit 消息符合前缀规范
[ ] commit 粒度合理
[ ] 不跨越不相关的文件
```

---

**本文件变动规则**：AGENTS.md 本身的变更属于协作规则变更。修改前应先说明原因，修改后应在 commit 消息中明确标注。
