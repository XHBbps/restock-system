# Specification Quality Checklist: 赛狐补货计算工具

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-04-07
**Last Updated**: 2026-04-08 (API reconciliation)
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)  ⚠ 例外：接口路径与字段名作为对齐事实列出
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- 模块 1–8 全部逐项确认完成
- 基于 8 份真实接口文档 + 7 份测试样例完成 API 对齐
- 88 条 FR、5 个 User Story、8 条 SC、20 个实体
- Step 1 velocity 从订单聚合（用发货量口径）
- 在途数据由"其他出库列表 + 备注含'在途中'"接口驱动（in_transit_record + in_transit_item 双表），每次同步按 last_seen_at 老化
- Step 5 已简化：去掉 MIN_ORDER_SAMPLE 阈值，有数据即按真实比例，零数据均分
- 任务系统：Scheduler + task_run 队列 + Worker（部分唯一索引去重、原子 claim、续租、僵尸回收）
- 时区统一：所有时间按订单站点时区解析后转北京时间存储
- 新增实体：sync_state、task_run
- Frontend Design Direction 章节已纳入 spec（色板 + 视觉语言 + 12 页面清单 + 信息架构 + 进度可视化策略）
- 关键修正：velocity 改用在线产品信息的 day7/14/30SaleNum（不再聚合订单）
- 店铺列表接口已接入（`/api/shop/pageList.json`），指定店铺模式完整可用
- access_token 接口细节已对齐（GET 方法，expires_in 毫秒，40001 刷新策略）
- 其他出库列表作为在途备用方案已记入 Notes
