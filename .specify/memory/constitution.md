<!--
Sync Impact Report
==================
Version change: (initial template) → 1.0.0
Bump rationale: MAJOR — first ratified version, replaces unfilled template placeholders
  with concrete principles, constraints, and governance.

Modified principles:
  - [PRINCIPLE_1_NAME] → I. KISS & YAGNI
  - [PRINCIPLE_2_NAME] → II. DRY & 单一职责
  - [PRINCIPLE_3_NAME] → III. 失败快速与关注点分离
  - [PRINCIPLE_4_NAME] → IV. 代码规范一致性 (NON-NEGOTIABLE)
  - [PRINCIPLE_5_NAME] → V. 可观测与可维护

Added sections:
  - Performance Standards (性能标准)
  - Development Workflow & Quality Gates (开发流程与质量门禁)

Removed sections: none

Templates requiring updates:
  - ✅ .specify/memory/constitution.md (this file)
  - ✅ .specify/templates/plan-template.md — Constitution Check 已对齐
  - ✅ .specify/templates/spec-template.md — 已加入性能 SC 示例
  - ✅ .specify/templates/tasks-template.md — 已加入 type checker 与性能门禁任务

Deferred TODOs:
  - 无
-->

# Restock System Constitution

## Core Principles

### I. KISS & YAGNI
保持简单是首要原则。每个功能 MUST 选择满足当前需求的最简实现，禁止为假设的未来需求
预留抽象、配置项或扩展点。三处相似代码优于一次过早的抽象。
**Rationale**: 过度设计是项目腐化最常见的根因；删除比新增容易得多。

### II. DRY & 单一职责
公共逻辑 MUST 提取为函数/模块复用，但仅在出现真实重复（≥2 处）时进行。每个函数、类、
模块 MUST 只承担一个明确职责，函数参数 ≤ 4 个，单函数 ≤ 50 行，单文件 ≤ 500 行，
嵌套深度 ≤ 3 层（优先使用 early return）。
**Rationale**: 小而专一的单元更易测试、复用和替换。

### III. 失败快速与关注点分离
错误 MUST 在最早可发现的位置抛出，禁止静默吞掉异常。系统 MUST 在 UI 层、业务逻辑层、
数据访问层之间保持清晰边界，跨层调用只能通过明确定义的接口。
**Rationale**: 静默错误和层级耦合是最难排查的两类缺陷。

### IV. 代码规范一致性 (NON-NEGOTIABLE)
所有提交 MUST 满足以下硬性规范：
- 命名：变量/函数统一风格（小驼峰或蛇形二选一），类用大驼峰，常量全大写
- 公共接口 MUST 有类型标注（TypeScript / Python type hint 等）
- 注释只解释"为什么"，不解释"是什么"
- 提交前 MUST 通过项目配置的 formatter（Prettier/Black/gofmt 等）与 linter
  （ESLint/Ruff 等）
- Git 提交遵循 Conventional Commits，小步提交
- 禁止：魔法数字、死代码、生产代码中的 `console.log`、`any` 类型滥用
**Rationale**: 一致性降低阅读成本，自动化检查比人工 review 更可靠。

### V. 可观测与可维护
关键路径 MUST 具备结构化日志、指标与告警。热点数据 MUST 明确缓存策略与 TTL。
所有数据库访问 MUST 避免 N+1 查询。
**Rationale**: 不可观测的系统等于不可维护的系统。

## Performance Standards

以下为硬性性能门禁，未达标的变更 MUST NOT 合入主干：

- **接口响应**：P95 < 500ms，P99 < 1s
- **首屏加载**：FCP < 1.5s，LCP < 2.5s
- **数据库查询**：单查询 < 100ms，禁止 N+1
- **内存**：单进程稳态内存 < 容器/实例限制的 70%
- **打包体积**：首屏 JS gzip 后 < 250KB
- **并发**：核心接口 MUST 支持 ≥ 20 QPS（基于 1–5 名内部用户场景，含 4× 冗余）
- **缓存**：热点数据 MUST 缓存并明确 TTL 策略
- **监控**：关键路径 MUST 接入日志、指标、告警三件套

## Development Workflow & Quality Gates

1. **代码评审**：所有变更 MUST 通过 PR 评审，至少 1 名评审者批准
2. **自动化检查**：CI MUST 运行 formatter、linter、类型检查、测试套件，全部通过方可合入
3. **测试**：核心业务逻辑 MUST 有单元测试，跨服务/跨层交互 MUST 有集成测试
4. **复杂度论证**：任何违反 Core Principles 的设计 MUST 在 PR 描述中明确论证理由，
   并记录到 plan 的 Complexity Tracking 章节
5. **性能回归**：影响关键路径的变更 MUST 在 PR 中附带性能数据
6. **提交粒度**：单个 PR 聚焦单一目的，避免捆绑无关改动

## Governance

本宪法 supersede 项目内所有其他实践与约定。冲突时以本宪法为准。

**修订流程**：
- 任何条款的修改 MUST 通过 PR 提交，更新本文件并同步更新 `.specify/templates/` 下的相关
  模板及运行时指引文档
- 修订 MUST 遵循语义化版本：
  - MAJOR：移除或不兼容地重定义原则/治理规则
  - MINOR：新增原则/章节或实质性扩展指引
  - PATCH：澄清、措辞、错别字等非语义修订
- 所有 PR 与评审 MUST 验证宪法合规性，复杂度与例外 MUST 显式论证

**合规审查**：每个 feature 的 plan 阶段 MUST 执行 Constitution Check；review 阶段
MUST 复核是否仍然合规。

**Version**: 1.0.0 | **Ratified**: 2026-04-07 | **Last Amended**: 2026-04-07
