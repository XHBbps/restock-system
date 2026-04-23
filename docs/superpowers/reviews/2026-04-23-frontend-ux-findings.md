# 前端 UX 审查 — 2026-04-23

> **审查范围：** 错误边界 / loading 超时反馈 / 表单禁用状态 / 键盘可访问性 / 三态（空/loading/错） / 前后端状态漂移（generation_status / stale）
> **审查时间：** 2026-04-23
> **审查者：** Claude Code（superpowers agent，Task 11）
> **问题总数：** 17 条 / Critical: 1 / Important: 7 / Minor: 6 / Ack: 3

---

## 问题分级说明

| 级别 | 定义 |
|------|------|
| Critical | 用户可见的白屏 / 功能不可用 / 静默数据错误 |
| Important | 明显的 UX 缺陷，影响操作信心但不阻断业务 |
| Minor | 小的不一致 / 不完善，有优化空间 |
| Ack | 确认已知 / 可接受，1-5 人内部工具场景不值得修复 |

---

## A. 错误边界 / 全局异常

### A-1 — `unhandledrejection` 静默吞错，用户无感知 [Important]

- **位置：** `frontend/src/main.ts:26-28`
- **现状：** `window.addEventListener('unhandledrejection', ...)` 仅 `console.error`，没有向用户展示任何提示。Vue 的 `app.config.errorHandler` 覆盖了组件内的同步错误，但 Promise rejection 如果逃出了所有 async/await 的 try/catch（比如 `onMounted(async () => { ... })` 外层忘了 await 某个调用），会进入这里被静默吞掉。对于 1-5 人内部工具，这不会白屏，但运营者完全不知道某次请求失败了。
- **建议：** 在 `unhandledrejection` 处理器里也 `ElMessage.error(...)` — 至少对非生产环境展示。或加一个较宽松的消息（"后台操作出现意外，请检查控制台"）。
- **工作量：** S（2 行）

### A-2 — `app.config.errorHandler` 已配置，但提示文案过于泛化 [Ack]

- **位置：** `frontend/src/main.ts:20-23`
- **现状：** 全局 errorHandler 存在（✅），提示为"操作异常，请刷新页面重试"。对于 Vue 渲染错误这是最合适的兜底，内部工具不需要更具体的文案。
- **结论：** 可接受，Ack。

### A-3 — axios 401 重定向有极端 race 条件 [Minor]

- **位置：** `frontend/src/api/client.ts:30-38`
- **现状：** 401 → `auth.clearAuth()` → 动态 import router → `router.replace(...)` 是异步链。在极低概率下（import 延迟 + 用户极快地点击导航触发第二个 401 请求），可能产生两次 replace 并都带着不同的 redirect 参数写入 query，后一次会覆盖前一次（实际无害，只是 redirect 可能丢失当前页面）。
- **建议：** 加防重入 flag（`let redirecting = false`）避免重复跳转。
- **工作量：** S

---

## B. Loading 超时反馈

### B-1 — 任务轮询无上限时间（生成/快照刷新可无限等）[Important]

- **位置：** `frontend/src/stores/task.ts`
- **现状：** `startPolling` 每 2 秒轮询，`MAX_RETRY=3` 仅针对**网络错误**（请求本身失败）。如果后端 worker 卡住但任务还在 `running` 状态，前端会永远轮询，`TaskProgress` 永远显示转圈，用户不知道是否要手动干预。`networkErrors` 变量在 store 里存了但 **`TaskProgress.vue` 根本不读 `networkErrors`**（组件没有引入它），这段错误状态是死代码。
- **建议：**
  1. `TaskProgress.vue` 应读取 `taskStore.networkErrors[taskId]` 并显示错误 UI。
  2. `task.ts` 加最大轮询次数（如 `MAX_POLL = 150` = 5 分钟），超出后将状态设为超时并调用 `onTerminal`（携带合成的 failed task 对象），触发 UI 提示"任务超时，请刷新页面确认状态"。
- **工作量：** M

### B-2 — 首页 Dashboard 初始加载无全局 `v-loading`，首屏出现"数字 0"闪烁 [Important]

- **位置：** `frontend/src/views/WorkspaceView.vue:20-135`
- **现状：** `loading` ref 存在，但模板中**没有** `v-loading` 指令覆盖整个页面或各 section card。加载期间：
  - 统计卡片 `DashboardStatCard` 显示 `0`（`data?.restock_sku_count ?? 0`）
  - 急需补货列表显示 `el-empty`（`data` 为 null，`!data` 为 true）
  - 快照状态标签显示"等待生成快照"（data 为 null 时）
  
  用户会看到 0→真实值 的闪变，以及 empty 状态和真实数据之间的切换，可能误判为"没有数据"。
- **建议：** 至少对 `<div class="workspace-view">` 加 `v-loading="loading"`，或对各 section 独立 loading。同时 `snapshotStatusLabel` 应在 `loading` 期间返回"加载中..."而非"等待生成快照"。
- **工作量：** S

### B-3 — axios 超时 30 秒，但 UI 层没有超时提示 [Minor]

- **位置：** `frontend/src/api/client.ts:14`
- **现状：** axios `timeout: 30000` 已设，超时会触发 `AxiosError`（`code=ECONNABORTED`）。`getActionErrorMessage` 里没有处理 `ECONNABORTED`，会 fallback 到 `!axiosError.response`（无 response），提示"后端服务不可用，请确认后端已启动且前端代理目标配置正确"——对于一个"服务慢"的场景，这条提示容易让用户误以为是环境问题。
- **建议：** 在 `apiError.ts` 里检查 `error.code === 'ECONNABORTED'` 或 `error.message.includes('timeout')`，提示"请求超时，请稍后重试"。
- **工作量：** S

---

## C. 表单提交防抖 + 禁用

### C-1 — `AppLayout` 修改密码弹框关闭后表单不重置 [Minor]

- **位置：** `frontend/src/components/AppLayout.vue:267-297`
- **现状：** `el-dialog` 没有 `destroy-on-close`，`pwdForm` 是 `reactive`，关闭弹框只是 `showPasswordDialog.value = false`，下次打开时旧密码字段仍然保留。若修改密码成功后（会跳 login），不是问题；但用户取消后重新打开，上次输入的旧密码仍然在框里。
- **建议：** 弹框的 `@close` 事件重置 `pwdForm`（或加 `destroy-on-close`）。
- **工作量：** S（3 行）

### C-2 — 所有表单 Loading 状态防重复提交覆盖完整 [Ack]

- **位置：** 全站表单
- **现状：** 逐一核查：
  - `LoginView`：`loading` ref + `:disabled="loading"` ✅
  - `AppLayout` 改密码：`pwdLoading` + `:loading="pwdLoading"` ✅ 
  - `GlobalConfigView` 保存：`saving` ref ✅
  - `UserConfigView` 创建/编辑/重置密码：`saving` ref ✅
  - `RoleConfigView` 保存：`saving` ref ✅
  - `SuggestionListView` 生成按钮：`generating` + `:disabled="!toggle?.enabled || generating"` ✅
  
  全覆盖，无遗漏。Ack。

---

## D. 键盘可访问性

### D-1 — 修改密码弹框缺少 Enter 键提交 [Important]

- **位置：** `frontend/src/components/AppLayout.vue:151-167`
- **现状：** 登录页 `el-input` 有 `@keyup.enter="handleLogin"` ✅，但 `AppLayout` 的修改密码弹框三个 `el-input` 均没有 `@keyup.enter`。用户习惯 Enter 提交，需要移动鼠标到"确认修改"按钮。
- **建议：** 给"确认密码"字段（最后一个输入框）加 `@keyup.enter="handleChangePassword"`，或 `el-form` 用 `@submit.prevent="handleChangePassword"`。
- **工作量：** S（1 行）

### D-2 — `UserConfigView` 和 `RoleConfigView` 表单弹框缺少 Enter 键提交 [Important]

- **位置：** `frontend/src/views/UserConfigView.vue:86-135`（3 个 dialog）, `frontend/src/views/RoleConfigView.vue:60-135`
- **现状：** 新建用户 / 编辑用户 / 重置密码 / 新建角色 / 编辑角色弹框里的 `el-input` 均无 `@keyup.enter`。
- **建议：** 至少给最后一个输入框加 Enter 提交，或 wrap `el-form` 用 `@submit.prevent`。
- **工作量：** S（各 1-2 行）

### D-3 — `SuggestionDetailDialog` 禁用了 Esc 关闭 + 隐藏了默认 × 按钮 [Minor]

- **位置：** `frontend/src/components/SuggestionDetailDialog.vue:6-8`
- **现状：** `:show-close="false"` 隐藏 Element Plus 默认 × 按钮（有自定义 × 替代），`:close-on-click-modal="false"` 禁止点击遮罩关闭。默认 `close-on-press-escape` 为 `true`，所以 Esc 键仍可关闭——但自定义 × 按钮没有键盘 focus ring（只有 `.dialog-close-btn:focus-visible` 的 `outline` 样式，实际上 `button[type=button]` 在 Safari / FireFox 的 tabindex 处理上可能 skip），且自定义 × 的 `tab` 顺序处于 header 区，顺序合理。
- **建议：** 不用大改，确认 `.dialog-close-btn` 的 `all: unset` 不会清掉 tabindex。`all: unset` 会清掉 user-agent 的 `display` 但保留 tab 可聚焦性（button 的 tabindex 默认 0，`all: unset` 不会改变可聚焦性），整体 OK。
- **工作量：** 0（确认即可）

---

## E. 数据三态

### E-1 — Dashboard 初始 loading 期间 empty 态和 loading 态混叠 [Critical]

- **位置：** `frontend/src/views/WorkspaceView.vue:46,76`
- **现状（具体场景）：**
  - 第一次进入页面，`loading=true`，`data=null`
  - 急需补货 SKU 列表：`v-if="data && data.top_urgent_skus.length > 0"` → false → `el-empty` "暂无急需补货项" **立即出现**
  - 统计卡片全显示 `0`
  - 用户在网络较慢时会看到空图标 + 0 数值的"假空状态"，持续 1-3 秒后数据填充
  
  这是唯一在初始加载期间可能产生**语义错误信号**的场景（用户可能以为"没有补货需求"，实际是在加载中）。
- **建议：** `loading.value = true` 时，统一用 `v-loading="loading"` 覆盖 workspace-view 容器，且 `snapshotStatusLabel` computed 里加 `if (loading.value) return '加载中...'` 分支（注意 `loading` 是 ref，computed 里要用 `loading.value`）。
- **严重度说明：** 对于 1-5 人已知系统来说白屏不会发生，但**语义错误的 empty 状态**（"暂无补货需求"）会让用户误操作（以为不需要补货而跳过今天的工作），因此升为 Critical。
- **工作量：** S

### E-2 — `SuggestionListView` loading 时 empty 态和 loading 态隔离正确 [Ack]

- **位置：** `frontend/src/views/SuggestionListView.vue:41-42`
- **现状：** `v-if="!loading && !suggestion"` — 等加载完成才显示空状态，不会产生混叠 ✅。
- **结论：** Ack，已正确处理。

### E-3 — 错误态后三态归零：部分视图 catch 后 data 不 reset，可能残留旧数据 [Minor]

- **位置：** `frontend/src/views/SuggestionListView.vue:147-157`，各数据视图
- **现状：** `SuggestionListView.loadCurrent` 的 catch 块里只处理 404（`suggestion.value = null`），其他错误只 `ElMessage.error` 但 `suggestion` 保持原值，这意味着下次用户操作时可能操作到旧数据（一般不成问题，因为 ElMessage 已提示失败）。WorkspaceView 错误时正确地 `data.value = null`（line 321）。
- **建议：** 不紧急，对所有 catch 块检查是否需要清空数据引用，特别是涉及删除后刷新的场景。
- **工作量：** S（视图逐一检查）

---

## F. 前后端状态漂移

### F-1 — `generation_status='failed'` 快照在历史详情弹框中无特殊提示 [Important]

- **位置：** `frontend/src/components/SuggestionDetailDialog.vue`，`frontend/src/api/snapshot.ts:15`
- **现状：** `SnapshotOut` 有 `generation_status: 'generating' | 'ready' | 'failed'` 字段（Task 2 新增），但 `SuggestionDetailDialog` 展示版本列表时没有读取该字段：版本列表只显示 `V{{ snap.version }}` + `{{ snap.item_count }} 条` + `{{ formatDateTime(snap.exported_at) }}`，failed 快照和 ready 快照在 UI 上**完全相同**。
  
  用户点击一个 `generation_status='failed'` 的快照后，`getSnapshot` 请求会得到一个 `items` 可能为空或不完整的详情，用户看到的是"该版本无条目"——这和实际语义（快照生成失败）完全不同，用户无法区分"该版本真的没条目"和"生成失败"。
- **建议：**
  1. 版本列表项：当 `snap.generation_status === 'failed'` 时，在 `.version-item__head` 旁边加一个红色警告标记或 `el-tag type="danger"` "生成失败"。
  2. 详情区：`currentSnapshot?.generation_status === 'failed'` 时，在表格上方显示 `el-alert type="error"` "此快照生成失败，数据可能不完整"。
  3. 版本列表项：当 `generation_status === 'generating'` 时，显示 loading 图标（理论上用户应该在任务完成前不会看到版本，但 stuck_generating 可能留下此状态）。
- **工作量：** S-M

### F-2 — Dashboard `snapshot_status='refreshing'` 有标签显示，但 `missing` 态文案不够区分度 [Minor]

- **位置：** `frontend/src/views/WorkspaceView.vue:191-205`
- **现状：**
  - `refreshing` → 黄色 tag "快照刷新中" ✅（伴随 TaskProgress 进度条）
  - `missing` + 有权限 → 蓝色 tag "快照待刷新" ✅
  - `missing` + 无权限 → 蓝色 tag "暂无快照" — 对于无权限用户，看到这条不知道是正常空状态还是系统异常
  - `ready` → 绿色 tag "快照已缓存" ✅
  
  `missing` + 无权限场景是最模糊的：用户知道系统有数据，但看到"暂无快照"，可能误认为是 bug 而去联系管理员。
- **建议：** `missing` + 无权限时改为"信息总览待刷新（联系管理员）"，或加一个 tooltip 说明。
- **工作量：** S（1 行文案）

### F-3 — 任务轮询网络错误 `networkErrors` 在 `TaskProgress.vue` 中未渲染（死代码） [Important]

（已在 B-1 中提及，此处补充漂移维度）

- **位置：** `frontend/src/stores/task.ts:43-44`，`frontend/src/components/TaskProgress.vue`
- **现状：** `taskStore.networkErrors[taskId]` 记录了网络连续失败 3 次的错误消息，但 `TaskProgress.vue` 完全没有读取它（通过检查全文，组件只读 `task.error_msg`），导致：
  - 网络中断 → 3 次失败 → polling 停止 → `TaskProgress` 卡在最后一次 task 状态（可能是 `running`）永远不更新
  - 用户以为任务还在运行，实际上前端已放弃轮询
  - 这是一个**前后端状态漂移**的典型案例：后端任务可能已成功，但前端永远停在"运行中"
- **建议：** `TaskProgress.vue` 引入 `taskStore.networkErrors`，当 `networkErrors[taskId]` 有值时展示错误 UI（如红色提示"网络中断，请刷新页面查看任务状态"），替代当前卡死的进度条。
- **工作量：** S（5-8 行）

---

## 汇总表

| 编号 | 严重度 | 模块 | 问题 | 工作量 |
|------|--------|------|------|--------|
| E-1 | Critical | WorkspaceView | Dashboard 初始加载期 empty 状态误导用户 | S |
| B-1 | Important | TaskProgress + task store | 轮询无上限 + networkErrors 死代码 | M |
| B-2 | Important | WorkspaceView | 首屏无 v-loading 导致 0/empty 闪变 | S |
| D-1 | Important | AppLayout | 修改密码弹框无 Enter 键提交 | S |
| D-2 | Important | UserConfigView / RoleConfigView | 用户/角色表单弹框无 Enter 键提交 | S |
| F-1 | Important | SuggestionDetailDialog | generation_status=failed 快照无提示 | S-M |
| F-3 | Important | TaskProgress + task store | networkErrors 未渲染（任务状态漂移） | S |
| A-1 | Important | main.ts | unhandledrejection 静默吞错 | S |
| A-3 | Minor | client.ts | 401 重定向有极端 race 条件 | S |
| B-3 | Minor | apiError.ts | axios 超时错误提示语义不准确 | S |
| C-1 | Minor | AppLayout | 修改密码弹框关闭后表单不重置 | S |
| E-3 | Minor | SuggestionListView | 错误态后可能残留旧数据 | S |
| D-3 | Minor | SuggestionDetailDialog | 自定义 × 按钮键盘可聚焦性 | 0 |
| F-2 | Minor | WorkspaceView | missing+无权限快照文案不够区分 | S |
| A-2 | Ack | main.ts | errorHandler 全局兜底存在 | 0 |
| C-2 | Ack | 全站表单 | 防重复提交覆盖完整 | 0 |
| E-2 | Ack | SuggestionListView | loading/empty 隔离正确 | 0 |

---

## 总结

系统整体错误处理框架相对完善（全局 errorHandler + axios 拦截 + getActionErrorMessage 工具函数），表单防重复提交覆盖完整，内部工具场景不会白屏崩溃。

最需要优先处理的问题有两类：

1. **状态漂移类（B-1 / F-1 / F-3）**：`networkErrors` 是存了但没渲染的死代码，任务轮询无超时上限，`generation_status='failed'` 的快照在 UI 上与正常快照无区分——这三条合起来描述了同一个风险：后端任务/快照进入异常态，前端无从得知。

2. **Dashboard 首屏三态混叠（E-1 + B-2）**：初始 loading 期间 empty 态抢先出现，用户可能看到"暂无急需补货项"或"统计数值 0"而误判业务现状。对于 1-5 人内部工具这是 Critical，因为空状态有明确的业务含义。

---

## 建议 follow-up plan

如有后续 patch sprint，建议优先级如下：

**P0（本次迭代内）：**
- E-1 + B-2：WorkspaceView 加 `v-loading` + snapshotStatusLabel loading 分支（约 30 min）
- F-3 + B-1：TaskProgress.vue 读取 `networkErrors`（约 1h）；task store 加最大轮询次数（约 30 min）

**P1（下个迭代）：**
- F-1：SuggestionDetailDialog 展示 generation_status 异常标记（约 1-2h）
- D-1 + D-2：各弹框加 Enter 键提交（约 30 min）
- B-3：apiError.ts 加 timeout 特判（约 15 min）

**P2（按需）：**
- A-1、A-3、C-1、E-3、F-2：各约 15-30 min，可在日常维护中顺手处理
