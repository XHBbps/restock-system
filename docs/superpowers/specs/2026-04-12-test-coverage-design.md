# 测试覆盖提升设计文档

> 设计日期: 2026-04-12
> 前置: `docs/superpowers/specs/2026-04-12-full-system-review.md` 全链路 Review
> 当前基线: 后端 169 passed / 55% 覆盖率阈值，前端 8 个测试 / ~2% 覆盖率

---

## 目标

按风险分层补充测试，优先覆盖"出 bug 代价最高"的路径：

1. 修复 Step5 ceil 回归（Review 修复引入的真实缺陷）
2. 补充推送零数量测试（验证 P2-7 修复）
3. 前端核心页面编辑逻辑单元测试

## 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 引擎边界测试数量 | 1 个（Step5 ceil） | 其余 7 个场景经逐项验证：已覆盖或生产不可达 |
| Step5 仓分配取整 | 改回 `round()` | 仓分配是固定总量的分配，不适用"宁多勿少"；`ceil` 导致 sum > country_qty |
| 前端测试框架 | Vitest + Vue Test Utils | 项目已配置，CI 已集成 |
| Playwright E2E | **拆为独立 plan** | 未安装、需下载浏览器+配置+mock 后端，工作量是 Task A-C 的 2-3 倍 |

## 排除项（经验证）

| 原 Task | 排除理由 |
|---------|---------|
| ~~Task C: api/suggestion.ts 测试~~ | 3 行 axios wrapper，零业务逻辑，测它 = 测 axios |
| ~~Task E: client.ts 401 测试~~ | `client.test.ts:46-74` 已完整覆盖（清 token + 非 401 不清） |
| ~~Task F: Playwright E2E~~ | 拆为独立 plan（未安装、配置重、scope 大） |
| ~~Task D 推送按钮禁用~~ | SuggestionDetailView 无 push 按钮，scope 已修正 |

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

**修复**: `step5_warehouse_split.py:191` 改回 `round()`。同时移除 line 189 的 `max(..., 0)` 保护（不再需要）。Step3/Step4 保持 `ceil()`。

**测试**: 新增 3+ 仓不等比例场景，断言 `sum(breakdown) == country_qty`。

---

## Task B: 推送 total_qty=0 测试

**场景**: 用户 PATCH total_qty→0 后推送，代码应抛 ValueError。

**代码路径**: `pushback/purchase.py:74-80` — 过滤 total_qty=0 条目，空列表时 raise。

**测试**: 构造全部 total_qty=0 的 items，断言 ValueError（"所有条目的 total_qty 均为 0"）。

---

## Task D: 前端 SuggestionDetailView 编辑逻辑测试

**实际可测逻辑**（经代码验证）:
- `isEditable(item)`: suggestion.status !== 'archived' && item.push_status !== 'pushed'
- `save(item)`: 调用 `patchSuggestionItem` → 成功后 `load()` 刷新 → 失败时 `ElMessage.error`
- Save 按钮 `:disabled="!isEditable(item) || !hasChanges(item)"`

**测试用例**:
1. archived 建议单的条目 → isEditable 返回 false → save 按钮 disabled
2. pushed 条目 → isEditable 返回 false
3. draft 建议单 + pending 条目 + 已修改 → save 按钮 enabled → 点击触发 API 调用

**Mock 方式**: Vue Test Utils mount + vi.mock api/suggestion + 断言 DOM 状态和函数调用。

---

## 不做的事

| 排除项 | 理由 |
|--------|------|
| 引擎 Step1/2/3/4/6 边界测试 | 经逐项验证已有充分覆盖（169 个测试） |
| api/suggestion.ts 单元测试 | 3 行 axios wrapper，无逻辑 |
| client.ts 401 处理测试 | 已有 4 个拦截器测试覆盖 |
| 同步层 UPSERT 行为测试 | 需真实 DB，属集成测试 |
| 数据/配置页面测试 | 只读展示 + 后端 schema 已覆盖 |
| Playwright E2E | 拆为独立 plan |
