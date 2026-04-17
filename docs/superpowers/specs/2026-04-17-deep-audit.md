# Restock System 深度审查报告（交互 / 分页 / 链路 / 部署）

> 审查日期：2026-04-17（二次深审）
> 审查范围：前后端交互契约 · 前端性能（分页） · 后端接口（分页） · 端到端功能链路 · 部署链路
> 方法：5 个 Explore subagent 独立取证 + 主对话汇总

---

## 0. 总览

| 审查面 | 分数 | 关键结论 |
|---|---|---|
| **前后端交互契约** | 3.5 / 5 | 契约大体一致；**无 CORS 配置**、**无 token 刷新**、类型声明松散 |
| **前端性能（分页）** | 3.6 / 5 | 订单页服务端分页完整；**SuggestionListView 全量加载是最大风险**；SkuCard 无 lazy |
| **后端接口（分页）** | 3.5 / 5 | 分页规范不统一（`page_size` 上限 100/200/500/1000/5000 混用）；**sort_by 无白名单**（注入风险） |
| **端到端功能链路** | 3.5 / 5 | 链路可执行；**推送后 PO 号与 in_transit 映射缺失**（重复推送风险） |
| **部署链路** | 4.0 / 5 | CI/CD 门控完整；**IMAGE_TAG 无默认值**、**APP_BASE_URL 声明缺失**、smoke_check 太浅 |

**综合再审结论**：系统可投产，但存在 **3 个新发现的 P0 级缺陷**（见 §7）未被原 backlog 覆盖。原 backlog 仍然有效，本报告作为补充。

---

## 1. 前后端交互契约

### 1.1 关键发现

**⚠️ `backend/app/main.py` 无 CORSMiddleware**
- 前端 `axios baseURL = '/'` 依赖同源部署（Caddy 代理）
- 若未来前后端分离部署，跨域请求会被浏览器拦截
- **建议**：添加 `CORSMiddleware(allow_origins=[...], allow_credentials=True)`，从 env 读取白名单

**⚠️ 无 JWT 刷新机制**
- `backend/app/api/auth.py` 仅签发 24h JWT，无 refresh token 端点
- 前端 `restoreAuth()` 仅调用 `/api/auth/me` 验证，过期即被 401 拦截跳登录
- **影响**：长时间操作中途被踢出
- **建议**：引入 refresh token 或滑动续期

**⚠️ 前端 `LoginResponse.user: Record<string, unknown>` 类型松散**
- 位置：`frontend/src/api/auth.ts:4-8`
- 后端 Pydantic 为 `UserInfoResponse` 强类型
- 下游 `_mapUserInfo()` 手工适配，违反 DRY
- **建议**：`interface UserInfo` 精确对齐后端字段

**⚠️ 422 降级处理无日志**
- `frontend/src/utils/apiError.ts` 已处理 Pydantic 422 的 `detail` 数组
- 但格式异常时静默降级到通用消息
- **建议**：降级路径加 `console.warn` 便于排障

### 1.2 正面设计

- ✅ 401 拦截器（`client.ts:24-39`）清 auth + 跳登录 + 保留 redirect
- ✅ 403 拦截器先 `restoreAuth()` 再提示权限不足
- ✅ 权限码前后端一致（`RESTOCK_VIEW` / `SYNC_OPERATE` 等）
- ✅ 异常响应统一 `{message, detail}` 或 `{detail}`
- ✅ 端点命名一致（均为 `/api/<resource-plural>`）
- ✅ 后端全 ORM，0 raw SQL

---

## 2. 前端性能（分页 · 重点）

### 2.1 所有页面分页策略矩阵

| 页面 | 数据量级 | 分页模式 | 瓶颈 | 风险 |
|---|---|---|---|---|
| **DataOrdersView** | 数万+ | 服务端（50/100/200） | 无查询缓存 | 低 ✅ |
| **DataInventoryView** | 仓库分组 | 服务端（20） | 嵌套表展开 | 低 |
| **DataProductsView** | 数千 SKU | 服务端（50/100/200） | **图片无 lazy** | 中 ⚠️ |
| **DataShopsView** | < 100 | 本地 | — | 低 |
| **DataWarehousesView** | < 50 | 本地 | — | 低 |
| **DataOutRecordsView** | 中 | 服务端（50/100） | 嵌套表无分页 | 低 |
| **SuggestionListView**（补货发起） | **动态可变** | **本地（20）** | `filteredItems + sortedItems` 每次全量重算 | **高 ❌** |
| **HistoryView** | 中 | 服务端（20） | — | 低 |

### 2.2 关键风险：补货发起页

`SuggestionListView.vue` 是当前**最薄弱**的性能点：
- `suggestion.value.items` 全量存内存
- 两个 computed（`filteredItems` → `sortedItems`）每次筛选都全量重算
- 若某次引擎生成超过 5000 条建议 → 筛选/排序卡顿 + 可能 OOM

**建议**：
1. 监控 `suggestion.items.length` 分布（加埋点）
2. 若常规 > 3000 条，切换为服务端分页 + 筛选
3. 或启用 `el-table-v2`（虚拟化）

### 2.3 构建与加载

**Bundle 体积**（`frontend/dist/assets/`）：
- `element-plus-*.js` **886 KB** — 已启 auto-import + `importStyle: false`，固有瓶颈
- `charts-*.js` 545 KB — ECharts
- `framework-*.js` 123 KB — Vue + Router + Pinia

**✅ 做得好**：
- 路由 lazy import 覆盖率 100%（17 个页面）
- vite `manualChunks` 已分 charts / element-plus / framework

**⚠️ 改进**：
- `SkuCard.vue` 裸 `<img>`，无 `loading="lazy"` → 商品页/订单页图片全部加载
- 图表库可按页懒加载（`PerformanceMonitorView` 专用）

### 2.4 列表渲染

- ✅ 订单页有 `listReqId` / `detailReqId` 防过期响应覆盖
- ✅ SKU 输入 300ms 防抖
- ⚠️ 无查询缓存（筛选切换后再切回需重新请求）

---

## 3. 后端接口（分页 · 重点）

### 3.1 18 个列表端点分页矩阵

| 端点 | page_size 上限 | sort 白名单 | filter 数 | count 方式 |
|---|---|---|---|---|
| `GET /api/data/orders` | 5000 | ⚠️ 无白名单 | 6 | subquery |
| `GET /api/data/inventory` | 5000 | ⚠️ 无白名单 | 4 | subquery |
| `GET /api/data/inventory/warehouse-groups` | **200** | — | 3 | subquery |
| `GET /api/data/out-records` | 5000 | ⚠️ 无白名单 | 5 | subquery |
| `GET /api/data/warehouses` | 1000 | — | 0 | COUNT(*) |
| `GET /api/data/shops` | 1000 | — | 0 | COUNT(*) |
| `GET /api/data/product-listings` | 5000 | — | 5 | subquery |
| `GET /api/data/sku-overview` | 5000 | — | 2 | subquery |
| `GET /api/suggestions` | 5000 | ⚠️ 无白名单 | 4 | **with_only_columns（非标准）** |
| `GET /api/config/sku` | **200** | — | 2 | subquery |
| `GET /api/tasks` | **100** | — | 2 | subquery |
| `GET /api/monitor/api-calls` | — | — | 1 | GROUP BY |
| `GET /api/monitor/api-calls/recent` | **500** | — | 2 | limit only |
| `GET /api/config/warehouse` | **无分页** ❌ | — | 0 | — |
| `GET /api/config/zipcode-rules` | **无分页** ❌ | — | 1 | — |
| `GET /api/config/shops` | 无分页 | — | 0 | — |
| `GET /api/metrics/dashboard` | N/A（单对象） | — | 0 | — |

### 3.2 主要问题

**⚠️ `page_size` 上限混乱**
- 100（tasks）/ 200（warehouse-groups, sku）/ 500（api-calls recent）/ 1000（warehouses, shops）/ 5000（其他）
- **建议**：按数据域分层约定：小数据（< 500 行/表）统一 1000，大数据（订单/库存/建议）统一 5000

**❌ `sort_by` 无白名单校验（潜在风险）**
- 前端传任意字段名可能导致 ORM 按未预期字段排序，或配合 CASE 表达式造成拒绝服务
- **建议**：每个端点定义 `SORTABLE_FIELDS: set[str]` 白名单，不在集合内 `raise ValidationError`

**⚠️ `GET /api/config/warehouse` 和 `/zipcode-rules` 无分页**
- 当前数据量小可接受，但未来邮编规则可能膨胀（每国 20 段规则 × 多国）
- **建议**：预留 `page/page_size` 参数，默认返回全量

**⚠️ `GET /api/suggestions` 用 `with_only_columns` 代替 COUNT**
- 位置：`backend/app/api/suggestion.py:117`
- 非标准写法，某些 SQLAlchemy 优化可能失效
- **建议**：改 `select(func.count()).select_from(...)` 标准模式

**⚠️ `SuggestionListOut` / `SkuConfigListOut` 响应缺 `page` / `page_size` 字段**
- 位置：`backend/app/schemas/suggestion.py:57-61`、`schemas/config.py:83-85`
- 前端分页回显需要这些字段
- **建议**：补字段对齐其他端点

### 3.3 正面设计

- ✅ 全文本筛选用 `escape_like()` 防注入
- ✅ 订单复合键查询用 `tuple_(shop_id, amazon_order_id).in_()` 避免 N+1
- ✅ 补充数据（`item_count`、`has_detail`）按当前页批量 IN 查询
- ✅ HTTP 状态码规范：201（POST）/ 204（DELETE）/ 404 / 409 / 422
- ✅ 事务边界清晰

---

## 4. 端到端功能链路

### 4.1 5 步链路验证

| 步骤 | 状态 | 备注 |
|---|---|---|
| 1. 赛狐同步 | ✅ | 7 个 sync job 齐全，限流 + 失败分类完备 |
| 2. 数据规范化 | ⚠️ | **SKU 启用条件仅查 `enabled`，未校验 `is_matched && online_status=active`** |
| 3. 引擎 6 步 | ⚠️ | 无仓库国家走 `unknown_order_qty` 路径可能静默失败 |
| 4. 建议单管理 | ✅ | CRUD 完整，状态流转、编辑、删除都就位 |
| 5. 推送采购单 | ⚠️ | **PO 号回写后未与 `in_transit_record` 关联**（重复推送风险） |

### 4.2 三个关键缺口

**❌ [步骤 3 → 5 交接] 推送后的 PO 号与在途库存映射缺失**
- 现象：`suggestion_item.saihu_po_number` 回写后，下次引擎依赖 `load_in_transit` 从**已推送且未归档**的建议条目汇总
- 风险窗口：赛狐新采购单需要数小时才同步回 `in_transit_record`，若期间用户再次触发引擎：
  - 已推送建议单的 `country_breakdown` 仍在用（正确）
  - 但若用户手工归档了这批建议单（或 2026-04-11 后的清理逻辑提前归档），在途 SKU 会漏算
- **建议**：审查 `_archive_active()` 的时机，确认归档策略是"生成新建议前归档旧 draft"而非"推送完成后归档"

**⚠️ [步骤 2] SKU 启用条件漏查在线状态**
- 位置：`backend/app/engine/runner.py:80-88`
- 现象：只检查 `SkuConfig.enabled=true`，但不联合查 `ProductListing.is_matched && online_status='active'`
- 影响：下架但配置未禁用的 SKU 会进入计算
- **建议**：引擎入口加 join 过滤，或同步层 `_backfill_sku_configs_from_synced_listings` 自动维护

**⚠️ [步骤 3] 无仓库国家静默降级**
- 现象：`load_country_warehouses` 返回空列表时，`explain_country_qty_split` 走 `unknown_order_qty`
- 影响：国家无仓库时分配可能失败且无告警
- **建议**：空仓库列表时写入 `suggestion.notes` 告警，或拒绝为该国生成补货量

### 4.3 新用户 Onboarding Flow

```
1. alembic upgrade head
2. 配置 backend/.env（SAIHU_* / JWT_SECRET / LOGIN_PASSWORD）
3. 初次启动 → LOGIN_PASSWORD 自动 hash 入库
4. 登录 → 设置 GlobalConfig（target_days / lead_time_days / restock_regions / default_purchase_warehouse_id）
5. 数据同步页 → "同步全部" → 等待 7 个 sync job 完成（约 10-30 分钟）
6. ⚠️ 验证：Warehouse 表 country 字段已正确（关联 inventory_snapshot_latest 级联）
7. ⚠️ 配置：ZipcodeRule 按国家补齐（影响 Step5 分仓准确性）
8. 补货发起页 → "生成建议" → 等待引擎完成
9. 审阅建议单 → 勾选 → 推送
10. ⚠️ 监控：推送后 PO 号是否在数小时内关联 in_transit_record
```

---

## 5. 部署链路

### 5.1 整体流程

```
Code Push → CI [test + lint + build + audit + docker-build]
    ↓ (CI 全绿)
Tag/Manual Trigger → deploy.yml (CI 门控)
    ↓ SSH to prod
validate_env.sh → pg_backup.sh → docker compose pull
    ↓
migrate.sh (文件锁) → rolling update (backend → worker → scheduler → frontend → caddy)
    ↓
smoke_check.sh → 成功 or 自动 rollback.sh
```

### 5.2 发现的断点

| 位置 | 问题 | 影响 | 建议 |
|---|---|---|---|
| `deploy/docker-compose.yml:86` | `IMAGE_TAG` 无默认值 | 手动部署易忘注入 → 拉取失败 | 默认 `${IMAGE_TAG:-latest}` |
| `deploy/docker-compose.dev.yml:14` | `APP_BASE_URL` 使用但未在 `.env.example` 声明 | 开发环境来源信息丢失 | 补到 `.env.example` |
| `deploy/scripts/smoke_check.sh` | 仅验证 `/healthz` `/readyz` | 业务端点故障不可见 | 加 `curl /api/auth/login`（期望 400/422）+ `/api/metrics/dashboard`（期望 401） |
| `deploy/scripts/migrate.sh` | `/tmp/restock_migrate.lock` 容器外路径 | 文件锁跨容器无效 | 改用 `pg_try_advisory_lock(migration_key)` |
| `.github/workflows/deploy.yml:41-42` | `check-ci` 通过 job name 字符串匹配 | CI 改名导致部署被意外跳过 | 改 `workflow_run` 触发 |
| `deploy/scripts/deploy.sh:13` | `PREV_SHA` 脚本开头抓取，后续代码变更不再更新 | 回滚 SHA 可能不准确 | 统一在进入关键段前快照 |
| `deploy/scripts/pg_backup.sh:36` | `stat -c%s` 非跨平台 | macOS 本地备份失败 | 加平台探测 |
| `deploy/Caddyfile:43-45` | `/docs` 未内网限制 | 仅靠 `APP_DOCS_ENABLED=false` 单重防护 | 加内网 matcher |
| `deploy/docker-compose.yml` caddy `depends_on` | 无超时 | 前置服务慢启 caddy 启动失败 | `condition: service_healthy` + `start_period` |

### 5.3 正面设计

- ✅ 非 root 用户：backend APP 用户、frontend nginx 8080
- ✅ `/healthz` `/readyz` Caddy 内网 matcher 正确
- ✅ CSP 严格（`default-src 'self'`），HSTS + X-Frame-Options 齐全
- ✅ 资源限制完整（db 1G / backend 512M / frontend 256M / caddy 128M）
- ✅ 日志轮转 json-file 50M × 5
- ✅ `.secrets.baseline` + detect-secrets pre-commit
- ✅ `deploy.sh` trap 自动回滚
- ✅ migrate.sh 文件锁（虽需改进为 DB 锁）
- ✅ `pg_backup.sh` 空库检测 + gzip 完整性验证
- ✅ CI publish job 依赖 backend/frontend/docker-build 三者通过

---

## 6. 新发现的待办项（补充原 backlog）

按优先级标注，追加到 `2026-04-17-optimization-backlog.md`。

### P0 追加（3 项 · 事故风险）

| # | 项目 | 维度 | 工作量 |
|---|---|---|---|
| **P0-NEW-1** | `sort_by` 无白名单（潜在 DoS / 信息泄露） | 安全 / 接口 | S |
| **P0-NEW-2** | 推送后 PO 号与 `in_transit_record` 映射缺失，存在重复推送风险 | 功能链路 | M |
| **P0-NEW-3** | `backend/app/main.py` 无 CORSMiddleware（若改分离部署立即失败） | 交互 / 部署 | S |

### P1 追加（10 项 · 季度内）

| # | 项目 | 维度 | 工作量 |
|---|---|---|---|
| **P1-NEW-1** | `SuggestionListView` 补货发起页全量加载改服务端分页 | 前端性能 | M |
| **P1-NEW-2** | `SkuCard` 图片 `loading="lazy"` | 前端性能 | S |
| **P1-NEW-3** | JWT 刷新机制或滑动续期 | 交互 / 安全 | M |
| **P1-NEW-4** | `IMAGE_TAG` 默认值 `latest` / `APP_BASE_URL` 补 `.env.example` | 部署 | S |
| **P1-NEW-5** | `smoke_check.sh` 增加业务端点验证 | 部署 | S |
| **P1-NEW-6** | `migrate.sh` 文件锁改 `pg_try_advisory_lock` | 部署 | S |
| **P1-NEW-7** | `deploy.yml` `check-ci` 改 `workflow_run` 触发 | CI/CD | S |
| **P1-NEW-8** | SKU 启用条件加 `is_matched && online_status=active` 联查 | 功能链路 | M |
| **P1-NEW-9** | `page_size` 上限按数据域分层统一 | 接口 | S |
| **P1-NEW-10** | `SuggestionListOut` / `SkuConfigListOut` 补 `page` / `page_size` 字段 | 接口 | S |

### P2 追加（7 项 · 质量提升）

| # | 项目 | 维度 | 工作量 |
|---|---|---|---|
| **P2-NEW-1** | 前端 `LoginResponse.user` 改精确类型 `UserInfo` | 交互 | S |
| **P2-NEW-2** | 前端 422 降级路径加 `console.warn` 便于排障 | 交互 | S |
| **P2-NEW-3** | `GET /api/suggestions` 改标准 `COUNT` 查询（弃 `with_only_columns`） | 接口 | S |
| **P2-NEW-4** | `GET /api/config/warehouse` / `zipcode-rules` 预留分页参数 | 接口 | S |
| **P2-NEW-5** | 订单页查询缓存（同筛选 5 分钟复用） | 前端性能 | S |
| **P2-NEW-6** | 无仓库国家引擎静默降级改显式告警 | 功能链路 | S |
| **P2-NEW-7** | Caddyfile `/docs` 加内网 matcher（与原 P0-4 合并） | 部署 / 安全 | S |

### P3 追加（2 项 · 观察备案）

| # | 项目 | 维度 | 工作量 |
|---|---|---|---|
| **P3-NEW-1** | `pg_backup.sh` 跨平台 `stat` | 部署 | S |
| **P3-NEW-2** | 仓库国家变更级联 `inventory_snapshot_latest.country` | 数据 | M |

---

## 7. 与原 backlog 的合并建议

原 `2026-04-17-optimization-backlog.md` 已列 54 项，本次新增 22 项，合计 **76 项**。

**变动**：
- 原 P0-4（`/docs` 内网限制）与 P2-NEW-7 合并
- 原 P0-6（SAST/SCA）独立保留
- 原 backlog 的 P0 仍为 8 项 + 新增 3 项 = **11 项 P0**

**建议下一步**：
1. 优先处理本次新发现的 **3 项 P0**（`sort_by` 白名单 / PO 在途映射 / CORS）
2. 再合并处理原 P0 的 S 项
3. 原 backlog 与新 backlog 统一到一份，按季度滚动维护

---

## 8. 评分汇总

| 项目 | 原评估 | 深审修正 | 变动原因 |
|---|---|---|---|
| 架构设计 | 3.5 | 3.5 | 无变动 |
| 代码质量 | 3.0 | 3.0 | 无变动 |
| 安全性 | 4.0 | **3.5** | 发现 `sort_by` 无白名单、CORS 未配置 |
| 可测试性 | 3.5 | 3.5 | 无变动 |
| 可观测性 | 4.0 | 4.0 | 无变动 |
| 性能 | 4.0 | **3.8** | 补货发起页全量加载风险 |
| 可靠性 | 4.0 | **3.7** | PO 在途映射缺失 |
| 部署 | 4.0 | 4.0 | 小缺陷多但不影响评级 |
| 数据层 | 5.0 | 5.0 | 无变动 |
| 可维护性 | 3.5 | 3.5 | 无变动 |
| 前端 UX/DX | 4.0 | **3.8** | SkuCard 无 lazy、无 token 刷新 |
| CI/CD | 5.0 | **4.5** | check-ci name 匹配风险 |
| 扩展性 | 4.0 | 4.0 | 无变动 |
| 技术债 | 3.0 | 3.0 | 无变动 |
| 合规 | 4.0 | 4.0 | 无变动 |

**调整后综合得分：3.85 / 5**（原 3.9，下调 0.05）

---

## 附录：本次审查未覆盖但值得后续补做

- 数据库 migration downgrade 真实跑通验证（P2-10 原 backlog 已列）
- 多用户并发场景的业务一致性（当前 1-5 用户无压力）
- 长时间运行后的内存/连接池/文件句柄泄漏
- 前端 accessibility（键盘导航、屏幕阅读器）
- 日志检索便利性（当前 JSON 无 aggregate layer）
