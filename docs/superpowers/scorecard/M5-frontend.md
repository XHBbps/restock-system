# M5 前端数据页 评分报告

> 模块范围：`frontend/src` 全部（views + 组件 + utils + stores + api 封装 + 构建配置 + Dockerfile + nginx.conf）
> 评分日期：2026-04-11
> 评分人：Claude (Opus 4.6) — 只读审计
> 模块特殊地位：**D9 用户体验标尺源头模块**；M5 是全项目唯一完整覆盖前端 UX 的模块。

---

## 构建/类型/测试结果

| 项 | 结果 | 备注 |
|---|---|---|
| `vue-tsc --noEmit` | ✅ 0 错误 | exit 0，无任何类型错误 |
| `vite build` | ✅ 成功 | 耗时 11.14 s，有 chunk-size warning（element-plus/charts 超 500 KB） |
| `vitest run` | ✅ 33 passed / 8 files | tableSort(12) + auth(4) + client(4) + TaskProgress(2) + element(3) + monitoring(3) + allocation(2) + guard(3) |
| `eslint` | ✅ exit 0 | 无 warning/error（配合 `--max-warnings 0` 脚本定义） |

**vite build dist 分布**（按 gzip 排序，仅关注 top）：
- `element-plus-BysntHKP.js`：906.32 KB / **293.61 KB gz** ⚠️ > 500 KB warning
- `charts-CpdnBEWG.js`（ECharts+vue-echarts）：557.23 KB / **188.66 KB gz** ⚠️ > 500 KB warning（**懒加载**，仅 Workspace/ApiMonitor/PerformanceMonitor 拉取）
- `framework-CHi8M_St.js`（Vue+Router+Pinia+lucide）：123.24 KB / 46.27 KB gz
- `element-plus-Plm10Dc1.css`：352.47 KB / 47.24 KB gz
- `client-D-bRuSsy.js`（axios 等）：37.63 KB / 15.06 KB gz
- `index-D3dBjzDk.js`：10.27 KB / 3.66 KB gz
- 所有 view chunk：2.3 – 16.6 KB（最大 ZipcodeRule 16.6 KB）
- **dist 总体积**：2.3 MB（gzip 后首屏 index+framework+element-plus+client ≈ **358 KB gz**，不含懒加载的 charts）

---

## D1 功能完整性 — 3

**判据匹配**：满足 Rubric 3 级（所有主流程端到端闭环：登录/登出 + Workspace 总览 + Suggestion 列表/详情/推送 + 7 个数据页 + 2 个同步控制台 + 3 个监控页 + 2 个全局配置页 + 跨页选择 + TaskProgress 实时轮询 + 401 自动登出 + 路由守卫），边界处理可见（404 路由 NotFoundView + 大量 el-empty 空态 + `404` 响应在 SuggestionList 专门静默而非 error，`selectedIds` 跨分页维护 +「select-all」跨页全量选）；未满足 4 级（无端到端 e2e 测试，33 个 vitest 集中在 utils/store/guard/client 单测，**整个 views/ 目录零组件测试**，仅 `TaskProgress.test.ts` 2 个组件测试；分页+筛选+跨页选择+sort 四状态交互无测试守护）

**关键证据**：
- `frontend/src/router/index.ts:178-181` — 路由守卫 `authGuard` 全局接入 `useAuthStore().isAuthenticated`
- `frontend/src/router/index.ts:11-158` — 17 个路由 + 10+ 遗留 redirect，覆盖 Home/Restock/Data/Settings 四段
- `frontend/src/views/SuggestionListView.vue:260-305` — 跨页选择（`selectedIds` + `handleSelectAll` 跨页汇总 + `syncTableSelection` 回写当前页）
- `frontend/src/views/SuggestionListView.vue:166-178` — 404 静默（`e.response?.status === 404` 返回 empty 而非 error）
- `frontend/src/api/client.ts:23-30` — 401 响应拦截器 `auth.clearToken()` + `window.location.href = '/login'` 自动跳转
- `frontend/src/components/TaskProgress.vue:70-83` — 任务进度轮询接入 `useTaskStore().startPolling()`，订阅 terminal 事件
- `frontend/src/stores/task.ts:17-42` — 2 秒轮询 + TERMINAL_STATES 终态集合 + 失败即停
- 所有数据页 `page_size: 5000` 一次拉全量：`api/data.ts:60,98,130,198,232` + `api/suggestion.ts:66` + `api/config.ts:40`

**差距**：无 e2e，跨页选择 + 筛选 + 排序的交互矩阵零组件测试（尤其 `handleSelectAll` 的 suppressSelectionSync 时序）。

**对照 M1=3 / M2=3 / M3=3 / M4=3**：M5 同级 3 分。M5 比后端模块的优势在于"主链路全页面实际可交互"，劣势是"整个 views/ 零测试"——与 M4 queue/worker/reaper 零单测同构问题，故持平。

---

## D2 代码质量 — 3

**判据匹配**：满足 Rubric 3 级（`vue-tsc --noEmit` **0 错误**，`eslint --max-warnings 0` **exit 0 / 零输出**，统一 format 脚本 prettier + organize-imports，vitest 33 tests 全 pass，utils 复用度高——`getActionErrorMessage` 跨 6 文件 15 处、`format/warehouse/countries/status/tableSort/apiError` 齐备，组件复用 `PageSectionCard` 10 页一致、`TablePaginationBar` 各数据页复用、`SkuCard` 表格+Workspace 复用，命名清晰无缩写，严格 TS 泛型使用），未满足 4 级（**views 零组件单测**，整体覆盖率 vitest threshold 仅 2%，巨型文件：`ZipcodeRuleView.vue` **1276 行** + `SuggestionDetailView.vue` 729 行，未抽出子组件；数据页间仍有 filter+sort+reactive 模板重复未抽通用 composable）

**关键证据**：
- `frontend/package.json:10` — `"lint": "eslint --ext .ts,.tsx,.vue --max-warnings 0 src"` + eslint 实际 exit 0
- `frontend/package.json:12` — `type-check: vue-tsc --noEmit`（本次运行 exit 0）
- `frontend/vitest.config.ts:19-21` — `thresholds.statements: 2` 极低基线（P2）
- 巨型文件：`wc -l src/views/ZipcodeRuleView.vue` **1276 行**；`SuggestionDetailView.vue` 729 行；`SuggestionListView.vue` 423 行
- 共享 utils 使用广度：Grep `from '@/utils/{format,warehouse,countries,status,tableSort,apiError}'` → **39 处 / 18 文件**
- `PageSectionCard` 使用：10 个 views 覆盖（`SuggestionList/History/GlobalConfig/ZipcodeRule/DataShops/DataWarehouses/DataProducts/DataOrders/DataInventory/DataOutRecords`）
- `frontend/src/utils/status.ts:13-26` — 枚举→中文 label 的统一 StatusMeta 模式，避免各 view 硬编码
- `frontend/src/utils/apiError.ts:3-36` — 统一 axios error 正规化，但仅 15 处调用，很多 catch 块仍是硬编码（如 `DataOrdersView.vue:205` `ElMessage.error('加载失败')`）

**差距**：ZipcodeRule 1276 行是明显代码异味需拆分；`DataOrdersView.vue:204-208` 直接 `ElMessage.error('加载失败')` 吞掉 error 未走 `getActionErrorMessage`；views 零组件测试。

**对照 M1=2 / M2=3 / M3=2 / M4=2**：M5 **与 M2=3 持平**，高于 M1/M3/M4。理由：M5 有 lint + type-check 通过（后端模块共性无 mypy 校验），vitest 33 tests 覆盖 utils/store 关键路径，eslint 0 warning——超出 Rubric 2 级；尚未达 4 级因 views 零测试 + 巨型文件。

---

## D3 安全性 — 2

**判据匹配**：满足 Rubric 2 级（**0 处 `v-html` / `innerHTML` / `dangerouslySet`** 零 XSS 注入面，所有请求走 axios + JWT Bearer 拦截器 + 401 自动登出，`baseURL: '/'` 同源策略无 CORS 暴露，无明文密钥或 token 打印到 console——`console.log/warn/error` **0 处**），未满足 3 级（**token 存储在 localStorage** 而非 HttpOnly cookie——公网 XSS 视角下是典型风险，`stores/auth.ts:8` + `stores/sidebar.ts:8,10`；**无 npm audit / CVE 扫描**，无 CI 依赖扫描；**无 Content-Security-Policy headers**——`nginx.conf:1-31` 缺 X-Frame-Options/X-Content-Type-Options/CSP/Referrer-Policy；无 subresource integrity；无 token 过期主动校验前端）

**关键证据**：
- Grep `v-html|innerHTML|dangerouslySet in src/` → **0 matches**（XSS 注入面清洁）
- `frontend/src/stores/auth.ts:8,14,19` — `localStorage.getItem/setItem/removeItem(TOKEN_KEY)` 全程 localStorage
- `frontend/src/api/client.ts:11-18,23-30` — Bearer 注入 + 401 clearToken + redirect
- Grep `console\.log|console\.error|console\.warn in src/` → **0 matches**（无敏感日志打印）
- `frontend/nginx.conf:1-31` — 仅有 gzip + static cache + SPA fallback + deny /. ；**无安全 headers**
- Grep `Sentry|rollbar|otel in frontend/` → 0 matches
- `frontend/package-lock.json` 存在但 `package.json:6-17 scripts` 无 `audit` / `audit-ci` 命令

**差距**（P0/P1 候选）：
- 🟡 **P1-M5-1**：token localStorage 存储在公网 XSS 场景下是核心风险（与后端 P0-2 公网假设覆盖关联）。短期内可维持（单用户场景），但应在 `docs/PROGRESS.md` 记录决策。
- 🟡 **P1-M5-2**：nginx.conf 缺安全 headers（CSP、X-Frame-Options、Referrer-Policy、Permissions-Policy）。与 Caddyfile 是否统一补齐要核对——此为 M5 与 Caddy 部署层的边界。
- 🟡 **P1-5 通用**：无 npm audit CI 扫描（跨模块共性）。

**对照 M1=2 / M2=2 / M3=2 / M4=2**：M5 同级 2 分。M5 独有亮点：**零 XSS 注入面 + 零 console 敏感日志**；独有缺口：**token localStorage** + 无安全 headers。

---

## D4 可部署性（按新口径实地评分） — 3

**判据匹配**：满足 Rubric 3 级（`frontend/Dockerfile` 标准两阶段构建 node:20-alpine → nginx:1.27-alpine + HEALTHCHECK wget，`vite.config.ts:36-55` **生产 sourcemap=false** + `manualChunks` 精准分包 element-plus/charts/framework，`nginx.conf` 含 gzip + 静态资源强缓存 + SPA fallback，`deploy/docker-compose.yml:124-137` 接入 frontend 服务 + `memory: 256m` 资源限制 + 依赖后端 healthy，`frontend/.env.example` 存在文档化 `VITE_API_PROXY_TARGET`，构建耗时 **11.14 s** 可接受），未满足 4 级（共性问题：无 CI/CD + 蓝绿 + IaC + 多环境 + 构建产物签名；M5 独有：`.env.example` 仅 1 行未覆盖生产前端环境变量；vite build 有 chunk-size warning 超 500KB 未处理——虽然 element-plus/charts 已分包但仍超阈值）

**关键证据**：
- `frontend/Dockerfile:1-23` — 两阶段 builder (node:20-alpine) + runtime (nginx:1.27-alpine) + HEALTHCHECK
- `frontend/vite.config.ts:36` — `sourcemap: false`（生产不暴露源码映射）
- `frontend/vite.config.ts:40-55` — `manualChunks` 手动拆 charts/element-plus/framework 三个 vendor bucket
- `frontend/nginx.conf:8-14,17-20,23-25` — gzip + /assets 强缓存 `immutable 1y` + SPA try_files fallback
- `deploy/docker-compose.yml:124-137` — frontend 服务定义 + 依赖 backend healthy + `memory: 256m`
- `deploy/docker-compose.yml:139-158` — Caddy 反代 frontend + backend，生产入口统一在 Caddy
- `frontend/.env.example:1` — `VITE_API_PROXY_TARGET=http://localhost:8000`（**仅 dev 代理，无生产 VITE_* 环境变量**）
- `frontend/package.json:8` — `"build": "vue-tsc --noEmit && vite build"`（build 即 type-check）
- build 产物 total 2.3 MB，chunk-size warning 但 manualChunks 已尽力

**差距**：
- chunk-size warning 未显式配置 `chunkSizeWarningLimit` 或进一步细分 element-plus（按需引入会更好——目前全量引入增加 900KB）
- `.env.example` 过于简陋（1 行），未文档化 build-time / runtime 前端配置

**对照 M1=3 / M2=3 / M3=3 / M4=3**：M5 同级 3 分。M5 的 D4 独有优势是前端产物全链路可复现（Dockerfile → nginx → Caddy 反代 → 资源限制），独有缺口是 element-plus 全量引入未按需。

---

## D5 可观测性 ◦（低权重） — 2

**判据匹配**：满足 Rubric 2 级（`ElMessage.error/warning` **39 处跨 18 文件** 覆盖面广，请求失败用户反馈到位，401 自动跳转 + token 清理，后端 `request_id` 中间件存在且前端 axios response 自动携带——`M1` calibration 有证据；前端无 console.log 污染，`ElMessageBox.confirm` 用在高危操作前），未满足 3 级（**无 Sentry / Rollbar / 自研前端错误上报**——Grep 全仓零命中，**无 Web Vitals / performance API 采集**，`frontend/src/views/WorkspaceView.vue:199-205` 关键 dashboard 加载失败**静默吞异常**仅 `data.value = null` 无 ElMessage 提示，TaskProgress 轮询失败 `stores/task.ts:34-38` 吞异常仅 stop polling 无任何用户反馈）

**关键证据**：
- Grep `ElMessage\.error|ElMessage\.warning in src/` → 39 处 / 18 文件（广度覆盖）
- `frontend/src/api/client.ts:23-30` — 401 响应拦截 + 自动 redirect
- Grep `Sentry|rollbar|otel|opentelemetry in frontend/` → **0 matches**
- `frontend/src/views/WorkspaceView.vue:199-205` — dashboard 加载失败仅 `data.value = null` 空态，**无错误提示**
- `frontend/src/stores/task.ts:34-38` — 轮询失败 `catch { polling.value.delete(taskId); return }` **吞异常**
- `frontend/src/views/data/DataOrdersView.vue:204-208` — `catch { ElMessage.error('加载失败') }` 吞错误内容不经 `getActionErrorMessage`

**差距**：
- 🟢 P2-M5-1：WorkspaceView 首屏失败静默
- 🟢 P2-M5-2：TaskProgress 轮询失败无任何用户提示（断网时任务卡死在"运行中"）
- 🟡 P1-M5-3：数据页 catch 块硬编码 "加载失败" 字符串未使用 `getActionErrorMessage`（`DataOrdersView:205`、`DataWarehousesView`、`DataShopsView` 等，仅 SuggestionList/Detail/SyncConsole/SyncLog/ZipcodeRule 6 文件用了 utils）
- 共性：无前端 RUM / Sentry / OpenTelemetry

**对照 M1=3 / M2=3 / M3=3 / M4=3**：**M5 为 2 分，比后端模块低 1 级**。理由：后端模块都有 structlog JSON 日志 + request_id 自动绑定 + api_call_log 结构化事件线（符合 Rubric 3 "request 追踪"），而前端无 Sentry 无错误上报 + 关键页面有静默吞异常。Rubric 3 要求"前端错误上报（Sentry/自研）"明确未达标。

---

## D6 可靠性 — 3

**判据匹配**：满足 Rubric 3 级（`getActionErrorMessage` 分类处理 502/500/network-down 三档回落 + loc:msg 格式化，401 自动跳转 + token 清理 **幂等**，大量 `el-empty` + `el-loading` + `el-alert` 空/加载/错误状态完整——`el-empty` 分布在 13 个 view，`v-loading` 在 13 个 view，TaskProgress 组件支持 `taskId null` 清空 + `watch` 切换 + `onBeforeUnmount` 清理轮询，`nextTick(() => table.clearSelection())` 筛选变化时清除跨页选择**防止脏选**，路由守卫无认证即 `redirect query` 记录原路径以登录后回跳），未满足 4 级（无 axios 重试策略如 axios-retry，无离线 cache/PWA，TaskProgress 轮询**网络断开后立即停止**无指数退避重试 `stores/task.ts:34-38`，无熔断或断路保护，无 chaos test）

**关键证据**：
- `frontend/src/utils/apiError.ts:9-36` — network-down / 500/ 业务 message / detail array / fallback 五档处理
- `frontend/src/api/client.ts:23-30` — 401 幂等处理（检查 pathname 避免登录页自己跳自己）
- `frontend/src/views/SuggestionListView.vue:244-248,310-313` — 筛选/sort 变化时清除跨页 selection `nextTick(() => tableRef.value?.clearSelection())`
- `frontend/src/views/SuggestionListView.vue:166-178` — 404 特殊静默路径（不报 error 而是显示 el-empty）
- `frontend/src/views/LoginView.vue:87-91` — 423 锁定状态专门分支提示"账号已锁定"
- Grep `el-empty|el-skeleton|v-loading|el-alert in views/` → **30 处 / 13 文件**
- `frontend/src/components/TaskProgress.vue:70-83` — watch taskId 切换、`onBeforeUnmount` 停止轮询、防止内存泄漏
- `frontend/src/stores/task.ts:34-38` — 轮询失败 silent stop（反面证据：无重试退避）

**差距**：
- 🟡 P1-M5-4：TaskProgress 断网即停 + 无重连退避，导致长任务在网络抖动时错过 terminal 事件，用户需手动刷新
- 共性：无熔断器 / 降级策略 / chaos test

**对照 M1=3 / M2=3 / M3=3 / M4=3**：M5 同级 3 分。M5 的独有亮点是 `getActionErrorMessage` 五档处理 + 跨页选择在筛选变化时自清理的细节。

---

## D7 可维护性 — 2

**判据匹配**：满足 Rubric 2 级（`frontend/README.md` 存在但非常简单——**仅 32 行**仅含基础命令，`AGENTS.md` 引用的前端约定（一次拉全量 + 5000 page_size + PageSectionCard + 32px 筛选控件高度）在代码中实际落地，组件命名一致 camelCase + kebab 文件，目录边界清晰 `views / components / api / stores / utils / styles / config / router`，Element Plus 统一在 `element-overrides.scss` 集中定制 shadcn Zinc 风格），未满足 3 级（**无 ADR**（后端 M4 已有 ADR-2，前端零 ADR），**无前端 runbook**（没有"前端挂了怎么排查"章节），**README 过于简陋**未文档化数据加载模式/组件清单/迁移指南，`ZipcodeRuleView.vue` 1276 行违反"模块边界清晰"，无"如何写一个新数据页"how-to）

**关键证据**：
- `frontend/README.md:1-32` — 全部内容 32 行，仅 install/dev/lint/build 命令清单
- `frontend/src/styles/element-overrides.scss:1-13` — 严格文档化 shadcn 对齐规范作为注释
- `frontend/src/components/PageSectionCard.vue:50-55` — `--el-component-size: 32px` 集中控制筛选高度，配合 AGENTS.md 约定
- `frontend/vite.config.ts:20` — SCSS 全局注入 `@use "@/styles/tokens.scss" as *;`
- `frontend/src/config/navigation.ts:1-40` — 导航结构化定义（NavItem/NavSubCategory/NavGroup 三层清晰）
- `frontend/src/router/index.ts:130-149` — **10+ 个 legacy redirect 活化石**未文档化迁移上下文，维护性差
- Grep `PageSectionCard in views/` → 10 个文件使用（使用面广但无文档说明何时用何时不用）
- `docs/deployment.md` / `docs/runbook.md` 后端覆盖，前端零前端章节
- `ZipcodeRuleView.vue` 1276 行 + `SuggestionDetailView.vue` 729 行 未拆子组件

**差距**：
- 🟡 P1-M5-5：README 过于简陋，未文档化前端约定、数据页模板、组件 API
- 🟡 P1-M5-6：无前端 ADR（例："为什么用 localStorage 存 token"、"为什么不用 Element Plus 按需引入"、"为什么一次拉 5000 条而非虚拟滚动"）
- 🟢 P2-M5-7：10+ legacy redirect 无文档说明何时可清理

**对照 M1=3 / M2=3 / M3=3 / M4=3**：**M5 为 2 分，低于后端所有模块 1 级**。理由：后端模块普遍有 `Project_Architecture_Blueprint.md` 深度文档 + runbook 章节 + ADR（M4），而前端 README 极简 + 零 ADR + 零 runbook 前端章节。Rubric 3 级要求"ADR + runbook + 注释覆盖"——M5 明确未达。

---

## D8 性能与容量 ⚠️ 主战场 — 3

**判据匹配**：满足 Rubric 3 级（**Vendor 精准分包**三桶 element-plus/charts/framework + 所有 view 自动 route code-split 每文件 2-16 KB + gzip 首屏 **~358 KB gz**（index+framework+element-plus+client）远优于"首屏 < 3s" 标准，charts 懒加载仅 3 个图表页拉取 188 KB gz、数据页不加载，`vite.config.ts:36` 生产 **sourcemap=false** 防暴露，nginx gzip + /assets immutable 强缓存 + SPA fallback 完整，`frontend` docker 资源限制 `memory: 256m`，table 5000 条本地分页在 Element Plus el-table 虚拟化支持下可接受 + `pagedRows = slice(start, start+pageSize)` computed 避免全量渲染），未满足 4 级（**element-plus 全量引入 906 KB / 293 KB gz** 未做按需 `unplugin-vue-components`/`unplugin-element-plus` 是最大 P1 优化空间，**无 Lighthouse / Web Vitals 自动化基准**，无 CDN 接入，无图片懒加载 `<img loading="lazy">` + 无 `<picture>` responsive，无 Service Worker / HTTP/2 push；vite build 有 chunk-size warning 两处未明确处置；一次拉 5000 条数据是内存占用上界但单用户场景可接受）

**关键证据**：
- vite build 实测产物（exit 0 + 上方表格）：
  - 首屏 gzip 约 **358 KB**（index 3.66 + framework 46.27 + element-plus 293.61 + client 15.06）
  - charts 懒加载 **188.66 KB gz**（仅 ApiMonitor/PerformanceMonitor/Workspace 触发）
  - 所有页面 chunk 最大 16.62 KB（ZipcodeRuleView），多数 < 5 KB
  - 构建 **11.14 s**
- `frontend/vite.config.ts:40-55` — 三桶 manualChunks + 框架/图表/组件分离
- `frontend/vite.config.ts:36-37` — `sourcemap: false`, `chunkSizeWarningLimit: 500`
- `frontend/nginx.conf:8-20` — gzip + `/assets/` `expires 1y; Cache-Control: public, immutable`
- `frontend/src/views/SuggestionListView.vue:239-242` — `pagedItems = sortedItems.slice(start, start+pageSize)` computed 分页避免渲染全量 5000 条
- `frontend/src/api/data.ts:60,98,130,198,232` — 6 接口 page_size 5000 一次拉全量（单用户场景可接受）
- `deploy/docker-compose.yml:134-137` — frontend `memory: 256m` 资源限制
- `frontend/package.json:18-28` — element-plus 全量 import `import 'element-plus/dist/index.css'` 在 main.ts:6

**差距**：
- 🟡 P1-M5-8：element-plus 906 KB（gzip 294 KB）未按需引入是最大 vendor 包。按需可降至 ~150 KB gz 级别。
- 🟢 P2-M5-9：无 Lighthouse CI / Web Vitals 采集基准
- 🟢 P2-M5-10：`chunkSizeWarningLimit: 500` 仍 warn 未显式处理

**对照 M1=2 / M2=2 / M3=2 / M4=2**：**M5 为 3 分，高于后端模块 1 级**。理由：M5 的 D8 实测证据非常强——vendor 分包 + 懒加载 + sourcemap off + 资源限制 + 首屏 358 KB gz + 图表懒加载 188 KB gz 全链路实测通过，符合 Rubric 3 "vendor 分包 + 资源限制 + 容量评估"。后端模块因无 SLO/慢查询日志停留在 2。**M5 D8 得分是全项目最高**。

---

## D9 用户体验 ⚠️ 主战场（M5 核心维度 / 标尺源头） — 3

**判据匹配**：满足 Rubric 3 级（
1. **统一组件容器**：`PageSectionCard` 在 10 个 views 一致使用 `#title` + `#actions` slot，自带 `--el-component-size: 32px` 筛选高度约束
2. **全中文界面**：`main.ts:7,17` 接入 `element-plus/es/locale/lang/zh-cn`，所有 label/placeholder/status/error 全部中文，Grep 未发现英文硬编码（`Loading/Error/Submit` 57 处全部是代码标识符而非 UI 文案，登录页仅「Sign in to Restock」一处英文作为品牌 tagline）
3. **设计系统对齐 shadcn Zinc**：`styles/element-overrides.scss:1-13` 显式注释 shadcn 对齐规范 + `:root` 32 行 CSS 变量覆盖 Element Plus 全套 token（primary = zinc-900 + light-3/5/7/8/9 分级），`styles/tokens.scss` 集中设计 token，`vite.config.ts:20` SCSS 全局注入
4. **加载/错误/空态反馈**：`v-loading` + `el-empty` + `el-alert` 共 30 处跨 13 个 view 覆盖，每个数据页都有空态文案（如"尚未拉取订单详情"、"暂无仓库数据"）
5. **错误提示具体可操作**：`getActionErrorMessage` 五档处理能把 loc+msg 格式化成「字段名：错误信息」（apiError.ts:19-26），network-down 提示"后端服务不可用，请确认后端已启动"具体指向排查点
6. **跨页选择体验**：`SuggestionListView.vue:260-305` `handleSelectAll` 跨所有页签全选 + `syncTableSelection` 分页切换时回写 checkbox 状态 + 筛选/sort 变化自动清除防脏选 + `suppressSelectionSync` 时序防御
7. **筛选控件高度统一 32px**：`PageSectionCard.vue:52-55` + `SuggestionListView.vue:388-393` + `element-overrides.scss` 多层 `--el-component-size: 32px` 约束，Grep 18 处
8. **动画与 tooltip**：`el-tooltip` 在表格列名/长文本广泛使用（`SuggestionListView.vue:59-71,77-87`），`AppLayout` 侧栏 `transition: width 300ms ease`，登录页交互网格 300/500ms 余温动画
9. **状态变化反馈**：建议单 urgent 行标红 `:row-class-name="rowClass"` + `row-urgent` 主题色；登录失败 `error-banner` + pulse 动画；任务进度 indeterminate progress bar + 状态 tag 实时切换；ElMessage.success/warning/error 三档
10. **移动端响应式**：`AppLayout.vue:549-563` + `PageSectionCard.vue:58-63` + `SuggestionListView.vue:416-420` 多处 `@media (max-width: 900px)` / `1100px` / `1280px` 断点，侧栏可收起 64px；但**非真正移动优先**——桌面侧栏即使收起仍占 64px 宽，触摸目标尺寸未专门优化，el-table 横向超宽在手机上仍需横向滚动
11. **登录页 IP 锁定反馈**：`LoginView.vue:87-91` 对 423 锁定状态专门中文提示

），未满足 4 级（
- **a11y 严重不足**：Grep `aria-|role=` 仅 5 文件命中且多为 Element Plus 自带非应用层，无 `aria-label`/`aria-describedby`/`aria-live` 主动标注，无 skip-link，无明显对比度合规测试，无键盘导航焦点管理（table 行/侧栏折叠等自定义交互无 `tabindex`/`Enter` 处理）
- **无键盘快捷键**：除表单 `@keyup.enter` 外无全局 `Ctrl+K` 搜索 / `Esc` 关闭 dialog 自定义绑定
- **无 i18n 基础设施**：全中文硬编码，未接入 vue-i18n，未来加英文需大规模改写
- **无用户行为分析 / A/B**：零埋点
- **移动端降级而非原生**：无 viewport meta tag 特殊处理（未检查），数据表格仍走桌面布局
- 部分细节瑕疵：`DataOrdersView.vue:205` 吞错误为「加载失败」；WorkspaceView 首屏加载失败静默；登录页 card title 是英文「Sign in to Restock」与全中文 UX 轻微冲突
）

**关键证据**（按维度列举）：
- 统一容器：`frontend/src/components/PageSectionCard.vue:1-64` + 10 views 使用
- 中文化：`frontend/src/main.ts:7,17` + `frontend/src/utils/status.ts:13-26` 全枚举 → 中文
- Zinc 对齐：`frontend/src/styles/element-overrides.scss:1-80` 显式 shadcn 注释 + primary zinc-900 + 分级 light-3/5/7/8/9
- 加载/空态：30 处 `el-empty/v-loading/el-alert` 分布 13 view
- 跨页选择：`frontend/src/views/SuggestionListView.vue:264-305` 四函数协同
- 32px：`frontend/src/components/PageSectionCard.vue:51-55` + 多 view `.toolbar-filters :deep` 覆盖
- 响应式：`frontend/src/components/AppLayout.vue:549-563` + `PageSectionCard.vue:58-63`
- 状态反馈：`SuggestionListView.vue:256-258,402-413` urgent 行标红 + hover 变色
- a11y 负面证据：Grep `aria-|role=` → 5 文件但大多 Element Plus 内置，无应用层主动标注
- i18n 负面证据：Grep `vue-i18n` → 0 matches；`main.ts:17` 只接入了 Element Plus zhCn 单语言包

**差距**（P0/P1/P2）：
- 🟡 P1-M5-9：无 a11y（aria 标签、键盘导航、跳转链接、焦点管理）——公网上云若涉及合规则是 blocker
- 🟡 P1-M5-10：无 i18n 框架，将来加英文需重做——战略决策需明确
- 🟢 P2-M5-11：移动端非原生优化，表格横向滚动体验一般
- 🟢 P2-M5-12：LoginView 「Sign in to Restock」英文与中文 UX 风格轻微冲突
- 🟢 P2-M5-13：WorkspaceView 加载失败静默（也是 D5 问题）

**对照 M1=N/A / M2=N/A / M3=2 / M4=N/A**：**M5 为 3 分，高于 M3 一级**。

### 对 D9 标尺的校准意见

M3 先前给 D9=2 的证据（后端 push_error 字段持久化 + PushBlockedError 结构化 detail）是**非常有限的单点"错误信息本地化"**，而 M5 的 D9 覆盖**设计系统 + 国际化基础 + 完整交互体验 + 组件复用 + 响应式 + 状态反馈 + 跨页交互**全链路——两者不在同一尺度。

**建议**：
- **不 retroactive 调整 M3=2**。M3 的 2 分反映的是"后端错误返回层面"的 UX，只能算 UX 的一个狭窄侧面。保留 M3=2 作为"后端模块默认 UX 上限" benchmark 有意义。
- **M5=3 作为 D9 真正的标尺基准**。M5 的完整 UX 已经满足 Rubric 3 级所有硬指标（统一容器 ✓ + 中文 ✓ + 加载错误反馈 ✓ + 设计系统 shadcn Zinc 对齐 ✓ + 状态反馈 ✓ + 错误提示具体可操作 ✓ + 跨页选择体验良好 ✓ + 移动端基本可用 ✓），未满足 4 级的核心原因是 a11y / 键盘快捷键 / i18n / 用户行为分析全部缺失，这是明确的一级差距。
- **后续 M6 如果涉及面向用户的界面（如系统管理/admin），D9 应参照 M5=3 标尺；后端模块默认 D9 = N/A 或参照 M3=2。**

---

## 模块平均分

| 维度 | 分数 |
|---|:---:|
| D1 功能完整性 | 3 |
| D2 代码质量 | 3 |
| D3 安全性 | 2 |
| D4 可部署性 | 3 |
| D5 可观测性 ◦ | 2 |
| D6 可靠性 | 3 |
| D7 可维护性 | 2 |
| D8 性能与容量 ⚠️ | 3 |
| D9 用户体验 ⚠️ | 3 |

**模块平均分 = (3+3+2+3+2+3+2+3+3) / 9 = 24 / 9 ≈ 2.67 / 4**

**主战场表现**：D9=3（最高）、D1=3、D8=3（全项目最高）

---

## 与 M1/M2/M3/M4 共性问题

- 无 CI/CD / 蓝绿部署 / 多环境（D4 共性）
- 无 OpenTelemetry / Grafana / 告警 / SLO/SLI（D5 共性）
- 无 chaos test / 故障注入（D6 共性）
- 无熔断器 / 死信队列（D6 共性）
- 无 npm audit CI 扫描（D3 共性对应 M1-M4 的 pip-audit 缺口）

## M5 独有问题

- 🟡 **token 存 localStorage**（D3，公网 XSS 风险）
- 🟡 **nginx.conf 缺安全 headers**（D3，CSP / X-Frame-Options / Referrer-Policy 全缺）
- 🟡 **element-plus 全量引入 906 KB**（D8，未按需大幅增加 vendor 体积）
- 🟡 **views 零组件测试**（D2，仅 TaskProgress 2 个，其余 5000+ 行业务代码无组件测试）
- 🟡 **ZipcodeRuleView 1276 行 + SuggestionDetailView 729 行**（D2，巨型文件）
- 🟡 **`getActionErrorMessage` 仅 15 处使用**（D5，大量 catch 块吞异常硬编码「加载失败」）
- 🟡 **TaskProgress 轮询失败立即 stop 无重试**（D6，断网即丢终态）
- 🟡 **WorkspaceView 首屏失败静默**（D5，无 ElMessage 提示）
- 🟡 **README 极简 32 行 + 零 ADR + 零前端 runbook 章节**（D7）
- 🟡 **a11y 基本缺失 + 无 i18n 基础设施**（D9，未达 Rubric 4 级）
- 🟢 10+ legacy redirect 无清理说明（D7）

## M5 独有亮点

- 🟢 **vue-tsc 0 错误 + eslint --max-warnings 0 exit 0 + vitest 33 pass**（D2，全项目唯一三个质量门户全绿的模块）
- 🟢 **vendor 精准分包 + 懒加载 + sourcemap 关 + 首屏 358 KB gz**（D8，**全项目 D8 最高分**）
- 🟢 **统一 PageSectionCard + 32px 筛选高度 + shadcn Zinc 设计系统对齐**（D9，UX 一致性标尺）
- 🟢 **跨页选择 + 筛选 sort 自动清理 + 401/404/423 特殊分支处理**（D6）
- 🟢 **零 `v-html` / 零 `console.log` / 零 `innerHTML`**（D3，XSS 注入面清洁）
- 🟢 **`getActionErrorMessage` 五档错误分类**（D6，比大多数前端项目的 catch-all 更细）

---

## P0/P1/P2 候选汇总（M5 独有，供 spec 回填）

（第二轮 review 后更新：a11y/i18n 降级到 P2；新增 ADR + ZipcodeRule 拆分 P2；token localStorage 决策加注）

- 🔴 P0：**0 项**（M5 无 P0 阻塞上云问题）
- 🟡 P1（**原 8 项 → 6 项**）：
  1. **P1-M5-1：token 存 localStorage**（D3，公网 XSS） ｜ 用户已 ack 接受单用户场景风险，新增 P2-M5-14 写 ADR 明确此决策
  2. **P1-M5-2：nginx 缺安全 headers**（D3，HSTS / X-Frame-Options / CSP / Referrer-Policy 全缺）
  3. **P1-M5-3：`getActionErrorMessage` 未普及**（D5，39 处 ElMessage.error 仅 15 处走统一错误处理）
  4. **P1-M5-4：TaskProgress 轮询失败无重试**（D6，断网即停）
  5. **P1-M5-5：README 简陋（32 行）+ 无 ADR**（D7）
  6. **P1-M5-8：element-plus 全量引入**（D8） ｜ 用户已立项按需引入（收益 ~150 KB gz），待实施
- 🟢 P2（**原 5 项 → 9 项**）：
  1. P2-M5-7：legacy redirect 清理说明
  2. P2-M5-9：无 Lighthouse CI
  3. P2-M5-11：移动端非原生优化
  4. P2-M5-12：LoginView 英文 tagline 与中文 UX 冲突
  5. P2-M5-13：WorkspaceView 首屏失败静默
  6. **P2-M5-14**（新增）：写 ADR 记录"token localStorage 在 1-5 人单用户场景下风险可接受"的决策（对应 #1 用户澄清）
  7. **P2-M5-15**（新增，由 D1/D2 差距升级）：拆分 `ZipcodeRuleView.vue` 1276 行巨型 view，按规则列表 / 规则编辑 / 规则预览三个子组件拆分；同时考虑拆分 `SuggestionDetailView.vue` 729 行
  8. **P2-M5-16**（新增，原 P1-M5-9 降级）：**a11y 缺失**——未来若扩展用户群（残障员工 / 对外政企客户）时重新评估。当前 1-5 人内部工具 ROI 倒挂，YAGNI 延后。不影响 D9=3 评分（a11y 是 Rubric 4 级门槛）
  9. **P2-M5-17**（新增，原 P1-M5-10 降级）：**i18n 缺失**——未来若国际化时重新评估。当前中文团队场景零 ROI，YAGNI 延后。不影响 D9=3 评分

---

## 给用户的待确认疑点

✅ 全部 5 个疑点在第二轮 review 中已由用户给出决策，详见 §8 用户澄清记录。

---

## 8. 用户澄清记录（2026-04-11 第二轮 review）

### #1 token 存储策略
- **疑问**：是否升级 HttpOnly cookie？
- **用户回答**：**接受 localStorage 现状**
- **影响**：
  - D3=2 不变；P1-M5-1 保留为 P1（单用户场景风险可接受但仍是公网视角缺口）
  - **新增 P2-M5-14**：写 ADR 明确"单用户 1-5 人场景下 token localStorage 风险可接受"的决策，为未来扩展到多用户场景留追溯依据

### #2 element-plus 按需引入
- **疑问**：是否立项按需引入？收益 ~150 KB gz
- **用户回答**：**接受，立项**
- **影响**：P1-M5-8 保留为 P1 并标记"已立项"，实施时机待定（打分完成后作为独立 fix PR）

### #3 a11y / i18n 路线图（Claude 主控推荐 + 用户采纳）
- **疑问**：是否列入路线图？
- **Claude 推荐**：**两者都不列入路线图，降级到 P2**
- **推荐理由**：
  - **a11y**：1-5 人内部团队无残障员工、无 WCAG/Section 508 合规需求、全 10+ views 加 aria 标签 + 焦点管理 + 键盘导航预估 1-2 周工作量，对当前用户群零业务价值，YAGNI 原则
  - **i18n**：内部中文团队零国际化需求，Vue 3 + Vue I18n 生态成熟（未来真要做不迟），当前纯技术债
  - 不阻塞交付，不影响 D9=3 评分（两者都是 Rubric 4 级"优秀"门槛，M5 已是"良好"）
- **用户决策**：**采纳推荐**
- **影响**：
  - 从 P1 列表移除 a11y / i18n 两项
  - 新增 P2-M5-16 (a11y) / P2-M5-17 (i18n)，描述为"未来若扩展用户群/国际化时重新评估"
  - M5 P1 列表从 8 项减到 6 项
  - D9 评分不变（3 分）

### #4 D9 标尺正式化（Claude 主控推荐 + 用户采纳）
- **疑问**：M5 D9=3 是否作为后续模块基准？M3=2 是否 retroactive 调整？
- **Claude 推荐**：**采纳 subagent 的三层标尺方案**
- **三层标尺正式化**：

  | 层 | 模块类型 | 标尺 | 分数范围 | 当前匹配模块 |
  |---|---|---|---|:--:|
  | **L1 面向用户 UI 模块** | 完整前端体验 | 参照 **M5=3** | 2-4 | M5、**M6** 含登录页/配置页 |
  | **L2 后端 + 部分 UX 暴露** | 通过错误字段/API 响应间接影响 UX | 参照 **M3=2** | 1-3 | M3 |
  | **L3 纯基础设施** | 无 UI 相关代码 | **N/A** | — | M1、M2、M4、M7、M8 |

- **推荐理由**：
  1. M5 是真正的"面向用户界面"模块，是 UX 标尺源头
  2. M3 的 2 分是在"仅 push_error 字符串展示"狭窄证据下评的，保留作为 L2 后端默认基准
  3. 不 retroactive 调整 M3 — M3 已封板，改动历史 commit 不合算
  4. M6 必须按 L1 评（含 LoginView / GlobalConfigView / PerformanceMonitorView 等面向用户的页面）
  5. M7/M8 纯基础设施，按 L3 N/A
- **用户决策**：**采纳推荐**
- **影响**：
  - spec 设计文档 §3 需同步更新 M6 D9 标尺说明
  - `_calibration.md` D9 小节顶部需加"三层标尺"说明
  - M5 D9=3 / M3 D9=2 均不 retroactive 调整

### #5 views 零组件测试（Claude 主控推荐 + 用户采纳）
- **疑问**：是否接受现状？
- **Claude 推荐**：**接受现状，不升级为 P1**
- **推荐理由**：
  1. 已有测试覆盖核心业务逻辑：utils（tableSort / format / apiError / element / monitoring / allocation）+ stores（auth / task）+ api client + route guard + TaskProgress —— **共 33 tests / 8 files**
  2. views 组件测试能发现的 bug（UI 交互、筛选 + 分页 + 跨页选择组合）**人工点击完全能发现**——1-5 用户会实际使用，UI bug 第一时间反馈
  3. 对比 M4 零单测的严重性：M4 是并发语义（SKIP LOCKED / lease / heartbeat）**人工无法验证** → 必须单测；M5 views 交互 **人工可验证** → 单测 ROI 倒挂
  4. 每个 view 的组件测试约 100-200 LOC，10+ views ≈ 2000+ LOC 测试代码 + 维护成本随 UI 变化
  5. `vue-tsc + eslint + vitest` 三质量门全绿本身就是重要守护
- **用户决策**：**采纳推荐**
- **影响**：
  - views 零组件测试保持为 D1/D2 的"未达 4 级差距"描述
  - 不升级为 P1/P2
  - M5 D1=3 / D2=3 维持不变
  - ZipcodeRuleView 1276 行巨型文件作为独立 P2-M5-15 保留（这是代码组织问题，与测试覆盖是两回事）

---

## 9. 第二轮变更摘要

**无代码改动**（本轮所有决策都是评分调整）。文档层变更：

| 位置 | 变更 |
|---|---|
| §4/§5/P1P2 列表 | a11y / i18n 从 P1 降级到 P2；新增 P2-M5-14 (ADR) / P2-M5-15 (拆分 ZipcodeRule) / P2-M5-16 (a11y 重评) / P2-M5-17 (i18n 重评) |
| §8 | 新增用户澄清记录（5 条） |
| `_calibration.md` D9 小节 | 待加"三层标尺"说明（下一步同步更新）|
| spec §3 设计文档 | M6 D9 应按 L1 评（下一步同步更新）|

**M5 评分无变化**：D1=3 D2=3 D3=2 D4=3 D5=2 D6=3 D7=2 D8=3 D9=3 → **平均 2.67**

**P1 / P2 列表演变**：
- P1：8 项 → **6 项**（a11y + i18n 降级）
- P2：5 项 → **9 项**（+ ADR + ZipcodeRule 拆分 + a11y 重评 + i18n 重评）
