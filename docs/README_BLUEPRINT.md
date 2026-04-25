# Restock System README 蓝图

> 生成日期：2026-04-25
> 生成依据：`readme-blueprint-generator` skill，并按本仓库实际文档结构改用 `AGENTS.md`、`docs/PROGRESS.md`、`docs/Project_Architecture_Blueprint.md`、`docs/onboarding.md`、`docs/deployment.md`、`.github/workflows/*` 作为事实来源。

---

## 1. 蓝图目标

本蓝图用于指导 `README.md` 的生成与后续维护，确保 README 能同时服务三类读者：

| 读者 | 关注点 | README 应回答的问题 |
|---|---|---|
| 业务方 | 系统解决什么问题 | 主链路、交付方式、当前是否回写赛狐 |
| 新开发者 | 如何理解与启动项目 | 技术栈、架构、目录、快速开始、常用命令 |
| 运维 / 发布人员 | 如何部署与验证 | Docker Compose 服务、Caddy、健康检查、文档入口 |

README 不替代完整架构蓝图、部署指南和运维手册，只提供入口级说明与最短路径。

---

## 2. 信息来源映射

| README 内容 | 主要来源 | 维护依据 |
|---|---|---|
| 项目定位 | `AGENTS.md` §1、`docs/onboarding.md` §1 | 业务主链路或部署形态变化时更新 |
| 已交付能力 | `docs/PROGRESS.md` §2 | 功能交付后按事实提炼，不复制所有变更流水 |
| 技术栈 | `AGENTS.md` §3、`backend/pyproject.toml`、`frontend/package.json` | 主依赖新增或版本大升级时更新 |
| 架构概览 | `docs/Project_Architecture_Blueprint.md` §1-§3 | 架构层、进程角色、任务队列变化时更新 |
| 快速开始 | `docs/onboarding.md` §4、`docs/deployment.md` §0.5 | 本地启动流程或环境变量变化时更新 |
| 常用命令 | `scripts/check.ps1`、`scripts/check.sh`、`backend/pyproject.toml`、`frontend/package.json` | 校验脚本或 npm / pytest 命令变化时更新 |
| 部署概览 | `docs/deployment.md` §1 | Docker service、Caddy、数据目录变化时更新 |
| CI/CD | `.github/workflows/ci.yml`、`.github/workflows/deploy.yml` | CI 门禁、镜像发布或部署流程变化时更新 |

---

## 3. 推荐 README 结构

### 3.1 Header

- 居中展示项目图标：`frontend/public/favicon.svg`
- 标题：`Restock System`
- 副标题：`跨境电商海外仓补货管理系统`
- 一句话主链路：`赛狐只读同步 · 6 步补货计算 · 建议编辑 · Excel 导出 · 不可变快照`

### 3.2 项目简介

应明确：

- 面向 1-5 人小团队；
- 从赛狐只读同步业务数据；
- 通过规则引擎生成采购 / 补货建议；
- 以 Excel 导出和快照版本化交付；
- 当前不回写赛狐。

建议使用 GitHub admonition 强调当前主链路，避免读者误以为仍存在赛狐写入链路。

### 3.3 功能特性

控制在 6-8 条，优先写稳定能力：

- 赛狐只读同步；
- 6 步补货引擎；
- 采购 / 补货拆分；
- 建议编辑与校验；
- Excel 导出与快照追溯；
- TaskRun 后台任务队列；
- JWT + RBAC + 生产文档关闭。

不要在 README 中展开所有近期变更，完整变更应链接到 `docs/PROGRESS.md`。

### 3.4 技术栈

使用表格按层级列出：

| 层级 | 内容 |
|---|---|
| 后端 | Python、FastAPI、SQLAlchemy、Alembic、Pydantic |
| 前端 | Vue、TypeScript、Vite、Pinia、Element Plus、ECharts |
| 调度 | APScheduler、TaskRun |
| 数据库 | PostgreSQL 16 |
| 部署 | Docker Compose、Caddy、Nginx |
| 测试 | pytest、ruff、mypy、Vitest、ESLint、vue-tsc |

README 中只保留主版本或大版本，精确依赖版本以 `pyproject.toml` 和 `package.json` 为准。

### 3.5 架构概览

使用简短 ASCII 图，表达：

```text
Frontend → Backend → PostgreSQL
             ├─ engine
             ├─ sync
             ├─ services
             ├─ tasks
             └─ saihu
```

重点说明生产环境的 6 服务部署：

- `backend`：HTTP API；
- `worker`：任务执行 + reaper；
- `scheduler`：定时入队；
- `frontend`：Nginx 静态资源；
- `db`：PostgreSQL；
- `caddy`：TLS 与反代。

详细架构链接到 `docs/Project_Architecture_Blueprint.md`。

### 3.6 快速开始

推荐给出三段命令：

1. 启动本地数据库；
2. 启动后端；
3. 启动前端。

再给出可选的本地全栈容器验证入口。README 不应完整复制 `docs/onboarding.md`，只保留最短可运行路径。

### 3.7 常用命令

按后端、前端、统一检查分组：

- 后端：`pytest`、`ruff check .`、`mypy app`、`alembic upgrade head`
- 前端：`npm run dev`、`npm run build`、`npm run test`、`npm run lint`
- 统一：`powershell scripts/check.ps1`、`bash scripts/check.sh`

### 3.8 项目结构

使用一层目录树即可，避免复制完整源码目录：

```text
backend/
frontend/
deploy/
docs/
scripts/
.github/
AGENTS.md
CLAUDE.md
```

### 3.9 核心业务流

使用编号列表描述：

1. 同步数据；
2. 生成建议；
3. 编辑校验；
4. 导出快照；
5. 历史追溯。

该段应保持业务友好，避免过多实现细节。

### 3.10 部署概览

只保留部署事实：

- Docker Compose + Caddy；
- Caddy TLS；
- 后端角色拆分；
- 数据与导出文件挂载到 `deploy/data/`；
- 详细步骤链接 `docs/deployment.md`；
- 故障排查链接 `docs/runbook.md`。

### 3.11 文档入口

README 最后应作为文档导航：

- `docs/PROGRESS.md`
- `docs/Project_Architecture_Blueprint.md`
- `docs/onboarding.md`
- `docs/deployment.md`
- `docs/runbook.md`
- `AGENTS.md`

---

## 4. 内容边界

README 应避免：

- 展开完整数据库模型；
- 罗列所有 API 端点；
- 复制 `PROGRESS.md` 的近期变更流水；
- 复制部署脚本细节；
- 添加未来计划或未经确认的能力；
- 保留已废弃的赛狐写入表述；
- 添加 `LICENSE`、`CONTRIBUTING`、`CHANGELOG` 等专属文件应承载的章节。

README 可以包含：

- 简短功能概览；
- 最短启动路径；
- 常用校验命令；
- 架构与部署入口；
- 指向事实文档的链接。

---

## 5. 维护规则

| 触发变化 | README 更新建议 |
|---|---|
| 主链路变化 | 更新 Header tagline、项目简介、核心业务流 |
| 技术栈大版本变化 | 更新技术栈表，并保持与 `AGENTS.md` 一致 |
| 新增核心能力 | 在功能特性中替换或追加一条，不超过 8 条 |
| 本地启动流程变化 | 更新快速开始命令，并同步 `docs/onboarding.md` |
| Docker 服务变化 | 更新部署概览，并同步 `docs/deployment.md` |
| 质量门禁变化 | 更新常用命令，并同步 CI / 脚本说明 |
| 文档结构变化 | 更新文档入口列表 |

如发生代码变更，仍需按 `AGENTS.md` 第 9 节执行文档同步协议；本蓝图只约束 README 的组织方式，不替代仓库级文档同步要求。

---

## 6. 当前 README 生成决策

本次生成的 `README.md` 采用以下取舍：

- **以事实文档为准**：主链路采用 `docs/PROGRESS.md` 当前状态，即 Excel 导出 + Snapshot 版本化，不再描述赛狐写入链路。
- **保留入口级细节**：启动命令、目录结构和部署概览保持简短，避免与 `docs/onboarding.md`、`docs/deployment.md` 形成重复维护。
- **强调对公网部署约束**：README 明确生产环境通过 Caddy + TLS 对公网开放，并提醒生产默认关闭 OpenAPI 文档。
- **同步文档入口**：后续若文档结构变化，README 与本蓝图需同步更新文档导航与项目结构。
