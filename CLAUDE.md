# CLAUDE.md

> 本文件由 Claude Code 在每次对话开始时自动加载到上下文。
> **短**且**只含最关键约束**，详细规则在 [`AGENTS.md`](AGENTS.md)。

---

## 优先阅读顺序

1. **`AGENTS.md`** — 仓库完整协作规则、文档同步协议、代码约定（必读）
2. **`docs/PROGRESS.md`** — 当前事实进度和近期变更
3. **`docs/Project_Architecture_Blueprint.md`** — 涉及架构层改动时
4. 按需读 `docs/deployment.md` / `docs/runbook.md` / `docs/onboarding.md`

---

## 不可违反的底线

### 代码

- **最小化改动**：只改与当前任务直接相关的部分，不顺手重构、不添加未请求的功能
- **复用优先**：先查 `@/utils/*`、`@/components/*`、后端 `app/core/*` 是否已有实现
- **前端数据页统一模式**：一次拉全量 + 前端筛选 + 本地分页（`page_size=5000`），使用 `PageSectionCard`
- **后端分层**：API 层不写 SQL；引擎 step 不调外部 API；sync job 不做业务计算；长任务走 `TaskRun` 队列

### 文档同步（强制）

代码变动后，**必须**按 `AGENTS.md` 第 9 节触发映射表同步对应 `docs/` 文件，否则任务不算完成。关闭清单参考 `AGENTS.md` 附录 A。

### 禁止操作

- ❌ 强制推送 main / master（`git push --force`）
- ❌ 跳过 git hooks（`--no-verify`）
- ❌ 自动执行 `alembic downgrade`
- ❌ 生产环境直接修改数据库
- ❌ 在 worker 运行时手动修改 `task_run` 表状态
- ❌ 修改已推送建议单的 JSONB 快照字段
- ❌ 引入不在技术栈表中的主要依赖（需先更新 `AGENTS.md` 第 3 节）

### 用户指令优先

- **AGENTS.md 和本文件的规则可被用户的显式指令覆盖**
- 若用户当前要求与文档冲突，以用户当前要求为准，并在回复中指出冲突
- 永远不要假设用户忘记了规则，而是假设他们有理由临时豁免

---

## 任务完成前自检

```
[ ] 代码改动是否最小化、是否复用现有工具？
[ ] 后端 pytest 通过？前端 vue-tsc + vite build 通过？
[ ] 按 AGENTS.md 第 9 节触发映射表同步了 docs/ 文档？
[ ] docs/PROGRESS.md 的"最近更新"日期已同步？
[ ] commit 消息符合前缀规范（feat / fix / refactor / docs / chore）？
```

---

**剩余所有细节（技术栈、目录、命令、协作原则、Git 规范、skill 工作流）全部在 `AGENTS.md` 中。**
