# Implementation Plan: 赛狐补货计算工具

**Branch**: `001-saihu-replenishment` | **Date**: 2026-04-08 | **Spec**: [./spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-saihu-replenishment/spec.md`

## Summary

对接赛狐 ERP OpenAPI 的 SKU 级补货计算工具。定时拉取产品 / 库存 / 在途 / 订单数据，按 6 步规则引擎（动销加权 → 销售天数 → 各国补货量 → 总采购量 → 仓内分配 → 采购/发货时间）生成每日补货建议，由单个采购员审核后一键回写赛狐生成采购单。技术路线：Python 3.11 + FastAPI + SQLAlchemy 2.0 async + PostgreSQL 16 + APScheduler + Vue 3 + Element Plus，单机 Docker Compose 部署。

## Technical Context

**Language/Version**: Python 3.11+ (后端)、TypeScript 5.x + Vue 3 (前端)
**Primary Dependencies**:
  - 后端：FastAPI 0.115+、SQLAlchemy 2.0 async、Alembic、Pydantic v2、httpx、aiolimiter、tenacity、APScheduler、structlog、passlib[bcrypt]、python-jose、pytest-asyncio
  - 前端：Vue 3、Element Plus、Pinia、Vue Router、Vite、axios、Lucide icons
**Storage**: PostgreSQL 16（JSONB 支持、部分唯一索引 for task_run 去重）
**Testing**: pytest + pytest-asyncio（后端单测 + 集成测试）、Vitest（前端单测）
**Target Platform**: 阿里云/腾讯云轻量应用服务器 2核4G / Ubuntu 22.04 / Docker Compose
**Project Type**: Web application（backend + frontend 双项目单仓）
**Performance Goals**:
  - 交互接口 P95 < 500ms / P99 < 1s
  - 首屏 FCP < 1.5s、LCP < 2.5s
  - 单查询 < 100ms（避免 N+1）
  - 首屏 JS gzip < 250KB
  - 规则引擎单批次（500 SKU）计算 < 5 分钟
  - 核心接口 ≥ 20 QPS（内部 1–5 用户场景）
**Constraints**:
  - 赛狐每接口 1 QPS 限流（token 接口另有独立限制）
  - access_token ~24h 有效，40001 失效后自动刷新 + 重试
  - 订单详情首次回填 ≤ 1 小时（近 30 天 ≤ 3000 单）
  - 稳态内存 < 容器限制的 70%
  - 亚马逊邮编 60 天后屏蔽 → 订单邮编本地永久留存
**Scale/Scope**:
  - 用户：1–5 人内部采购员
  - 数据：100–500 启用 SKU × 4–5 目标国 × 6–10 海外仓
  - 订单：约 3000/月（≈100/天）
  - 页面：12 个
  - 数据库实体：20 个
  - FR：88 条

## Constitution Check

基于 `.specify/memory/constitution.md` v1.0.0 的合规门禁，逐项核对：

- [x] **KISS / YAGNI**：单 FastAPI 进程内嵌 APScheduler + Worker，不引入 Redis / Celery / 消息队列；task_run 复用 Postgres；不做多租户/权限/国际化/暗色模式/CSV 导入
- [x] **DRY / 单一职责**：按模块拆分（saihu/sync/engine/pushback/api/core），每文件单一职责；函数控制在 50 行内
- [x] **失败快速 & 关注点分离**：Pydantic 在入参处校验；saihu 客户端层处理重试/限流/签名，向上抛业务异常；UI/业务/数据清晰分层
- [x] **代码规范一致性 (NON-NEGOTIABLE)**：ruff + black + mypy + pytest + Conventional Commits；前端 eslint + prettier + vue-tsc
- [x] **可观测与可维护**：structlog JSON 日志 + api_call_log 表；task_run 表覆盖任务状态与进度；关键 SQL 走索引避免 N+1
- [x] **性能标准**：Technical Context 中已列出全部宪法门禁数值

Constitution Check **PASS**。无需进入 Complexity Tracking。

## Project Structure

### Documentation (this feature)

```text
specs/001-saihu-replenishment/
├── plan.md              # 本文件
├── research.md          # Phase 0 输出：技术研究与决策
├── data-model.md        # Phase 1 输出：20 实体 DDL
├── quickstart.md        # Phase 1 输出：部署与首次使用指南
├── contracts/           # Phase 1 输出：按资源拆分的 API 契约
│   ├── auth.yaml
│   ├── task.yaml
│   ├── suggestion.yaml
│   ├── config.yaml
│   ├── sync.yaml
│   └── monitor.yaml
├── checklists/
│   └── requirements.md
├── spec.md
└── tasks.md             # Phase 2 输出（由 /speckit.tasks 生成）
```

### Source Code (repository root)

```text
restock_system/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口 + lifespan 启动 scheduler + worker
│   │   ├── config.py                # pydantic-settings
│   │   ├── db/
│   │   │   ├── session.py           # SQLAlchemy async engine + session
│   │   │   └── base.py              # Declarative base
│   │   ├── models/                  # ORM 模型（每表一文件）
│   │   │   ├── sku.py
│   │   │   ├── warehouse.py
│   │   │   ├── product_listing.py
│   │   │   ├── inventory.py
│   │   │   ├── in_transit.py
│   │   │   ├── order.py
│   │   │   ├── zipcode_rule.py
│   │   │   ├── suggestion.py
│   │   │   ├── shop.py
│   │   │   ├── task_run.py
│   │   │   ├── sync_state.py
│   │   │   ├── overstock.py
│   │   │   ├── api_call_log.py
│   │   │   └── access_token.py
│   │   ├── schemas/                 # Pydantic DTO
│   │   ├── api/                     # FastAPI 路由
│   │   │   ├── auth.py
│   │   │   ├── task.py
│   │   │   ├── suggestion.py
│   │   │   ├── config.py
│   │   │   ├── sync.py
│   │   │   └── monitor.py
│   │   ├── saihu/                   # 赛狐 API 客户端
│   │   │   ├── client.py            # httpx + sign + 限流 + 重试
│   │   │   ├── sign.py              # HmacSHA256 签名算法
│   │   │   ├── rate_limit.py        # aiolimiter 每接口 token bucket
│   │   │   ├── marketplace.py       # marketplaceId → country → timezone
│   │   │   └── endpoints/           # 9 接口封装（每接口一文件）
│   │   ├── sync/                    # 同步任务执行
│   │   │   ├── product_listing.py
│   │   │   ├── warehouse.py
│   │   │   ├── inventory.py
│   │   │   ├── out_records.py
│   │   │   ├── order_list.py
│   │   │   ├── order_detail.py
│   │   │   └── shop.py
│   │   ├── engine/                  # 规则引擎 Step 1–6
│   │   │   ├── runner.py            # 编排器
│   │   │   ├── step1_velocity.py
│   │   │   ├── step2_sale_days.py
│   │   │   ├── step3_country_qty.py
│   │   │   ├── step4_total.py
│   │   │   ├── step5_warehouse_split.py
│   │   │   ├── step6_timing.py
│   │   │   └── zipcode_matcher.py   # 邮编规则匹配
│   │   ├── pushback/                # 推送采购单
│   │   │   └── purchase.py
│   │   ├── tasks/                   # 任务系统
│   │   │   ├── scheduler.py         # APScheduler 配置 + 定时入队
│   │   │   ├── worker.py            # Worker 循环 + 原子 claim + 心跳
│   │   │   ├── queue.py             # enqueue / dedupe / 状态切换
│   │   │   ├── reaper.py            # 僵尸任务回收
│   │   │   └── jobs/                # 每种 job 的执行函数
│   │   └── core/
│   │       ├── logging.py           # structlog 配置
│   │       ├── exceptions.py        # 业务异常
│   │       ├── security.py          # passlib + JWT
│   │       └── timezone.py          # 北京时间转换工具
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py
│   ├── alembic/
│   │   └── versions/
│   ├── alembic.ini
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── main.ts
│   │   ├── App.vue
│   │   ├── router/
│   │   ├── stores/                  # Pinia
│   │   ├── api/                     # axios 封装
│   │   ├── composables/
│   │   ├── components/              # 通用组件（徽章/卡片/步骤条等）
│   │   ├── views/                   # 12 页面
│   │   │   ├── LoginView.vue
│   │   │   ├── SuggestionListView.vue
│   │   │   ├── SuggestionDetailView.vue
│   │   │   ├── HistoryView.vue
│   │   │   ├── SkuConfigView.vue
│   │   │   ├── GlobalConfigView.vue
│   │   │   ├── WarehouseView.vue
│   │   │   ├── ZipcodeRuleView.vue
│   │   │   ├── ShopView.vue
│   │   │   ├── OverstockView.vue
│   │   │   ├── ApiMonitorView.vue
│   │   │   └── ManualTaskView.vue
│   │   ├── styles/
│   │   │   └── tokens.scss          # Ryvix 设计 tokens
│   │   └── utils/
│   ├── tests/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── Dockerfile
├── deploy/
│   ├── docker-compose.yml
│   ├── Caddyfile
│   └── .env.example
├── docs/
│   └── saihu_api/                   # 接口文档 + 测试样例
├── specs/
└── .specify/
```

**Structure Decision**: 采用 **backend + frontend 双项目单仓** 结构。理由：
1. 前后端独立开发、独立容器化，但同仓保证 spec/docs 与代码同步提交
2. 后端按业务域拆分子模块（saihu/sync/engine/pushback/tasks），符合 DRY + 单一职责
3. 前端按 12 个页面拆分 views，每个 view 对应一个 User Story 或子功能
4. `deploy/` 集中放 docker-compose.yml + Caddyfile 等部署相关文件

## Complexity Tracking

> Constitution Check 全部通过，无需论证例外。
