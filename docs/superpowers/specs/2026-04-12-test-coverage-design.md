# 测试覆盖提升设计文档

> 设计日期: 2026-04-12
> 前置: `docs/superpowers/specs/2026-04-12-full-system-review.md` 全链路 Review
> 当前基线: 后端 169 passed / 55% 覆盖率阈值，前端 8 个测试 / ~2% 覆盖率

---

## 目标

按风险分层补充测试，优先覆盖"出 bug 代价最高"的路径：

1. 修复 Step5 ceil 回归（Review 修复引入的真实缺陷）
2. 补充推送零数量测试（验证 P2-7 修复）
3. 前端 API 层 + 核心页面单元测试
4. Playwright E2E 黄金路径

## 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 引擎边界测试数量 | 1 个（Step5 ceil） | 其余 7 个场景经逐项验证：已覆盖或生产不可达 |
| Step5 仓分配取整 | 改回 `round()` | 仓分配是固定总量的分配，不适用"宁多勿少"；`ceil` 导致 sum > country_qty |
| 前端测试框架 | Vitest + Vue Test Utils | 项目已配置，CI 已集成 |
| E2E 框架 | Playwright | 社区标准，支持多浏览器，API mock 能力强 |
| 后端覆盖率目标 | 55% → ~60% | 新增 2 个后端测试，提升有限但都在高风险路径 |
| 前端覆盖率目标 | ~2% → ~15% | 补核心路径，不追数字 |

---

## Task A: Step5 ceil 回归修复

**问题**: Phase 1 的 P0-2 修复将 Step5 仓分配的 `round()` 改为 `math.ceil()`，但仓分配是固定总量的等比分配，ceil 导致前 N-1 仓的累计超过 country_qty，末仓得 0。

**复现**:
```
4 仓各占 25%, country_qty=5:
  仓1: ceil(5*0.25) = 2, accumulated=2
  仓2: ceil(5*0.25) = 2, accumulated=4
  仓3: ceil(5*0.25) = 2, accumulated=6
  仓4(末仓): max(5-6, 0) = 0
  sum = 6 ≠ 5
```

**修复**: Step5 `step5_warehouse_split.py:191` 改回 `round()`。Step3/Step4 保持 `ceil()`。

**测试**: 3+ 仓不等比例场景断言 `sum(breakdown) == country_qty`。

---

## Task B: 推送 total_qty=0 测试

**场景**: 用户 PATCH total_qty→0 后推送，代码应抛 ValueError。

**代码路径**: `pushback/purchase.py:74-80` — 过滤 total_qty=0 条目，空列表时 raise。

**测试**: 构造全部 total_qty=0 的 items，断言 ValueError。

---

## Task C: 前端 api/suggestion.ts 单元测试

**覆盖范围**:
- `fetchSuggestionDetail(id)` — 正常返回 + 404 处理
- `patchSuggestionItem(suggestionId, itemId, data)` — 正常 + 422 校验错误
- `pushSuggestionItems(suggestionId, itemIds)` — 正常 + 409 冲突

**Mock 方式**: vi.mock axios 拦截请求，验证 URL/参数/错误处理。

---

## Task D: 前端 SuggestionDetailView 编辑测试

**覆盖范围**:
- 编辑 total_qty 输入框 → 触发 save → 调用 patchSuggestionItem
- push 按钮对 blocked 状态条目禁用
- push 按钮对已 pushed 建议单禁用

**Mock 方式**: Vue Test Utils mount + stub API 调用 + 断言 DOM 状态。

---

## Task E: 前端 api/client.ts 401 处理测试

**场景**: API 返回 401 → 清除 token → 跳转 /login。

**现有测试**: `client.test.ts` 有基础 setup 测试，但不测 401 拦截器逻辑。

---

## Task F: Playwright E2E

**前置**: 安装 Playwright + 配置 `playwright.config.ts`。

**测试流程**:
1. 登录页输入凭证 → 跳转 Dashboard
2. 导航到建议单列表 → 点击进入详情
3. 编辑 total_qty → 保存 → 验证更新

**环境**: 需要 docker-compose 运行后端 + 种子数据。可用 `playwright.config.ts` 的 `webServer` 配置自动启动前端 dev server。后端 API 用 Playwright 的 `route` API mock。

---

## 不做的事

| 排除项 | 理由 |
|--------|------|
| 引擎 Step1/2/3/6 边界测试 | 经逐项验证已有充分覆盖 |
| 同步层 UPSERT 行为测试 | 需真实 DB，属集成测试 |
| 数据页面（订单/库存/出库）测试 | 只读展示页，风险低 |
| 配置页面测试 | 后端 schema 测试已覆盖校验逻辑 |
| 后端覆盖率提升到 70% | 当前 ~60% 的缺口主要在 sync/API 层薄包装代码，单测 ROI 低 |
