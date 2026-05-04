# Restock System 项目进度

> 最近更新：2026-05-04（订单列表新增平台筛选与动态平台选项；映射规则页共享组文案统一为“库存共用组”。）
> 本文档记录已交付能力和近期重大变更。架构细节见 [`Project_Architecture_Blueprint.md`](Project_Architecture_Blueprint.md)。

---

## 1. 总体状态

| 维度 | 状态 |
|---|---|
| 主链路 | 打通 — 赛狐同步 → 补货计算 → 建议编辑 → Excel 导出 + Snapshot 版本化（Plan A 已替换旧赛狐写入链路） |
| 工程化 | 运行时配置校验、健康检查、部署脚本、CI 骨架、测试覆盖已就绪 |
| 前端 | 已统一到 `PageSectionCard`；订单、历史、商品、库存、出库记录等高增长页面已切换为后端分页模式并补齐移动端卡片视图，设计系统对齐 shadcn Zinc |
| 后端 | 三服务进程分离（backend / worker / scheduler），TaskRun 队列稳定运行 |

---

## 2. 已交付能力

### 2.1 后端与部署

- **配置校验**：生产环境强制要求关键密钥与赛狐凭证
- **健康检查**：
  - `GET /healthz` — 进程存活
  - `GET /readyz` — 按进程角色检查数据库 + worker + reaper + scheduler
- **部署脚本**（`deploy/scripts/`）：
  - `deploy.sh` — 完整发布流程（备份 → 迁移 → 镜像 → smoke check → 失败回滚）
  - `migrate.sh` / `pg_backup.sh` / `restore_db.sh` / `rollback.sh` / `validate_env.sh` / `smoke_check.sh`
- **本地 dev 全栈验证**：新增 `deploy/docker-compose.dev.yml`、`deploy/Caddyfile.dev`、`deploy/.env.dev.example`，支持本机验证 db → migration → backend/worker/scheduler → frontend → caddy 的完整容器链路，且不污染生产 Compose
- **进程角色解耦**：通过 `PROCESS_ENABLE_WORKER/REAPER/SCHEDULER` 将 backend 镜像拆为 3 个服务
  - `backend` — 仅 HTTP API
  - `worker` — 任务执行 + 僵尸回收
  - `scheduler` — 定时入队
- **资源限制**（`docker-compose.yml`）：db 1G、backend 512M、worker 512M、scheduler 512M、frontend 256M、caddy 128M
- **后端镜像启动修复**：`backend/Dockerfile` 运行阶段将 `/install/lib/python3.11/site-packages` 加入 `PYTHONPATH`，修复 `uvicorn` / `alembic` 在容器中 `ModuleNotFoundError` 的阻塞问题

### 2.2 同步与调度
- **EU 合并同步口径**：订单、商品、出库、库存同步均按全局 eu_countries 将 EU 成员国合并到 EU，并在 original_* 字段保存原国家码；calc_engine 已移出 APScheduler 定时注册，仅保留手动生成入口。
- **新国家发现口径**：多平台订单同步遇到有效 2 位国家码时直接落入 `order_header.country_code` 并参与计算；若该国家已配置到 `eu_countries`，则归并为 `EU` 并在 `original_country_code` 保留原码；空值或非法国家码才写为 `ZZ` 并记录结构化日志。
- **订单处理列表同步来源**：`sync_order_list` 当前只调用赛狐订单处理列表 `/api/packageShip/v1/getPackagePage.json`，按 `purchaseDateStart/purchaseDateEnd` 拉取滚动 12 个月窗口，`pageSize=200`，继续复用全局店铺过滤；订单国家现在统一读取响应顶层 `marketplace` 字段，空值或非法值回落 `ZZ`，`address.countryCode/address.country` 不再作为国家来源。包裹数据统一写入 `source='订单处理'`，并保存 `package_sn/package_status/shop_name/postal_code/order_platform`；冲突更新时若本次接口邮编为空或地址缺失，不覆盖已有 `order_header.postal_code`。同步开始前会清理旧 `source in ('亚马逊','多平台')` 的订单头、明细、详情和详情抓取日志，避免切换后重复计算。
- **商品主数据同步来源**：`sync_product_listing` 先调用赛狐 SKU 主数据接口 `/api/commodity/pageList.json` 写入 `commodity_master`，再调用在线产品 listing 接口 `/api/order/api/product/pageList.json` 补充店铺、站点、sellerSku 与近 7/14/30 天销量。同步新发现的 SKU 只补建 `sku_config(enabled=true)`，不覆盖已有 `enabled` 与 `lead_time_days`；后续人工禁用的 SKU 不会被商品同步重新打开。

- **调度器开关**：`GET/POST /api/sync/scheduler`，开关状态持久化到 `global_config.scheduler_enabled`
- **调度参数实时生效**：`sync_interval_minutes`、`calc_cron` 保存后立即 reload
- **cron 校验**：非法表达式在保存前拦截
- **手动触发**：`POST /api/sync/shop` 及其他 sync 端点
- **自动同步任务**（APScheduler 间隔触发）：
  - `sync_product_listing` / `sync_inventory` / `sync_out_records` / `sync_order_list`
- **失败调用自动重试任务**：`retry_failed_api_calls` 每 5 分钟扫描 `api_call_log` 中可精确还原的赛狐 `40019` 失败调用（必须有 `request_payload`），按原始 `endpoint + request_payload` 从老到新重放；相关同步任务活跃时跳过，成功后将原失败日志标记为 `resolved` 并从失败列表隐藏，最多自动重试 5 次。
- **定时任务**（cron，Asia/Shanghai）：
  - 03:00 `sync_shop`
  - 03:30 `sync_warehouse`
  - 02:00 `daily_archive`
  - 默认 08:00 `calc_engine`（可配置，`global_config.suggestion_generation_enabled` 控制是否实际产出建议）
- **信息总览快照刷新任务**：`refresh_dashboard_snapshot` 通过 TaskRun 入队执行；`GET /api/metrics/dashboard` 只读返回现有快照 / 活跃任务状态，手动“刷新快照”是默认触发入口
- **旧订单详情抓取链路已删除**：订单处理列表已包含补货计算需要的订单、SKU、国家、邮编和包裹状态；自动 `sync_order_detail`、手动 `refetch_order_detail`、订单页“详情获取”入口、旧订单详情 job 模块和旧赛狐订单 endpoint 封装均已删除。`order_detail` / `order_detail_fetch_log` 作为历史表保留，订单详情弹窗只展示本地订单头与明细。

### 2.3 补货计算引擎
- **采购/补货拆分**：引擎同时产出 SKU 级 `purchase_qty` 与国家/仓库级 `country_breakdown` / `warehouse_breakdown` / `restock_dates`，并分别统计 `procurement_item_count`、`restock_item_count`；成功生成后自动关闭生成开关，等待导出与人工开新周期。

- **6 步流水线**（`backend/app/engine/runner.py`）：
  1. `step1_velocity` — 加权日均销量（7日×0.5 + 14日×0.3 + 30日×0.2）
  2. `step2_sale_days` — 可售天数 + 库存聚合（含在途）
  3. `step3_country_qty` — 各国补货量（`target_days + (demand_date - today)` 作为有效目标库存天数）
  4. `step4_total` — 总采购量（基于新的 Σcountry_qty − 本地库存 + ceil(Σvelocity × safety_stock_days)，clamp 到 0；`buffer_days` 不参与采购量）
  5. `step5_warehouse_split` — 按邮编规则分配到具体仓库；订单样本来自 `source='订单处理'` 且 `package_status!='has_canceled'` 的包裹订单，以 `quantity_shipped - refund_num` 为样本数量，优先使用 `order_header.postal_code`，已知邮编命中部分按真实比例分配，未知部分按该国家已配置邮编规则的仓均分
  6. `step6_timing` — 紧急标志与补货日期（任一正补货国家 `sale_days <= lead_time_days` 即为紧急；`restock_date[sku][country] = today + int(sale_days[sku][country]) − lead_time_days`）
- **补货区域过滤**：全局参数 `restock_regions` 支持按国家多选；为空数组时表示全部国家参与计算，配置后仅这些国家的订单会参与 `step1_velocity` 销量统计和 `step5_warehouse_split` 的国家订单分仓
- **并发保护**：`pg_advisory_xact_lock(7429001)` 事务级锁，阻止并发引擎覆盖彼此
- **补货日期参与数量计算**：`POST /api/engine/run` 必填 `demand_date` 且不能早于北京时间今天；runner 按 `today=now_beijing().date()` 计算 `demand_days=max(demand_date - today, 0)`，再用 `target_days + demand_days` 作为 Step 3 有效目标库存天数；`restock_regions` 仍只决定哪些国家参与补货，`restock_dates` 继续保存用于追溯、导出和紧急程度判断，不再按日期过滤国家
- **快照追溯**：`velocity_snapshot`、`sale_days_snapshot`、`global_config_snapshot` 存入 JSONB 字段；其中 `global_config_snapshot` 会记录 `restock_regions` 与本次补货日期 `demand_date`

### 2.4 补货建议管理
- **采购/补货独立导出**：建议单分为采购 Tab 与补货 Tab，采购快照只要求 purchase_qty > 0，补货快照只要求国家补货量大于 0；两类快照按 snapshot_type 独立递增版本、独立更新条目导出状态。

- **建议单**：`draft / archived / error` 状态流转（Plan A 后端重构后旧链路状态 `partial` / `pushed` 已随 §3.49 一并移除）
- **跨页选择**：补货发起页的 `selectedIds` 数组跨分页保持，支持全选筛选后的所有条目
- **编辑校验**：建议详情支持编辑 `total_qty` / `country_breakdown` / `warehouse_breakdown`；国家补货量不要求与总采购量一致，已配置仓库时仓内分量之和必须等于国家补货量；`urgent` 会随国家补货量变更按对应 SKU 的提前期重新判定
- **历史记录删除**：历史记录页新增建议单删除入口，删除准入统一为 `snapshot_count === 0`（尚未生成任何导出快照的建议单才可物理删除，保留快照的建议单保留历史追溯不允许删除）
- **触发方式中文化**：历史记录页“触发方式”由原始值改为中文展示，当前口径统一为“手动触发 / 自动触发”
- **Excel 导出**：业务人员在建议详情勾选 `export_status='pending'` 的条目，点击“导出 Excel”走一步式 `POST /api/suggestions/{id}/snapshots` + `GET /api/snapshots/{id}/download` blob 下载；服务端生成不可变 `suggestion_snapshot` + `suggestion_snapshot_item` JSONB 快照并同步落盘 Excel 文件，后续可反复下载；元信息页记录“补货日期”，采购/补货明细表不增加补货日期列；首次导出后 `global_config.suggestion_generation_enabled` 自动翻 OFF，业务人员在全局配置页翻回 ON 时会二次确认并归档全部 `draft` 建议单以开启下一周期

### 2.5 前端 Dashboard 体系
- **嵌套路由与 Tab 视图**：当前建议、建议详情、历史记录均拆为 procurement / restock 子路由，`SuggestionTabBar` 统一切换；采购页默认按 `commodity_sku` 稳定排序，仅展示商品信息、采购量与导出状态，补货页支持国家与仓库下钻。

- **统一页面容器**：所有列表页使用 `PageSectionCard`（`#title` + `#actions` slot）
- **移动端增强基础设施**：`AppLayout.vue` 在窄屏改用顶部菜单按钮 + `el-drawer` 导航；`PageSectionCard` 的 actions 区在小屏自动纵向排列；`TablePaginationBar` 基于 `useResponsive()` 在手机端切换为紧凑分页；`element-overrides.scss` 统一补齐移动端 dialog、表单与表格横向滚动兜底。
- **移动端卡片列表**：新增 `frontend/src/components/MobileRecordList.vue` 与 `frontend/src/composables/useResponsive.ts`，桌面端保留原 `el-table`，移动端复用同一份接口响应展示卡片，不新增移动专用 API 或 store。
- **共享工具模块**：
  - `frontend/src/utils/format.ts` — 时间格式化（`formatShortTime` / `formatDateTime` / `formatDetailTime`）和分页工具（`clampPage`）
  - `frontend/src/utils/warehouse.ts` — 仓库类型标签和标签类型
  - `frontend/src/utils/countries.ts` — 国家代码映射
  - `frontend/src/utils/status.ts` — 状态元数据
  - `frontend/src/utils/tableSort.ts` — 排序工具
  - `frontend/src/utils/monitoring.ts` — 监控页名称映射、分位点工具和任务反馈文案
- **Dashboard 复用组件**：
  - `DashboardPageHeader` / `DashboardStatCard` / `DashboardSection` / `DashboardChartCard` / `DataTableCard`
  - `BaseChart`（ECharts 封装）
- **数据加载模式**：订单页、历史记录页、商品页、库存页、出库记录页使用“后端分页 + 后端筛选”；仓库、店铺等低增长基础页仍保留轻量分页
- **商品页主数据口径**：`DataProductsView.vue` 通过 `/api/data/sku-overview` 展示 `commodity_master + sku_config`，商品名、图片、状态、组合标识、采购周期优先取主数据；listing 仅作为展开明细和销量参考，无 listing 的商品 SKU 也会显示。
- **筛选控件高度统一**：`PageSectionCard` 的 `section-actions` 强制所有控件 32px 高度
- **订单处理列表展示**：`DataOrdersView.vue` 展示包裹状态、店铺名称、平台、国家、邮编与本地订单明细；筛选支持 SKU / 订单号、国家、店铺、平台和包裹状态，其中平台选项来自 `GET /api/data/order-platforms` 返回的已落库订单平台。来源和包裹号不再作为页面展示或搜索字段，平台字段改为标签样式，店铺仅显示名称，订单明细中的商品 SKU 固定使用 `commoditySku`。
- **全局参数页补货区域配置**：`GlobalConfigView.vue` 的“补货区域”多选已接入动态国家选项，保存前变更检测与配置变更提示已纳入 `restock_regions`
- **动态国家选项**：`GET /api/config/country-options` 返回内置国家与订单、仓库、库存、出库在途中已观测国家的并集，并在输出前统一标准化 ISO 二字码别名；订单、库存、出库、仓库、邮编规则、补货区域和 EU 成员国配置均改用该接口，接口不可用时前端降级使用内置选项。
- **信息总览风险图与首行卡片**：`WorkspaceView.vue` 左侧图表使用“各国缺货风险分布”分组柱状图，按实时 `sale_days` 把各国 SKU 分为“紧急 / 临近补货 / 安全”三类并列展示；首行卡片则改为“需补货SKU / 无需补货SKU / 覆盖国家”，其中 `需补货SKU` 基于当前系统补货计算口径统计 `total_qty > 0` 的启用 SKU 数，`无需补货SKU` 为剩余启用 SKU 数，右侧“补货量国家分布”继续基于当前建议单全部条目的 `country_breakdown` 汇总
- **急需补货SKU口径**：信息总览中的“急需补货SKU”按“商品信息 / 国家 / 可售天数”逐行展示；仅展示存在有效国家级 `sale_days` 且低于等于提前期的行；其中可售天数直接取当前建议单 `sale_days_snapshot` 中该国家对应 SKU 的值，小于 1 天统一显示为 `<1天`
- **信息总览快照模式**：`WorkspaceView.vue` 优先读取 `/api/metrics/dashboard` 返回的 `dashboard_snapshot` 缓存，页面头部展示快照状态和同步时间；无缓存或旧快照时返回 `snapshot_status="missing"`，不自动触发刷新，页面仅在具备 `home:refresh` 时展示“刷新快照”按钮与任务进度轮询

### 3.97 前端移动端增强版（2026-05-04）
- **公共布局**：`frontend/src/components/AppLayout.vue` 在手机端隐藏固定侧栏，顶部栏显示菜单按钮，并通过 `el-drawer` 展示原导航；桌面端侧栏折叠与 hover 子菜单行为保持不变。
- **共享组件**：新增 `frontend/src/composables/useResponsive.ts` 统一输出 `isMobile/isTablet`；新增 `frontend/src/components/MobileRecordList.vue` 作为移动端卡片列表外壳；`TablePaginationBar.vue` 手机端隐藏 total/page size 并使用紧凑 pager。
- **高频数据页**：`DataOrdersView.vue`、`DataProductsView.vue`、`DataInventoryView.vue`、`DataOutRecordsView.vue` 在移动端切换为卡片列表，保留桌面端表格；订单详情弹窗手机端全屏，库存 / 出库 / 商品 listing 明细保留可展开区域。
- **建议与历史页**：`ProcurementListView.vue`、`RestockListView.vue`、`SuggestionHistoryView.vue` 移动端使用卡片展示主要字段与操作，继续复用现有跨页选择、导出和删除逻辑；`SuggestionDetailDialog.vue` 手机端全屏，版本列表与明细区改为上下布局。
- **低频页兜底**：`PageSectionCard.vue`、`DashboardPageHeader.vue`、`DashboardSection.vue`、`DataTableCard.vue`、`GlobalConfigView.vue` 和 `element-overrides.scss` 补齐小屏动作区换行、表单单列化、dialog 宽度和表格横向滚动规则，配置/监控页保持可用不遮挡。
- **验证**：前端 `cmd /c npm run build` 通过；`cmd /c npm test` 在提权环境通过（31 个文件、136 条测试）。

### 3.96 商品 SKU 默认启用与历史启用迁移（2026-05-04）
- **默认启用**：`backend/app/sync/product_listing.py` 的商品主数据补齐与 listing 补齐均改为只给缺失 SKU 新建 `sku_config(enabled=true)`；`backend/app/api/config.py` 的商品页“同步商品主数据”补齐入口同样默认启用新 SKU。
- **保留人工禁用**：上述入口都只插入缺失配置，不更新已有 `sku_config`，因此用户后续手动禁用的 SKU 不会被商品同步覆盖。
- **历史迁移**：新增 `backend/alembic/versions/20260504_1000_enable_existing_sku_configs.py`，一次性执行 `UPDATE sku_config SET enabled = true WHERE enabled = false`；downgrade 不反向关闭历史 SKU。
- **测试**：更新 `backend/tests/unit/test_sync_product_listing_job.py` 与 `backend/tests/unit/test_sku_init.py`，覆盖同步补齐和商品页补齐的新 SKU 默认启用口径。

### 3.99 订单平台筛选与映射规则文案调整（2026-05-04）
- **订单平台筛选**：`GET /api/data/orders` 新增 `platform` 查询参数，按 `order_header.order_platform` 精确筛选；`GET /api/data/order-platforms` 返回去重、非空、按名称排序的平台列表，权限沿用 `DATA_BIZ_VIEW`。
- **数据库索引**：`backend/alembic/versions/20260504_1800_add_order_platform_purchase_index.py` 为 `order_header(order_platform, purchase_date)` 增加复合索引，SQLAlchemy model 同步声明 `ix_order_header_platform_purchase`，用于平台筛选和按下单时间排序。
- **前端筛选**：`frontend/src/views/data/DataOrdersView.vue` 新增“平台”下拉筛选，页面加载时独立获取平台选项；平台选项加载失败时保留空选项，不阻断订单列表加载。
- **映射规则文案**：`frontend/src/views/SkuMappingRuleView.vue` 移除映射规则区和库存共用组区的说明描述；共享组相关页面文案统一为“库存共用组 / 新增库存共用组 / 添加SKU”，后端接口路径与模型命名保持不变。
- **测试**：补充 `backend/tests/unit/test_data_orders_api.py` 与前端 `DataOrdersView`、`SkuMappingRuleView` 测试，覆盖平台筛选、平台选项接口、平台选项失败降级和文案口径。

### 3.98 库存 SKU 共享组与组件归一（2026-05-04）
- **数据库表**：`physical_item_group` 与 `physical_item_sku_alias` 继续作为共享组载体，但组表已移除 `primary_sku`；组内成员现在平权，唯一约束只保留组名唯一与成员 SKU 全局唯一。
- **后端服务**：`backend/app/services/physical_item.py` 改为提供 `sku_to_group_key` / `members_by_group_key`，仅用于库存组件 SKU 的共享组解析；商品 SKU 不再归一到共享组。
- **引擎接入**：`backend/app/engine/runner.py` 保持商品 SKU 原样进入 Step 1 / Step 5 与建议展示；`backend/app/engine/sku_mapping.py` 在加载规则与汇总组件库存时先将库存组件 SKU 解析到共享组身份，再做库存合并和扣减，并会折叠同一商品下重复的等价替代组。
- **配置接口**：`GET/POST/PATCH/DELETE /api/config/physical-item-groups` 保留；`frontend/src/views/SkuMappingRuleView.vue` 改为“库存共用组”管理区，仅维护组名、成员 SKU、启用状态与备注，并在映射规则表中展示组件所属共用组。
- **测试**：补充 `backend/tests/unit/test_physical_item.py`、`backend/tests/unit/test_engine_sku_mapping.py` 与前端 `SkuMappingRuleView` 测试，覆盖成员校验、库存共享组解析和重复替代组折叠。

### 3.95 订单邮编空值不覆盖修复（2026-05-04）
- **同步保护**：`backend/app/sync/order_list.py` 保持从 `raw.address.postalCode` 解析邮编；插入新订单时仍允许 `postal_code=NULL`，但订单头唯一键冲突更新时，若本次赛狐响应邮编为空字符串、`null` 或 `address` 缺失，会从 `ON CONFLICT DO UPDATE SET` 中移除 `postal_code`，避免把已有有效邮编覆盖为空。
- **有效更新**：当本次响应包含非空 `address.postalCode` 时，`postal_code` 仍正常参与 upsert 更新，用于修正赛狐侧最新邮编。
- **测试**：补充 `backend/tests/unit/test_sync_order_list_eu.py`，覆盖非空邮编参与更新、空字符串或缺失地址不参与冲突更新。

### 3.93 新观测国家展示补齐与 ZZ 原因确认（2026-05-03）
- **国家展示**：`backend/app/core/countries.py` 与 `frontend/src/utils/countries.ts` 补齐 `AT - 奥地利`、`CH - 瑞士`、`CY - 塞浦路斯`、`DK - 丹麦`、`EE - 爱沙尼亚`、`FI - 芬兰`、`LT - 立陶宛`、`LV - 拉脱维亚`、`MT - 马耳他`、`SI - 斯洛文尼亚`。动态国家选项和前端本地 `getCountryLabel()` 均会按“国家码 - 中文名”展示，不再仅显示原始代码。
- **时区约束**：`backend/app/core/timezone.py` 为上述内置国家补齐 IANA 时区，保持“内置国家必须有时区映射”的单测约束。
- **ZZ 原因**：生产订单重新同步后，`ZZ` 主要集中在 Temu 半托管、Walmart、TikTok、Wayfair 等非 Amazon 平台；当前同步层以赛狐包裹列表顶层 `marketplace` 为唯一国家来源，只在该字段缺失或不是有效两位国家码时写入 `ZZ`，不会按地址、店铺名或平台名猜测国家。
- **验证**：`pytest -p no:cacheprovider tests/unit/test_country_mapping.py tests/unit/test_timezone.py -q` 通过；`cmd /c npx vitest run src/utils/countries.test.ts` 通过。

### 3.94 订单页口径清理与国家来源切换（2026-05-03）
- **国家来源**：`backend/app/sync/order_list.py` 现在只读取赛狐订单处理列表响应顶层 `marketplace` 作为订单国家来源；有效二字码继续按 EU 配置映射到 `EU`，无法识别或为空时写入 `ZZ`。`address.countryCode` / `address.country` 不再参与国家解析。
- **页面口径**：`backend/app/api/data.py` 与 `backend/app/schemas/data.py` 的订单列表 / 详情 DTO 去掉了 `source` 对前端的展示字段；`frontend/src/views/data/DataOrdersView.vue` 移除了来源与包裹号展示/搜索，平台改为标签样式，店铺仅显示名称，详情基础信息不再显示店铺 ID / 来源 / 包裹号，明细商品列固定使用 `commoditySku`。
- **详情定位**：前端详情接口仍可带 `package_sn` 作为内部精确定位参数，但不再把 `source` 作为页面输入；订单页搜索也不再按包裹号匹配。
- **历史数据修复**：不做一次性 SQL 猜测回填；历史订单国家口径通过重新执行 `sync_order_list` 任务回填，剩余 `ZZ` 代表赛狐包裹列表本身没有返回可识别国家码。

### 3.91 订单同步切换为订单处理列表接口（2026-05-03）
- **赛狐接口**：`backend/app/saihu/endpoints/package_ship.py` 新增 `POST /api/packageShip/v1/getPackagePage.json` 封装；`sync_order_list` 改为只按 `purchaseDateStart/purchaseDateEnd` 同步滚动 12 个月订单处理列表，`pageSize=200`，继续支持 `shopIdList` 店铺过滤。
- **落库字段**：`backend/alembic/versions/20260503_1700_use_package_order_source.py` 为 `order_header` 新增 `package_sn/package_status/shop_name/postal_code`，唯一键调整为 `shop_id + amazon_order_id + source + package_sn`。新数据统一写 `source='订单处理'`，`order_platform=platformName`，包裹内 `orders` 生成订单头，`items.commoditySku` 写入 `order_item.commodity_sku`，`quantityOrdered` 同时作为下单数和计算数。
- **旧来源清理**：每次订单处理列表同步前会删除旧 `source in ('亚马逊','多平台')` 的 `order_header`、级联明细、`order_detail` 与 `order_detail_fetch_log`，避免旧亚马逊 / 多平台订单与新包裹订单重复参与销量计算。
- **补货计算口径**：`step1_velocity` 和 `step5_warehouse_split` 只消费 `source='订单处理'`；除 `package_status='has_canceled'` 的已作废包裹外，其余包裹状态都参与销量和分仓样本。Step 5 邮编优先读取 `order_header.postal_code`。
- **入口停用**：`sync_all` 与 APScheduler 不再入队 `sync_order_detail`；`POST /api/sync/order-detail/refetch`、前端 `OrderDetailFetchAction` 和相关手动详情获取 API 已移除。`retry_failed_api_calls` 仅把 `/api/packageShip/v1/getPackagePage.json` 映射到 `sync_order_list / sync_all`，旧订单列表、旧多平台订单和旧订单详情接口不再自动重放。
- **前端展示**：订单页改为包裹订单视图，展示包裹状态、店铺名称、平台、国家、邮编和本地订单明细，详情弹窗不再依赖订单详情抓取；来源和包裹号不再展示或参与搜索，包裹号仅保留为详情内部定位字段。
- **测试**：新增 `backend/tests/unit/test_package_ship_endpoint.py`，并更新订单同步、EU 映射、Step 1 / Step 5、数据订单 API、失败重试、同步控制和订单页前端测试，覆盖分页请求体、拆包唯一键、旧来源清理、已作废包裹排除和本地详情展示。

### 3.92 旧订单详情与旧订单接口残留清理（2026-05-03）
- **后端删除**：删除旧订单详情 job 模块 `backend/app/sync/order_detail.py`，删除旧赛狐订单 endpoint 封装 `backend/app/saihu/endpoints/order_list.py`、`multiplatform_order.py`、`order_detail.py`。数据库 `order_detail` / `order_detail_fetch_log` 表和 ORM 模型继续保留，仅作为历史数据结构。
- **监控口径**：`GET /api/monitor/api-calls` 不再返回基于旧亚马逊订单详情抓取的 `postal_compliance_warning`；旧订单详情合规统计 SQL 已移除。
- **限流与重试**：`/api/order/detailByOrderId.json` 不再有独立 QPS 覆盖，按默认 1 QPS 口径展示；`retry_failed_api_calls` 仍只支持当前可还原 endpoint，旧订单列表、旧多平台订单和旧订单详情接口不参与自动重放。
- **前端历史日志展示**：`frontend/src/utils/monitoring.ts` 保留旧 endpoint 名称映射，但标注为“历史日志展示：旧订单列表同步 / 旧多平台订单同步 / 旧订单详情同步”，仅用于既有 `api_call_log` 展示。
- **测试清理**：删除旧 job / endpoint 单测 `test_sync_order_detail_job.py`、`test_sync_order_detail_classification.py`、`test_multiplatform_order_endpoint.py`，并更新监控、限流、重试和前端 monitoring 测试。

### 3.90 SKU 映射共享库存按销量分配（2026-05-03）
- **数据库迁移**：`backend/alembic/versions/20260503_1500_allow_shared_sku_mapping_components.py` 移除 `sku_mapping_component.inventory_sku` 全局唯一约束，新增 `rule_id + inventory_sku` 唯一约束；不同商品映射规则可复用同一库存 SKU，同一商品规则内仍禁止重复组件。
- **接口与导入**：`backend/app/api/config.py` 不再拦截跨商品库存 SKU 复用；Excel/CSV 导入只校验同一商品规则内的重复库存 SKU。`backend/app/schemas/config.py` 的校验文案同步调整为“同一商品规则内库存SKU重复”。
- **引擎分配**：`backend/app/engine/sku_mapping.py` 在同一仓库、同一组件 SKU 维度先按启用商品规则分配共享组件库存，再按组合短板计算可组装数量；Step 2 使用仓库所在国家的 `velocity[sku][country]` 分配，Step 4 使用 SKU 全国家 velocity 合计分配；若共享 SKU 中任一启用商品没有正销量信号，则该组件在共享商品间均分。停用规则不参与共享分配，商品 SKU 自身库存仍直接计入。
- **测试**：补充 `backend/tests/unit/test_engine_sku_mapping.py` 与 `backend/tests/unit/test_sku_mapping_import.py`，覆盖共享组件按比例分配、无销量均分、本地仓合计销量口径、跨商品导入复用成功、同规则重复失败和模型唯一约束口径。

### 3.89 商品主数据同步接入（2026-05-03）
- **赛狐接口**：新增 `backend/app/saihu/endpoints/commodity.py`，封装 `POST /api/commodity/pageList.json`，分页请求体为 `pageNo/pageSize`，默认不加 `state`、`isGroup` 过滤，避免漏掉停售、组合 SKU 或加工 SKU。
- **数据库迁移**：`backend/alembic/versions/20260503_1000_add_commodity_master.py` 新增 `commodity_master` 表，主键为赛狐返回的 `sku`，保存 `commodity_id/name/state/is_group/img_url/purchase_days/child_skus/last_sync_at` 等主数据字段。
- **同步任务**：`backend/app/sync/product_listing.py` 的 `sync_product_listing` 调整为“商品主数据 → 在线产品 listing”两段同步；主数据和 listing 新发现的 SKU 当前默认补建 `sku_config(enabled=true)`，已存在的 `enabled` 与 `lead_time_days` 不覆盖。`run_engine` 仍只读取 `SkuConfig.enabled=True`。
- **商品页接口**：`GET /api/data/sku-overview` 改为 `SkuConfig` 左连接 `CommodityMaster`，搜索支持 SKU 与商品名；返回新增 `commodity_id/state/is_group/purchase_days/has_listing`，商品名和图片优先使用主数据，listing 仅用于展开明细和销量汇总。
- **库存匹配口径**：库存页未匹配判断改为“存在商品主数据 SKU、listing 商品 SKU 或映射组件库存 SKU”即视为已匹配，接入完整商品 SKU 后减少库存 SKU 误判。
- **前端与监控**：`frontend/src/views/data/DataProductsView.vue` 改为“商品主数据”展示，`frontend/src/config/sync.ts` 与 `frontend/src/utils/monitoring.ts` 将商品同步文案更新为“商品主数据同步”；赛狐 `40019` 精确重试映射新增 `/api/commodity/pageList.json -> sync_product_listing`。
- **测试**：新增 `backend/tests/unit/test_saihu_commodity_endpoint.py`、`backend/tests/unit/test_data_sku_overview_api.py`，并更新商品同步、SKU 初始化、库存匹配与商品页前端测试，覆盖分页请求、空 SKU 跳过、默认启用、主数据优先和无 listing 展示。

### 3.88 SKU 映射替代组合改造（2026-05-02）
- **数据库迁移**：`sku_mapping_component` 新增 `group_no`，默认值为 1，旧组件行自动归入“组合 1”；当时仍保留 `sku_mapping_rule.commodity_sku` 唯一与 `sku_mapping_component.inventory_sku` 全局唯一，后续 §3.90 已将组件唯一约束收窄为同一规则内唯一。
- **规则语义**：同一商品 SKU 下，相同 `group_no` 的组件是 AND 组合，不同 `group_no` 是 OR 替代方案。`A=B+C+D` 表示一个组合，`A=B 或 C 或 D` 表示三个单组件组合，`A=B+C+D 或 E+F+G` 表示两个组合。
- **计算口径**：`backend/app/engine/sku_mapping.py` 改为每仓库、每组合分别计算可组装数量；单组件组合按 `库存数 // quantity`，多组件组合按 `min(各组件库存数 // quantity)`，同商品同仓库的多个替代组合结果相加。Step 2 海外仓库存/在途换算和 Step 4 本地仓采购量抵扣共用该口径，不跨仓拼组件。
- **导入导出与 API**：映射组件 DTO 增加 `group_no`，校验 `group_no >= 1`、组件数量为正、库存 SKU 不重复；导出模板新增“组合编号”列，导入兼容旧模板，缺少“组合编号”时默认组合 1。
- **前端页面**：`frontend/src/views/SkuMappingRuleView.vue` 的组件编辑器改为按“方案”分组展示，公式预览使用 `或` 连接替代组合；新增/编辑 payload 会携带 `group_no`。
- **测试**：补充 `backend/tests/unit/test_engine_sku_mapping.py`、`backend/tests/unit/test_sku_mapping_import.py` 与 `frontend/src/views/__tests__/SkuMappingRuleView.test.ts`，覆盖替代单组件、替代多组件、不跨仓、本地仓无国家字段、旧/新模板导入、重复库存 SKU 和前端公式/payload。

### 3.87 Step 5 未知分仓样本均分修复（2026-04-30）
- **分仓样本口径**：`backend/app/engine/step5_warehouse_split.py` 的 `load_all_sku_country_orders()` 从订单详情内连接改为左连接，同 SKU + 国家下已发货/部分发货订单即使无详情、无邮编也会进入分仓样本；样本数量改为 `max(quantity_shipped - refund_num, 0)`，与 Step 1 销量口径一致，零或负数净发货不参与分仓。
- **未知需求分配**：Step 5 先把订单样本拆成已知仓需求与未知仓需求；已知部分继续按邮编规则命中的仓库比例分配，未知部分按该国家已配置邮编规则的仓库均分，最终合并为 `warehouse_breakdown`。若全部未知，保持规则仓均分；若国家无规则仓，仍保持不拆仓。
- **解释快照**：`allocation_snapshot` 保留原字段，混合场景 `allocation_mode` 记录为 `mixed_known_unknown`，并继续记录 `matched_order_qty`、`unknown_order_qty` 与 `eligible_warehouses`。
- **测试**：更新 `backend/tests/unit/test_engine_step5.py`，覆盖未知样本不跟随已知仓、纯已知 60/40、全未知均分、无规则仓不拆仓、净发货数扣减与订单详情左连接。

### 3.86 调度器下次执行时间与店铺自动同步修复（2026-04-30）
- **状态接口修复**：`backend/app/tasks/scheduler.py` 的 `scheduler_status()` 在 API-only backend 进程中不再依赖本进程 APScheduler 已启动；当 `job.next_run_time` 为空时，会通过 job trigger 和北京时间推导下一次触发时间，避免 `/api/sync/scheduler` 返回全空计划导致前端“自动同步下次执行”图表无内容。
- **店铺基础同步纳入自动调度**：`sync_shop` 新增每日 03:00 APScheduler cron 入队，与前端“自动同步任务”列表口径一致；`sync_warehouse` 继续每日 03:30 执行，商品、库存、出库、订单列表、订单详情继续按 `sync_interval_minutes` 间隔执行。
- **测试**：更新 `backend/tests/unit/test_scheduler_api.py`，覆盖 API 进程推导 next run 和 `sync_shop` 每日 cron 注册。

### 3.85 角色权限配置语义修复（2026-04-29）
- **权限依赖补齐**：`backend/app/core/permissions.py` 新增 `expand_permission_dependencies()`，角色权限保存时会将 `*:edit`、`*:operate`、`*:manage`、`*:delete`、`*:export`、`*:refresh`、`*:new_cycle` 等操作权限自动补齐同组 `*:view`；若系统未注册对应 `view` 权限则保持原权限不变。`frontend/src/views/RoleConfigView.vue` 勾选和保存前也执行同一口径预览。
- **会话失效体验**：`backend/app/api/auth_roles.py` 在角色权限集合无实际变化时不再删除重插 `role_permission`，也不再 bump 该角色用户的 `perm_version`；当前用户所在角色权限实际变化时，前端保存前弹确认，保存成功后清理本地登录态并跳转登录页。
- **超管有效权限**：`GET /api/auth/roles/{role_id}/permissions` 对超管角色返回全部 active 权限码，与登录态中的有效权限保持一致；超管角色权限修改仍拒绝。
- **测试**：新增 `backend/tests/unit/test_auth_roles.py` 与 `frontend/src/views/__tests__/RoleConfigView.test.ts`，覆盖权限依赖补齐、无变化不 bump、超管权限读取/拒改、当前角色保存确认与主动退出。

### 3.84 Review 修复：凭据清理、仓库拆分与订单明细保护（2026-04-29）

- **赛狐示例凭据清理**：`docs/saihu_api/test_sellfox_apis.ps1` 不再提供默认 access token / client secret，改为必须从 `SELLFOX_ACCESS_TOKEN`、`SELLFOX_CLIENT_SECRET` 环境变量读取；`backend/tests/unit/test_sign.py` 改用非敏感示例值，`docs/saihu_api` 中真实形态 token / secret 已替换为 `<ACCESS_TOKEN>`、`<CLIENT_SECRET>` 等占位符。
- **Step 5 仓库拆分修复**：`backend/app/engine/step5_warehouse_split.py` 的 matched 模式从逐仓 `round()` 改为 floor + 最大余数法，按规则仓顺序稳定处理余数，保证 `sum(warehouse_breakdown.values()) == country_qty`，避免小数量、多仓比例下超配。
- **订单明细保护策略**：`backend/app/sync/order_list.py` 在亚马逊 `orderItemVoList` 或多平台 `skuInfoVo` 等明细缺失、为空、或全部因关键字段缺失被跳过时，不再删除本地旧 `order_item`；只有本次解析到有效明细时才清理未出现的旧 item，并记录结构化 warning 便于排查赛狐异常响应。
- **测试**：补充 `backend/tests/unit/test_engine_step5.py` 的 `country_qty=5`、权重 `3/3/3/1` 超配回归用例；补充 `backend/tests/unit/test_sync_order_list_eu.py` 覆盖亚马逊与多平台空/无效明细不触发删除；签名单测固定断言更新为非敏感 fixture。

### 3.83 国家代码 ISO 标准化与成员国显示修复（2026-04-29）

- **统一规范化**：`backend/app/core/countries.py` 新增国家代码别名映射，当前 `UK` 统一归一为 ISO 标准代码 `GB`；观测国家、赛狐多平台国家字段和 EU 成员国配置均复用该函数。
- **补货区域别名归一**：`backend/app/core/restock_regions.py` 复用国家码标准化入口，保存 `restock_regions=["UK","GB"," ro "]` 时会归一去重为 `["GB","RO"]`，引擎继续消费标准化后的补货区域集合。
- **配置读写**：`GlobalConfigOut` 读取历史 `eu_countries=["UK","RO"]` 时返回 `["GB","RO"]`；`PATCH /api/config/global` 保存 `eu_countries` 时先标准化、去重，再用标准化集合触发 `backfill_order_eu_country_mapping()` 回填历史订单。
- **EU 本地回填扩展**：保存 `eu_countries` 且实际变化时，`backend/app/core/country_mapping.py` 会在同一事务内回填 `order_header`、`inventory_snapshot_latest`、`in_transit_record`；库存源国家优先取 `original_country`，在途源国家优先取 `original_target_country`，缺失时取当前国家字段，加入 EU 写 `EU + original_*`，移出 EU 恢复源国家并清空 `original_*`。
- **国家选项显示**：`GET /api/config/country-options` 采集观测国家时会先标准化，因此历史 `UK` 只展示为 `GB - 英国`；内置中文名补齐 `CZ - 捷克`、`RO - 罗马尼亚`，这些代码不再进入 `unknown_country_codes`。
- **时区防漏**：`backend/app/core/timezone.py` 补齐 `CZ -> Europe/Prague`、`RO -> Europe/Bucharest`，`country_to_tz()` 会先执行国家码别名标准化，因此 `UK` 使用 `GB` 的 `Europe/London`；单元测试约束除 `EU`、`ZZ` 外所有内置国家必须配置时区。
- **前端降级选项**：`frontend/src/utils/countries.ts` 补齐 `CZ`、`RO` 的中文标签；正常路径仍以接口返回的 `label` 为唯一显示来源。
- **测试**：补充 `backend/tests/unit/test_country_mapping.py`、`backend/tests/unit/test_config_schema.py`、`backend/tests/unit/test_timezone.py`、`backend/tests/integration/test_config_api.py` 与 `frontend/src/views/__tests__/GlobalConfigView.test.ts` 覆盖别名标准化、成员国读写、国家选项、EU 本地回填、时区映射和前端 label。

### 3.82 订单同步水位与多平台 6 个月窗口修复（2026-04-29）
- **亚马逊水位口径**：`backend/app/sync/common.py` 的 `mark_sync_success()` 新增可选 `success_at` 参数，`sync_order_list` 成功后传入本次查询窗口的 `date_end`，避免任务完成时间晚于查询窗口结束时间时跳过运行期间产生的 `updateDateTime` 更新；其他同步任务未传 `success_at` 时仍使用完成时间作为成功水位。
- **多平台窗口**：`backend/app/sync/order_list.py` 将多平台订单 `purchase` 滚动窗口从近 30 天调整为 6 个日历月，并用日历月回退算法处理月末边界，例如 `2026-08-31 -> 2026-02-28`、闰年 `2024-08-31 -> 2024-02-29`；接口参数仍为 `startDate/endDate`，格式保持 `yyyy-MM-dd`。
- **测试**：补充 `backend/tests/unit/test_sync_common.py` 和 `backend/tests/unit/test_sync_order_list.py`，覆盖显式成功水位、订单任务传入 `date_end`、多平台 6 个月窗口和月末夹取规则。

### 3.81 部署镜像拉取失败回退本地构建（2026-04-28）

- **发布容错**：`deploy/scripts/deploy.sh` 在 `docker compose pull backend worker scheduler frontend` 失败或超时时，会自动回退为 `docker compose build backend frontend`，继续使用当前 `IMAGE_TAG=sha-<commit>` 在服务器本地构建应用镜像；应用镜像 pull 默认最多等待 600 秒，可通过 `IMAGE_PULL_TIMEOUT_SECONDS` 覆盖。
- **服务口径**：`worker` 与 `scheduler` 共用 backend 镜像，因此回退构建 backend/frontend 即覆盖全部应用服务；数据库和 Caddy 镜像仍保持原有“尽量 pull，失败不阻塞”的行为。
- **文档同步**：`docs/deployment.md` 的发布流程已补充 GHCR 拉取失败时的本地构建回退说明。

### 3.80 多平台订单同步参数修正（2026-04-28）

- **接口参数**：`backend/app/saihu/endpoints/multiplatform_order.py` 按赛狐文档改为传 `startDate` / `endDate`，日期格式为 `yyyy-MM-dd`，避免 `/api/multiplatform/order/list.json` 返回 `40014 [endDate] 结束日期不能为空`。
- **返回字段兼容**：`backend/app/sync/order_list.py` 兼容文档字段 `skuInfoVo` 作为多平台订单明细来源；`extraInfo` 若返回 JSON 字符串，会解析后继续读取 `warehouse_country`。
- **状态映射**：多平台订单状态兼容英文枚举 `Pending / Unshipped / PartiallyShipped / Shipped / Completed / Canceled / Refunded`，继续归一到本地订单状态口径。
- **测试**：新增 `backend/tests/unit/test_multiplatform_order_endpoint.py`，并更新 `backend/tests/unit/test_sync_order_list_eu.py` 覆盖请求体字段、`skuInfoVo`、英文状态与字符串 `extraInfo`。

### 3.79 动态国家选项与新国家入库口径（2026-04-28）

- **配置接口**：新增 `GET /api/config/country-options`，返回内置常见国家与数据库已观测国家的并集，并标注 `builtin`、`observed`、`can_be_eu_member` 与 `unknown_country_codes`；观测来源包括 `order_header.country_code/original_country_code`、`warehouse.country`、`inventory_snapshot_latest.country/original_country`、`in_transit_record.target_country/original_target_country`。
- **同步口径**：`backend/app/sync/order_list.py` 对多平台订单的 `marketplaceCode` / `extraInfo.warehouse_country` 执行 2 位字母国家码校验；新国家如 `RO` 首次出现时按 `RO` 入库，不再变成 `ZZ`；空值或非法值才回落 `ZZ` 并记录 `multiplatform_order_country_unrecognized` 结构化日志。
- **EU 配置保护**：`backend/app/schemas/config.py` 对 `eu_countries` 继续归一化去重，但拒绝 `EU` 与 `ZZ`；管理员保存新 EU 成员后，沿用既有 `backfill_order_eu_country_mapping()` 回填历史订单。
- **前端接入**：全局参数页、订单页、库存页、出库页、仓库页和邮编规则页均改用动态国家选项；全局参数页会提示“新发现国家”，未知名称国家显示原始代码，EU 成员国下拉不展示 `EU` / `ZZ`。
- **测试**：补充 `backend/tests/integration/test_config_api.py`、`backend/tests/unit/test_config_schema.py`、`backend/tests/unit/test_sync_order_list_eu.py` 与 `frontend/src/views/__tests__/GlobalConfigView.test.ts`，覆盖动态选项、EU 成员校验、新国家入库和前端加载。

### 3.78 订单页接入多平台订单接口（2026-04-28）

- **数据库字段**：`order_header` 新增 `source`、`order_platform`，历史数据默认回填为“亚马逊”；唯一约束调整为 `shop_id + amazon_order_id + source`。`order_detail` 与 `order_detail_fetch_log` 新增 `source` 并纳入主键，避免同店铺同订单号不同来源互相覆盖详情状态。
- **同步任务**：`sync_order_list` 保持原任务名和入口不变，内部先按 `updateDateTime` 增量同步亚马逊订单，再按 6 个日历月 `purchase` 滚动同步多平台订单；`sync_all`、定时同步和 `/api/sync/orders` 无新增步骤。
- **字段归一**：亚马逊订单写 `source='亚马逊'`、`order_platform='亚马逊'`；多平台订单写 `source='多平台'`、`order_platform=platformName`，`orderNo` 继续落入内部 `amazon_order_id` 字段。多平台状态归一为 `Shipped / PartiallyShipped / Unshipped / Pending / Canceled / Unknown`，仅 `localSku` 非空的明细写入 `order_item`。
- **补货计算**：多平台订单明细沿用现有 `order_item` 销量口径，归一状态为 `Shipped / PartiallyShipped` 且 SKU 有效时参与 `step1_velocity` 销量统计；`step5_warehouse_split` 当前通过订单详情左连接消费有效发货订单，无详情或无邮编的多平台订单按未知需求参与规则仓均分。
- **详情拉取**：`sync_order_detail`、`refetch_order_detail` 与订单详情接口查询均带 `source` 口径；后台详情任务只筛选 `source='亚马逊'`，不会对多平台订单调用 `/api/order/detailByOrderId.json`。
- **前端展示**：订单列表新增“来源”“订单平台”列，详情弹窗展示对应字段；多平台订单详情状态显示“不适用”，点击详情仍可查看本地订单头与明细。
- **40019 重试**：`retry_failed_api_calls` 支持 `/api/multiplatform/order/list.json`，其忙碌任务映射为 `sync_order_list` / `sync_all`，避免与正在运行的订单同步并发重放。

### 3.77 Deploy 等待 CI 与镜像发布完成（2026-04-28）

- **门禁口径**：`.github/workflows/deploy.yml` 的 `check-ci` 继续先把手动输入的分支、tag、完整或短 commit SHA 解析为完整 `RESOLVED_SHA`，再用 `checks.listForRef` 查询目标 commit 的 check runs。
- **等待范围**：Deploy 必须等待 `backend`、`frontend`、`docker-build`、`publish` 四个 required checks 全部 `success`；check 尚未出现或仍处于 `queued` / `in_progress` 时，每 15 秒继续轮询，最多等待 30 分钟。
- **失败处理**：任一 required check 返回 `failure`、`cancelled`、`timed_out`、`action_required` 或其他非成功终态时，`check-ci` 立即失败并输出具体 job 名与结论；超时后输出仍未完成的 required checks。
- **发布体验**：保留手动触发 `Deploy(ref=...)` 与 `v*` tag push 自动 Deploy 行为；刚 push 后可立即手动触发 Deploy，workflow 会在 SSH 部署前等待 CI 与 `sha-<commit>` GHCR 镜像发布完成。

### 3.76 SKU 映射规则与补货计算接入（2026-04-27）

- **数据库表**：新增 `sku_mapping_rule` / `sku_mapping_component`，一条商品 SKU 只能有一条规则；初始版本要求 `sku_mapping_component.inventory_sku` 全局唯一，后续 §3.90 已改为允许跨商品规则共享库存 SKU，并在引擎计算时按销量比例分配共享组件库存。
- **配置接口**：新增 `GET/POST/PATCH/DELETE /api/config/sku-mapping-rules`，支持按商品 SKU / 库存 SKU 搜索、启用状态筛选、分页；新增 `/export` Excel 导出与 `/import` Excel/CSV 导入，导入列为“商品SKU、库存SKU、组件数量、启用、备注”，整批校验失败时不写入。
- **前端页面**：新增 `frontend/src/views/SkuMappingRuleView.vue`，入口在“设置 > 基础配置 > 映射规则”，查看使用 `config:view`，新增、编辑、启停、删除、导入使用 `config:edit`。
- **计算口径**：`backend/app/engine/sku_mapping.py` 提供同仓库组装计算；`step2_sale_days.py` 在海外库存 + 在途读取后叠加映射可组装数量，`step4_total.py` 在本地库存读取后叠加映射可组装数量。`A=2*B` 按 `floor(B/2)`，`A=1*B+2*C` 按同仓库 `min(floor(B/1), floor(C/2))`；组件分散在不同仓库不跨仓组合。
- **边界口径**：同步落库数据不改写，库存明细页仍展示原始库存 SKU；停用规则保留但不参与计算；组件在途必须有目标仓库 ID 才参与映射组合，直接商品 SKU 在途仍沿用现有按国家聚合口径。

### 3.75 同步日志 40019 精确自动重试（2026-04-27）
- **日志字段**：`api_call_log` 新增 `request_payload`、`retry_status`、`auto_retry_attempts`、`next_retry_at`、`resolved_at`、`last_retry_error`、`retry_source_log_id`。`SaihuClient.post()` 会保存原始请求 payload；最终仍为 `40019` 的可还原调用初始化为 `queued`，历史无 payload 的 `40019` 标记为 `unsupported`。
- **后台任务**：新增 `retry_failed_api_calls` TaskRun job，由 APScheduler 每 5 分钟入队，使用 TaskRun dedupe 避免并发；任务只处理 `saihu_code=40019`、`retry_status='queued'`、`request_payload IS NOT NULL`、`auto_retry_attempts < 5`、`retry_source_log_id IS NULL` 的原始失败日志，并按 `called_at ASC, id ASC` 从老到新执行。
- **冲突与限速**：重试前按 endpoint 检查相关 `pending/running` TaskRun；`sync_all` 视为所有 endpoint 忙碌，当前订单处理列表接口检查 `sync_order_list`。重放间隔按 QPS 保守计算，当前默认 1 QPS endpoint 为 1.5 秒。
- **终态**：重试成功时原失败日志标记 `resolved` 并从失败列表隐藏；再次 `40019` 未满 5 次继续 `queued`，第 5 次标记 `permanent`；非 `40019` 失败或其他异常直接标记 `permanent`。
- **前端与 API**：`GET /api/monitor/api-calls/recent` 返回重试状态、尝试次数和 `can_retry`；`only_failed=true` 默认排除 `resolved` 和自动重试子日志。`POST /api/monitor/api-calls/{id}/retry` 改为单条精确重试入口，仅允许可还原的 `40019` 日志入队。
- **展示口径**：`GET /api/monitor/api-calls/recent` 额外返回 `retry_display_status`、`retry_display_text`、`retry_attempt_text`。`0/5` 表示后台 `retry_failed_api_calls` 的自动重放次数，不代表 `SaihuClient` 的即时 tenacity 重试次数；`retry_status IS NULL` 的 40019 原始日志展示为“未入自动队列”，自动重试子日志展示为“即时重试日志”，次数显示 `-`。

### 3.74 库存明细未匹配标识与筛选（2026-04-27）
- **判定口径**：库存 SKU 若在 `product_listing.commodity_sku` 中不存在，则 `backend/app/api/data.py` 返回 `is_package=true`；存在则返回 `false`。该口径不新增数据库字段，不依赖商品名或图片是否为空。
- **接口过滤**：`GET /api/data/inventory` 与 `GET /api/data/inventory/warehouse-groups` 新增可选查询参数 `is_package=true|false`；缺省时保持全部库存。筛选通过 `EXISTS / NOT EXISTS` 下推到 SQL，分页总数、仓库分组 `sku_count`、可用库存合计和占用库存合计均按筛选后结果计算。
- **前端展示**：`frontend/src/views/data/DataInventoryView.vue` 的筛选区展示“未匹配”下拉（全部 / 未匹配 / 已匹配），展开明细表展示“未匹配”列，`●` 表示未匹配，`○` 表示已匹配，圆点按当前文本 2 倍字号显示。
- **测试**：更新 `backend/tests/unit/test_data_inventory_groups_api.py` 与 `frontend/src/views/__tests__/DataInventoryView.test.ts`，覆盖 `is_package` 字段、筛选参数和回到第一页行为。
### 3.72 信息总览 EU 口径修正（2026-04-26）
- **EU 配置回填**：`PATCH /api/config/global` 保存 `eu_countries` 且实际变化时，会按当前 EU 配置重新归一化本地 `order_header.country_code`、`marketplace_id` 与 `original_country_code`；源国家优先取 `original_country_code`，否则取当前 `country_code`，不调用赛狐 API。
- **快照刷新**：`eu_countries` 变化仍会将 `dashboard_snapshot.stale=True`，沿用现有信息总览自动刷新任务机制；`eu_countries` 值未变化时不执行历史订单回填，也不额外置 stale。
- **风险分布口径**：`backend/app/api/metrics.py` 的 `country_risk_distribution`、`urgent_count` / `warning_count` / `safe_count`、`risk_country_count` 和 `top_urgent_skus` 统一按 `restock_regions` 过滤后的国家展示；`restock_regions=[]` 仍表示全部国家参与，配置为 `["EU"]` 时风险图和覆盖国家只显示 `EU`。
- **保留统计**：`restock_sku_count` / `no_restock_sku_count` 继续使用当前补货引擎数量口径，不改变 API 返回字段结构和前端页面结构。

### 3.73 生产主分支切换与部署分支对齐（2026-04-27）
- **主分支口径**：生产线从 `recover-demand-date-base` 切换为新的 `master`，旧 `master` 保留为 `master_former` 备查。
- **部署兼容**：`.github/workflows/deploy.yml` 在分支部署时使用 `git checkout -B <branch> origin/<branch>`，确保服务器本地旧分支不会因非快进历史阻塞后续 `master` 部署。
- **发布口径**：当前线上 revision 为 `182beabc6110c4f983faef5489e6bb617c449a6e`，后续生产部署可直接选择 `master` 或发布 tag。

### 3.71 补货日期参与数量计算（2026-04-26）
- **引擎口径**：`backend/app/engine/runner.py` 不再调用旧的持久化前日期过滤逻辑；`demand_date` 只作为补货目标日期参与数量计算，公式为 `国家补货量=max(ceil((target_days + demand_days) × 国家日均销量 - 国家库存覆盖量), 0)`，其中 `demand_days=max(demand_date - today, 0)`。
- **采购联动**：Step 4 继续使用 `compute_total()`，但输入的 `country_qty` 已是补货日期扩展后的国家补货量，因此采购量会随更远补货日期同步增加；公式保持 `max(Σcountry_qty - 国内仓库存 + ceil(Σvelocity × safety_stock_days), 0)`。
- **保留字段**：API 字段名继续为 `demand_date`，`restock_dates` 继续计算并保存，用于追溯、Excel 明细和紧急程度判断，不再决定国家是否进入本次补货。
- **信息总览**：`backend/app/api/metrics.py` 的“需补货SKU / 无需补货SKU”统计读取当前最新 `draft` 建议单的 `global_config_snapshot.demand_date` 计算同一口径；无当前建议单时按 `demand_days=0` 统计。
- **展示与导出**：`frontend/src/views/SuggestionListView.vue`、`frontend/src/components/SuggestionDetailDialog.vue` 与 `backend/app/services/excel_export.py` 的用户可见文案统一为“补货日期”，接口契约不变。

### 3.66 Deploy workflow 短 SHA 解析修复（2026-04-25）
- **check-ci 修复**：`Deploy` workflow 不再直接把手动输入的短 SHA 传给 `actions/checkout`；先 checkout 默认分支并 fetch 全量分支 / tag，再把分支名、tag、完整或短 commit SHA 解析成完整 commit。
- **CI 校验口径**：`checks.listForRef` 改为使用解析后的完整 SHA，避免短 SHA 被误当作分支 / tag 通配 ref 导致 checkout 失败。

### 3.68 CI pip-audit 工具链修复（2026-04-25）
- **后端 CI**：`.github/workflows/ci.yml` 暂时对 `pip-audit` 增加 `--ignore-vuln CVE-2026-3219`，避免 PyPI 尚无 `pip>=26.0.2` 可安装版本时，工具链自身 `pip 26.0.1` 漏洞阻断后端 job；待修复版发布后移除忽略项。

### 3.69 部署脚本可执行位修复（2026-04-25）
- **部署权限**：恢复分支同步将 `deploy/scripts/*.sh` 标记为 `100755`，避免 SSH 部署时直接调用 `validate_env.sh`、`rollback.sh` 等脚本出现 `Permission denied`。
- **tag 更新**：`Deploy` workflow 的 fetch 改为显式强制拉取 `+refs/heads/*` 与 `+refs/tags/*`，不再使用隐式 `--tags`，允许服务器本地 tag 跟随 GitHub 强制更新，避免重新移动 `v-demand-date-20260425` 后报 `would clobber existing tag`。

### 3.70 生产冒烟检查本机解析修复（2026-04-25）
- **冒烟检查**：`deploy/scripts/smoke_check.sh` 支持 `SMOKE_BASE_URL` 与 `SMOKE_RESOLVE_LOCAL`，生产默认通过 `curl --resolve APP_DOMAIN:443:127.0.0.1` 从服务器本机访问 Caddy 的 `/healthz`、`/readyz`，避免公网健康端点被 Caddy 404 保护时误触发回滚。
- **文档同步**：`deploy/.env.example`、`docs/deployment.md`、`docs/runbook.md` 与 `docs/onboarding.md` 已说明生产公网访问 `/healthz`、`/readyz` 返回 404 属于预期安全策略。

### 3.67 Alembic 生产 revision 兼容修复（2026-04-25）
- **迁移拓扑**：保留补货日期相关真实迁移 `20260423_1100_add_restock_dates` 与 `20260424_0100_drop_purchase_date_from_suggestions`，并新增 `20260425_1420` 兼容 marker。
- **生产兼容**：`20260425_1420` 不修改 schema，仅用于兼容已经推进到该 revision 的生产库，避免回到该迁移链路时提示 `Can't locate revision identified by '20260425_1420'`。

### 3.65 Caddy CSP 临时放行 Google Fonts（2026-04-25）
- **CSP 调整**：`deploy/Caddyfile` 的 `style-src` 放行 `https://fonts.googleapis.com`，`font-src` 放行 `https://fonts.gstatic.com`，用于兼容当前生产镜像中仍存在的 Google Fonts 外链。
- **风险说明**：这是兼容性方案，攻击面略大于完全自托管字体；长期建议改为自托管或系统字体栈。

### 3.64 历史产物与旧配置清理（2026-04-25）
- 删除历史设计材料目录，并同步移除 AGENTS、onboarding、架构蓝图、README 与报告中的旧入口引用。
- 删除旧赛狐写入模块残留目录与各类本地构建 / 测试缓存产物；`deploy/data/`、`backend/.venv/`、`cloudflared-windows-amd64.exe`、`Ai_project.lnk` 保留不动。
- 运行时配置移除旧写入重试与批量大小配置项，`backend/.env.example`、`docs/deployment.md` 与配置校验单测同步收敛。

### 3.63 安全库存采购-only 项保留到采购建议（2026-04-24）
- **过滤口径**：旧 `demand_date` 日期筛选在无补货国家命中时，不再直接丢弃 SKU；只要过滤前完整 SKU 口径的 `purchase_qty > 0`，仍保留为采购-only 条目。（该口径已由 §3.71 取消，`demand_date` 现作为补货日期参与数量计算。）
- **补货字段收口**：采购-only 条目持久化时写入 `country_breakdown={}`、`warehouse_breakdown={}`、`allocation_snapshot={}`、`restock_dates={}`、`total_qty=0`、`urgent=false`；补货清单与补货 Excel 仍只包含实际补货量大于 0 的条目。
- **计数与导出**：`procurement_item_count` 继续按 `purchase_qty > 0` 统计，`restock_item_count` 继续按 `total_qty > 0` 统计；采购快照可导出这类安全库存采购项，补货快照不包含它们。
- **测试**：更新 `backend/tests/unit/test_engine_runner.py`，覆盖采购-only 保留、无采购量继续丢弃、补货项与安全库存采购-only 项混合生成，以及采购/补货 item count 独立统计。

### 3.62 前端隐藏补货日期展示（2026-04-24）
- **页面展示收口**：`frontend/src/views/suggestion/RestockListView.vue` 与 `frontend/src/components/SuggestionDetailDialog.vue` 移除 SKU 表格“最晚补货日期”列和展开行国家级“补货日期”列，当前前端仅展示商品、补货量、国家分布与仓库分配。
- **数据与导出保留**：API 类型中的 `restock_dates`、后端持久化、快照冻结和 `backend/app/services/excel_export.py` 补货 Excel “补货日期”列保持不变，用于历史追溯、紧急程度判断与 Excel 交付。

### 3.61 旧 `demand_date` 日期筛选口径（2026-04-24，已由 §3.71 取代）
- **旧范围**：`backend/app/engine/runner.py` 当时的持久化前日期筛选由 `restock_dates[country] == demand_date` 调整为 `restock_dates[country] <= demand_date`，选择某一日期时会包含当天及之前已到期但尚未处理的补货国家。
- **空日期处理**：当时 `restock_dates[country]` 为空的国家不纳入日期筛选范围，因为无法判断是否已到期；无补货命中但 `purchase_qty > 0` 时会保留为采购-only 条目，否则返回 `no_suggestion_needed`，不归档旧 draft、不关闭生成开关、不生成空建议单。
- **展示与导出**：当时 `frontend/src/views/SuggestionListView.vue`、`frontend/src/components/SuggestionDetailDialog.vue` 与 `backend/app/services/excel_export.py` 的用户可见文案随该口径调整；API 字段名继续保持 `demand_date`。（当前文案见 §3.71。）

### 3.60 `demand_date` 驱动采补建议生成（2026-04-24）
- **发起入口校验**：`frontend/src/views/SuggestionListView.vue` 删除手动“刷新”按钮，改为默认空的“补货日期”日期选择器；点击生成时前端校验空值与早于北京时间今天，合法时调用 `runEngine({ demand_date })`。
- **任务复用与结果摘要**：前端新增 `frontend/src/api/task.ts:listTasks()`，页面加载与切回时分别查询 `calc_engine` 的 `pending` / `running` 任务并复用 `TaskProgress`；后端扩展 `JobContext.progress(result_summary=...)` 与 worker 进度写回，生成成功或无需求均写结构化 JSON。
- **后端入队契约**：`POST /api/engine/run` 请求体改为必填 `{ "demand_date": "YYYY-MM-DD" }`，缺失、格式错误或早于北京时间今天均由 Pydantic 返回 422；入队 payload 写入 `demand_date`，仍使用 `dedupe_key="calc_engine"` 防并发生成。
- **旧持久化前筛选**：当时 `backend/app/engine/runner.py` 先计算完整中间结果，再按 `demand_date` 保留到期国家；该口径已由 §3.71 取消，当前 `demand_date` 作为补货日期参与数量计算。
- **展示与导出**：当前建议页顶部、历史详情元信息与 Excel 元信息页均展示补货日期；历史列表、采购明细表、补货明细表不新增补货日期列，不改导出文件名。

### 3.59 移除采购日期与采购页紧急筛选（2026-04-24）
- **后端链路收缩**：`backend/alembic/versions/20260424_0100_drop_purchase_date_from_suggestions.py` 删除 `suggestion_item`、`suggestion_snapshot_item` 上的 `purchase_date`；`backend/app/engine/step6_timing.py` 仅保留 `urgent` 与 `restock_dates` 计算，`backend/app/engine/runner.py`、`backend/app/api/suggestion.py`、`backend/app/api/snapshot.py` 与相关 DTO 不再写入、存储或返回采购日期。
- **采购导出精简**：`backend/app/services/excel_export.py` 的采购工作簿移除“采购日期”“逾期备注”两列，采购导出仅保留 SKU、商品名、图片 URL、采购量、各国动销合计、本地库存可用+占用、安全库存天数。
- **前端采购侧收口**：`frontend/src/views/suggestion/ProcurementListView.vue` 移除“仅显示紧急（≤30天）”开关、`purchase_date` 列与相关排序/筛选逻辑；`frontend/src/components/SuggestionDetailDialog.vue` 的采购历史详情同步移除采购日期列；`frontend/src/components/PurchaseDateCell.vue` 及其单测已删除。
- **验证**：后端定向测试 `pytest -p no:cacheprovider backend/tests/unit/test_engine_step6.py backend/tests/unit/test_engine_runner.py backend/tests/unit/test_excel_export_service.py backend/tests/unit/test_suggestion_patch.py backend/tests/unit/test_suggestion_model.py backend/tests/unit/test_suggestion_snapshot_model.py backend/tests/unit/test_suggestion_snapshot_schemas.py backend/tests/integration/test_snapshot_api.py` 通过（`51 passed, 13 skipped`，跳过因 `TEST_DATABASE_URL` 未配置）；前端 `npm run test -- src/views/suggestion/__tests__/ProcurementListView.test.ts src/components/__tests__/SuggestionDetailDialog.test.ts`、`npx vue-tsc --noEmit`、`npm run build` 通过。

### 3.58 删除整单后自动尝试开启生成开关（2026-04-24）
- `frontend/src/views/SuggestionListView.vue` 的“删除整单”改为前端串行两步：先调用 `DELETE /api/suggestions/{id}` 删除当前 draft 建议单，再调用 `PATCH /api/config/generation-toggle` 尝试把全局“采购建议生成开关”设为开启。
- 删除成功且开关开启成功时，页面提示“删除成功，已自动开启生成开关”，并同步刷新当前建议单与开关状态；不再跳转到全局参数页。
- 若删单成功但开关开启失败（如缺少 `restock:new_cycle` 权限或 `can_enable=false`），前端保留删除结果，提示用户“删除成功，但开启生成开关失败，请前往全局参数手动开启”，并刷新当前页状态。
- 更新 `frontend/src/views/__tests__/SuggestionListView.test.ts`，覆盖“删除成功后自动开启”“删除成功但开启失败”“删除失败时不触发开启”三条交互分支。

### 3.57 补货发起页支持跨页全选导出（2026-04-24）
- `frontend/src/views/suggestion/ProcurementListView.vue` 与 `frontend/src/views/suggestion/RestockListView.vue` 改为前端自管勾选状态：表头全选覆盖当前 Tab 下全部可导出条目，不再受当前分页限制；搜索仅用于定位并取消个别条目，翻页与筛选后已选状态持续回显。
- 新增 `frontend/src/views/suggestion/useCrossPageSelection.ts` 复用组合式逻辑，统一处理 `selectedIds`、全选/半选状态、按行勾选，以及 `suggestion.id` 切换后的选择重置和可导出 ID 集合变化后的自动清理。
- 采购/补货导出按钮文案改为显示当前总选中数，例如“导出采购单 Excel（N项）”“导出补货单 Excel（N项）”；导出时继续复用现有快照接口，仅把提交的 `item_ids` 改为跨页累计后的全局选择集合。
- 前端测试新增覆盖跨页全选、搜索后取消单条、翻页回显、切换建议单重置选择，以及导出接口收到全局选中 ID 集合的断言。

### 3.56 分仓候选仓收口为“仅规则仓参与”（2026-04-24）
- **Step5 口径调整**：`backend/app/engine/step5_warehouse_split.py` 的国家候选仓不再来自该国家全部海外仓，而是只来自“该国家下已配置邮编规则”的仓库集合。
- **兜底逻辑**：有订单未命中规则或该国无订单时，只在规则仓集合内均分；若该国家一个规则仓都没有，则该国家 `warehouse_breakdown` 为空，不再回退到该国家全部海外仓。
- **测试**：更新 `backend/tests/unit/test_engine_step5.py`，覆盖规则仓去重、无规则仓不参与、兜底均分仅限规则仓。

### 3.55 补货日期（最晚补货日期）落地（2026-04-23）
- **字段落地**：迁移 `20260423_1100` 为 `suggestion_item` 与 `suggestion_snapshot_item` 新增 JSONB 字段 `restock_dates`，按 `SKU × 国家` 冻结每个正补货国家的最晚补货日期，值为 ISO 日期字符串或 `null`。
- **计算口径**：`backend/app/engine/step6_timing.py` 新增 `compute_restock_dates()`，公式为 `restock_date[sku][country] = today + int(sale_days[sku][country]) − lead_time_days(sku)`；仅对 `country_breakdown[country] > 0` 的国家输出，缺少 `sale_days` 时保留 `null`，且不受 `buffer_days` 影响。
- **持久化与编辑**：`backend/app/engine/runner.py` 在生成建议单时写入 `restock_dates`；`backend/app/api/suggestion.py` 在 PATCH 修改 `country_breakdown` 后会同步重算 `total_qty`、`urgent` 与 `restock_dates`，前端保持只读展示，不提供手工编辑。
- **快照与导出**：`backend/app/api/snapshot.py` 在补货快照中冻结 `restock_dates`；`backend/app/services/excel_export.py` 的补货工作簿在 `SKU×国家`、`SKU×国家×仓库` 两个 Sheet 新增“补货日期”列。
- **前端展示策略**：当前前端不再展示“最晚补货日期”列或展开行国家级“补货日期”列；`restock_dates` 继续通过后端、快照与 Excel 导出保留，前端仅保留类型字段以兼容接口。

### 3.54 buffer_days / lead_time_days 计算口径调整（2026-04-23）
- **引擎公式**：`backend/app/engine/step4_total.py` 的采购量改为 `purchase_qty = max(0, Σcountry_qty − (local.available + local.reserved) + ceil(Σvelocity × safety_stock_days))`；`buffer_days` 保留兼容参数但不再参与采购量。
- **采购日期**：`backend/app/engine/step6_timing.py` 改为 `purchase_date = today + int(min_sale_days) − buffer_days − lead_time_days`；`urgent` 仍只按正补货国家 `sale_days <= lead_time_days` 判定，不受 `buffer_days` 影响。
- **追溯字段**：`backend/app/engine/runner.py` 继续在 `global_config_snapshot` 冻结 `buffer_days`，并将其传入 step6 用于采购日期计算；持久化字段仍为 `purchase_qty` / `purchase_date`。
- **测试**：更新 `backend/tests/unit/test_engine_step4.py`、`test_engine_step6.py`、`test_engine_runner.py`、`test_engine_types.py`，覆盖新公式、本地库存扣减、`buffer_days` 不影响采购量和采购日期提前逻辑。

### 3.53 采购/补货分拆与 EU 合并（2026-04-21）
- **数据模型**：迁移 `20260420_0900` 将采购与补货字段拆分：`global_config` 新增 `safety_stock_days` / `eu_countries`，`suggestion` 新增 `procurement_item_count` / `restock_item_count`，`suggestion_item` 新增 `purchase_qty` / `purchase_date` 与 `procurement_*`、`restock_*` 两组导出状态，`suggestion_snapshot` 新增 `snapshot_type`，同步源表补齐 `original_*` 字段用于保留 EU 合并前原国家。
- **同步层**：`backend/app/sync/order_list.py`、`product_listing.py`、`out_records.py`、`inventory.py` 接入 `app.core.country_mapping.apply_eu_mapping()`；DE/FR/IT/ES/NL/BE/PL/SE/IE 可按全局 `eu_countries` 合并为 `EU`，GB/UK 不纳入 EU，并在发生合并时写入对应 `original_*` 字段。
- **引擎**：`step4_total` 采购公式更新为 `purchase_qty = max(0, Σcountry_qty − (local.available + local.reserved) + ceil(Σvelocity × safety_stock_days))`，其中 `Σvelocity` 覆盖所有国家且 `buffer_days` 不参与采购量；`step6_timing` 新增 `purchase_date = today + int(min_sale_days) − buffer_days − lead_time_days`，runner 写入采购/补货 item_count，成功生成后自动翻 OFF。
- **API 与导出**：全局参数 DTO 删除旧 `calc_*` / `include_tax` / 默认采购仓字段，新增 `safety_stock_days`、`eu_countries` 与 generation-toggle `can_enable`；建议单响应/PATCH 支持采购数量与采购日期；快照端点拆分为 `POST /api/suggestions/{id}/snapshots/procurement` 与 `/restock`，旧端点返回 410，Excel 采购/补货工作簿格式独立。
- **前端**：`/restock/current`、`/restock/suggestions/:id`、`/restock/history` 改为 `procurement` / `restock` 嵌套路由；新增 `SuggestionTabBar`、`PurchaseDateCell`、采购列表、补货下钻列表、详情子视图、历史快照子视图；全局参数页新增安全库存与 EU 成员配置，`COUNTRY_OPTIONS` 增加 `EU-欧盟`。
- **验证**：宿主机后端 `python -m pytest -v -p no:cacheprovider` 结果 `308 passed`；前端 `npx vue-tsc --noEmit`、`npx vite build`、`npm run test -- --run` 通过（26 个测试文件 / 103 个用例）；本地 dev 容器通过 `deploy/docker-compose.dev.override.yml` 将 DB 端口映射到 15433 后完成生成 → 编辑 → 采购/补货双导出 → 翻 ON 归档 → 再生成 smoke。
### 3.52 Full audit 收口修复（2026-04-20）
- **后端并发与一致性**：
  - `backend/app/api/snapshot.py` 为建议单、导出条目和 `global_config` 增加 `SELECT ... FOR UPDATE`，避免并发导出 / 新周期切换时出现 version 冲突或对已归档建议继续导出。
  - `backend/app/api/snapshot.py` 将 `SuggestionItem.export_status='exported'` 延后到 Excel 文件成功落盘之后，失败分支只把 snapshot 标记为 `failed`，保留条目为 `pending` 以支持重试。
  - `backend/app/api/auth.py` 把登录失败计数改为锁行后重算/写回，避免并发失败登录丢失增量。
  - `backend/app/tasks/worker.py` 为 heartbeat、进度回写和终态写回统一增加 `status='running' + worker_id` 约束；租约丢失后抛 `TaskLeaseLostError` 并停止继续覆盖状态。
- **后端查询口径**：
  - `backend/app/api/suggestion.py` 新增 `display_status=pending|exported|archived|error`，历史记录页的状态过滤改为后端统一按 `snapshot_count` 派生，移除前端“先查 draft 再二次过滤当前页”的错位逻辑。
  - `backend/app/api/metrics.py` 的 Dashboard 当前建议只再读取 `draft`，补充 `suggestion_snapshot_count` 与旧/异常 `dashboard_snapshot.payload` 容错，避免信息总览 500。
  - `backend/app/api/config.py` 将 `sync_interval_minutes` / `calc_cron` / `scheduler_enabled` 纳入 scheduler reload 触发集合，参数保存后立即生效（`calc_enabled` 字段已在 Plan A 删除）。
- **前端交互**：
  - `frontend/src/views/WorkspaceView.vue` 统一改读 `exported_count`，右侧进度文案改为“已导出”，状态 tag 基于 `suggestion_snapshot_count` 派生。
  - `frontend/src/views/HistoryView.vue` 直接把 `display_status` 透传后端，新增“异常”筛选项并移除当前页二次过滤。
  - `frontend/src/views/SuggestionListView.vue`、`frontend/src/views/SuggestionDetailView.vue` 将生成开关探测改为 fail-close；探测失败时禁用生成/导出按钮。
  - `frontend/src/views/GlobalConfigView.vue` 把生成开关单独加载；全局配置主表单加载成功时不再因开关读失败而整页报错。
- **测试与审查**：
  - 新增/更新 `backend/tests/unit/test_metrics_snapshot_api.py`、`backend/tests/unit/test_suggestion_list_api.py`、`backend/tests/unit/test_worker.py`、`backend/tests/integration/test_snapshot_api.py` 与 5 个前端视图单测，覆盖快照失败重试、display_status 过滤、worker 租约丢失守卫和 fail-close 行为。
  - 二次人工 review 未发现新的阻断问题；CodeRabbit CLI 当前环境未安装，未执行外部 review。
- **本地 dev 重建稳定性**：
  - `deploy/docker-compose.dev.yml` 不再硬编码清华镜像，改为从 `deploy/.env.dev` 读取 `PIP_INDEX_URL` / `PIP_TRUSTED_HOST`，默认回落到官方 PyPI，避免本地 `docker compose ... up -d --build` 因单一镜像源超时而直接阻断。
  - `deploy/.env.dev.example`、`docs/deployment.md`、`docs/onboarding.md` 同步补充 pip 镜像源覆盖说明，保持本地全栈重建入口可调试。

### 3.51 Plan A 收尾 hotfix + 历史状态显示派生化（2026-04-19）
- **后端**：`backend/app/api/metrics.py` 的 `DashboardOverviewPayload` 为 `restock_sku_count`/`no_restock_sku_count`/`exported_count` 新增 `= 0` 默认值，兼容 Plan A 之前生成的旧 `dashboard_snapshot.payload`，修复信息总览 500。
- **部署**：`deploy/docker-compose.dev.yml` 给 `backend` 服务挂载 `./data/exports:/app/data/exports` 并在 `x-backend-env` 里显式声明 `EXPORT_STORAGE_DIR`，修复 Excel 导出 PermissionError。
- **前端 UX**：
  - `frontend/src/api/client.ts` 新增 axios 模块扩展 `suppressForbiddenToast`，避免可选探测触发"权限不足"误报；`frontend/src/api/config.ts` 的 `getGenerationToggle` 携带该标志。
  - `frontend/src/views/SuggestionListView.vue` 的"生成补货建议"按钮按 `toggle.enabled` 禁用 + `title` 提示，避免开关 OFF 时误导出"已刷新"成功 toast（runner 会 skip 但 task.status=success）。
- **历史状态显示 4 档派生化**：
  - `frontend/src/utils/status.ts` 新增 `deriveSuggestionDisplayStatus(status, snapshot_count)` + `getSuggestionDisplayStatusMeta`：`draft && snapshot_count=0 → 未提交`、`draft && snapshot_count>0 → 已导出`、`archived → 已归档`、`error → 异常` 兜底。
  - `frontend/src/views/HistoryView.vue` 合并"状态"+"导出状态"两列为一列；状态下拉改为 3 档 `未提交 / 已导出 / 已归档`，选"未提交/已导出"发 `status=draft` 再前端二次按 `snapshot_count` 过滤。
  - `SuggestionListView.vue` / `SuggestionDetailView.vue` 的状态 tag 同步切换到派生函数。
  - 测试：`status.test.ts` 新增派生函数断言；`HistoryView.test.ts` 状态下拉断言切换到新 value 枚举。

### 3.50 Plan A 前端收尾：导出按钮 + 历史快照区 + 生成开关 + 旧链路死代码清理（2026-04-19）
- 前端：新增快照 API 客户端与 blob 下载工具；建议单详情页加导出按钮（一步式 POST+GET blob）与历史快照区；全局配置页加生成开关卡片（即时保存 + 翻 ON 二次确认）；列表页加开关只读 tag；全量清理旧赛狐写入时代死代码（~110 行 UI + 8 死字段 + `utils/status.ts` map + 4 个测试文件的旧链路 case）；`Suggestion.status` TS 枚举收敛为 `'draft' | 'archived' | 'error'`；`HistoryView.canDelete` 改用 `snapshot_count === 0`。
- 后端：alembic 迁移 `20260419_0000_grant_export_and_config_view_to_business_role` 给“业务人员”角色补齐 `restock:export` + `config:view`（幂等 `ON CONFLICT DO NOTHING`）。
- 新增/更新文件：`frontend/src/api/snapshot.ts`、`frontend/src/utils/download.ts` 新增；`frontend/src/api/suggestion.ts`、`frontend/src/api/config.ts`、`frontend/src/utils/status.ts`、`frontend/src/views/SuggestionDetailView.vue`、`frontend/src/views/SuggestionListView.vue`、`frontend/src/views/HistoryView.vue`、`frontend/src/views/GlobalConfigView.vue` 同步收敛为导出视角，并清理旧字段、批量动作列等相关 UI 与测试分支。

### 3.49 Plan A 后端导出重构：旧赛狐写入链路 → Excel 导出 + Snapshot 版本化（2026-04-19）
- 数据模型：`backend/alembic/versions/20260418_0900_redesign_to_export_model.py` 新增 `suggestion_snapshot` / `suggestion_snapshot_item` / `excel_export_log` 三张表，清空 `suggestion` / `suggestion_item` 的旧链路字段，追加 `export_status` / `exported_snapshot_id` / `exported_at` / `archived_trigger` / `archived_by` 等导出 & 归档审计字段；`suggestion.status` 枚举收缩为 `draft / archived / error`；`global_config` 新增 `suggestion_generation_enabled` 与 `generation_toggle_updated_by / generation_toggle_updated_at`；非生产数据采用一次性迁移。
- ORM + DTO 同步：`backend/app/models/{suggestion,suggestion_snapshot,excel_export_log,global_config}.py`、`backend/app/schemas/{suggestion,suggestion_snapshot,config}.py` 去除全部旧链路字段并新增 snapshot 相关 DTO。
- Excel 生成：新增 `backend/app/services/excel_export.py`，基于 openpyxl 生成四 Sheet 工作簿（汇总 / 明细 / 国家 / 仓库分仓）；文件落到 `deploy/data/exports/{yyyy}/{mm}/` 容器卷，文件名由 `build_filename(suggestion_id, version, exported_at_compact)` 统一；`openpyxl>=3.1.2` 加入 `backend/pyproject.toml` 生产依赖。
- 新增快照 API（`backend/app/api/snapshot.py`）：`POST /api/suggestions/{id}/snapshots` 创建并冻结 snapshot、生成 Excel 并将 `suggestion_generation_enabled` 翻为 OFF；`GET /api/suggestions/{id}/snapshots`、`GET /api/snapshots/{id}`、`GET /api/snapshots/{id}/download` 支持列表 / 详情 / 下载计数 + `excel_export_log` 审计；时间戳统一走 `now_beijing()`。
- 生成开关 API（`backend/app/api/config.py`）：新增 `GET/PATCH /api/config/generation-toggle`；翻 ON 时连带归档全部 `status='draft'` 建议单并打上 `archived_trigger='admin_toggle'` + `archived_by` / `archived_at`。
- 建议单 & 引擎清理：`backend/app/api/suggestion.py` 删除旧赛狐写入端点，`GET /api/suggestions` 注入 `snapshot_count`，删除接口校验快照归属；`backend/app/engine/runner.py` 在生成开关关闭时直接返回 `None`，`_archive_active` 现由 `run_engine` 在写入新 draft 前主动调用，移除 `commodity_id` 自动补齐；`backend/app/tasks/access.py` 及任务注册清理旧赛狐写入作业。
- 权限：`backend/app/core/permissions.py` 新增 `restock:export` / `restock:new_cycle`，`superadmin` 自动继承。
- 代码删除：旧赛狐写入作业、`backend/app/saihu/endpoints/purchase_create.py`、`backend/app/core/commodity_id.py` 及对应旧单测。
- 集成测试抱真实 PostgreSQL：`backend/tests/integration/conftest.py` 采用 `NullPool` 避免跨 event loop 连接复用，client fixture 预置 role+sys_user 并以 `unittest.mock.patch` 短路 `/readyz` 的数据库 / 后台探测；`backend/tests/integration/factories.py` 新增 `seed_test_user`；`backend/pyproject.toml` 将 `asyncio_default_fixture_loop_scope` 改为 `function`；新增 `backend/tests/integration/test_export_e2e.py`、`test_generation_toggle_api.py` 等，`test_config_api.py` 同步新字段。24 项集成测试在 `replenish_test` 库全绿（`TEST_DATABASE_URL=postgresql+asyncpg://postgres@localhost:5433/replenish_test`）。

### 3.44 鉴权/RBAC 收口与快照刷新边界修复（2026-04-16）
- `backend/app/api/config.py`、`backend/app/api/data.py`、`backend/app/api/suggestion.py` 不再使用弱化版 `get_current_session()`；改为基于 `get_current_user()` / `require_permission()` 的后端权限校验，分别对 `config:*`、`data_base:*`、`data_biz:*`、`sync:view`、`restock:*`、`history:delete` 生效
- `backend/app/api/task.py` 改为按 `job_name` 做作业级权限隔离：同步类任务映射到 `sync:view` / `sync:operate`，`calc_engine` 映射到 `restock:operate`，`refresh_dashboard_snapshot` 映射到 `home:refresh`；通用创建接口不再接受旧赛狐写入作业
- `backend/app/api/suggestion.py` 旧赛狐写入任务的去重键曾按建议单和条目集合排序，避免不同子集误复用同一活跃任务
- `backend/app/api/metrics.py` 将 `GET /api/metrics/dashboard` 收敛为纯读取接口；无快照或旧快照时返回 `snapshot_status="missing"`，不再自动入队刷新；`GET /api/metrics/prometheus` 新增 `monitor:view` 校验
- `deploy/Caddyfile` 为 `/api/metrics/prometheus` 增加独立内网 matcher，公网请求直接返回 404，作为应用层权限之外的第二道防线
- **测试**：新增 `backend/tests/unit/test_task_api.py`，并更新 `backend/tests/unit/test_metrics_snapshot_api.py`、`backend/tests/unit/test_suggestion_patch.py`、`backend/tests/integration/conftest.py`、`frontend/src/views/__tests__/WorkspaceView.test.ts`

### 3.45 订单页大批量加载性能优化（2026-04-16）
- `backend/app/api/data.py` 的 `GET /api/data/orders` 新增 `shop_id` 过滤参数；订单列表查询改为严格按当前页返回，并仅对当前页订单补查 `item_count` / `has_detail`，避免大批量订单下前端一次加载 5000 条和后端批量补查明细状态
- `backend/app/models/order.py` 与 `backend/alembic/versions/20260416_1700_add_order_page_indexes.py` 为 `order_header` 补充 `shop_id + purchase_date`、`order_status + purchase_date` 索引，优化订单页按店铺/状态倒序浏览
- `frontend/src/views/data/DataOrdersView.vue` 改为服务端分页：页码、页大小、筛选、排序均回传 `/api/data/orders`；SKU 输入改为短防抖搜索；店铺筛选选项改为独立调用 `listDataShops()`，不再从当前页订单数据推导
- **测试**：新增 `backend/tests/unit/test_data_orders_api.py` 与 `frontend/src/views/__tests__/DataOrdersView.test.ts`，覆盖 `shop_id` 过滤、空页短路、服务端分页、页码切换、店铺筛选与 SKU 防抖搜索

### 3.46 Review 风险修复：部署链路、前端容错与限流边界（2026-04-17）
- `.github/workflows/ci.yml` 为 `v*` tag 补充 CI + GHCR 发布触发，`publish` 统一覆盖 `main` / `master` / tag；`.github/workflows/deploy.yml` 与 `deploy/scripts/deploy.sh` 同步收敛为按真实 commit SHA 派生 `IMAGE_TAG=sha-<commit>`，并兼容 branch / tag / detached SHA 部署，修复 `main` 分支和 tag 发布容易拉不到镜像的问题
- `deploy/Caddyfile` 的生产 CSP 将 `img-src` 放行到 `https://m.media-amazon.com`，与赛狐同步的 Amazon 商品主图来源保持一致，避免订单/商品页缩略图被浏览器策略拦截
- `frontend/src/config/appPages.ts` 新增统一页面定义，`frontend/src/router/index.ts` 与 `frontend/src/config/navigation.ts` 改为共同消费同一份路由/菜单元数据，减少页面 path / title / permission 双份维护
- `frontend/src/utils/storage.ts` 新增安全读取工具；`frontend/src/stores/auth.ts`、`frontend/src/stores/sidebar.ts` 在 localStorage JSON 损坏或结构异常时自动清理脏数据并回退默认值，避免 SPA 启动阶段因 `JSON.parse` 直接崩溃
- `backend/app/tasks/access.py` 收敛 TaskRun 作业白名单与查看/操作权限映射，`backend/app/api/task.py` 改为复用统一注册表；旧赛狐写入作业仅允许通过专用业务入口触发
- `backend/app/core/rate_limit.py` 为进程内限流补充周期性全局过期清理、`max_tracked_clients` 容量上限和最旧客户端驱逐逻辑，降低不同 IP 扫描导致的内存持续膨胀风险
- **测试**：新增 `backend/tests/unit/test_rate_limit_middleware.py`、`frontend/src/stores/__tests__/sidebar.test.ts`，并扩展 `frontend/src/stores/__tests__/auth.test.ts`

### 3.47 剩余大数据页服务端分页迁移（2026-04-17）
- `backend/app/api/suggestion.py` 的 `GET /api/suggestions` 返回补齐 `page` / `page_size`，历史记录页直接消费后端当前页结果，不再在前端对 5000 条建议单做本地筛选分页
- `backend/app/api/data.py` 复用库存筛选逻辑，并新增 `GET /api/data/inventory/warehouse-groups`，按仓库维度返回分页分组、SKU 数、可用/占用库存合计与当前页明细，库存页在保持“按仓库展开”交互的同时避免一次性加载全部库存
- `backend/app/api/data.py` 新增 `GET /api/data/out-record-types`，出库记录页的类型筛选选项改为独立读取；`DataOutRecordsView.vue` 改为将 SKU、仓库单号、国家、类型、在途状态、排序、分页全部下推到 `/api/data/out-records`
- `frontend/src/views/data/DataProductsView.vue`、`DataInventoryView.vue`、`DataOutRecordsView.vue` 与 `frontend/src/views/HistoryView.vue` 均改为后端分页模式：`rows` 仅保存当前页，`total` 来自接口，筛选变化重置第一页，页码/页大小变化触发重新请求
- **测试**：新增 `backend/tests/unit/test_data_inventory_groups_api.py`、`backend/tests/unit/test_suggestion_list_api.py`、`frontend/src/views/__tests__/DataProductsView.test.ts`、`frontend/src/views/__tests__/DataInventoryView.test.ts`，并更新历史记录与出库记录页测试覆盖服务端分页参数

### 3.48 GHCR owner 小写归一化修复（2026-04-17）
- `.github/workflows/ci.yml` 的 `publish` job 新增 owner 归一化步骤，统一使用小写 owner 生成 `ghcr.io/<owner>/restock-{backend,frontend}:sha-<commit>` 与 `latest` 标签，修复 GitHub 用户名包含大写字符时 buildx 直接报 `repository name must be lowercase`
- `deploy/scripts/validate_env.sh` 将 `GHCR_OWNER` 纳入必填校验，并显式拒绝非小写值；`deploy/scripts/deploy.sh` 在调用 Compose 前再次导出小写 `GHCR_OWNER`，避免线上 `.env` 沿用旧值导致拉镜像失败
- `deploy/.env.example` 与 `docs/deployment.md` 同步明确 `GHCR_OWNER` 必须使用全小写 GitHub 用户名/组织名
- `.github/workflows/deploy.yml` 的 `check-ci` job 补充 `contents: read`，修复手动触发部署时 `actions/checkout` 因权限不足报 `repository not found` 的阻塞问题

### 3.43 CI 安全校验修复：JWT 密钥长度 + 前端依赖审计（2026-04-15）
- `backend/app/config.py` 将默认 `jwt_secret` 占位值提升到 32 字节以上，并在 `validate_settings()` 中新增 `JWT_SECRET must be at least 32 bytes` 校验；生产环境占位值检测同步更新，避免 `PyJWT` 因 HMAC 密钥过短抛出 `InsecureKeyLengthWarning`，导致 `tests/unit/test_security.py` 在 CI 中失败
- `frontend/package.json`、`frontend/package-lock.json` 升级 `axios` 至 `1.15.0`、`vitest` / `@vitest/coverage-v8` 至 `4.1.4`，并通过同一依赖树消除 GitHub Actions 中 `npm audit --audit-level=high` 的高危告警
- **验证**：`backend/tests/unit/test_security.py` 10 项单测已通过；前端在 Docker `node:20-alpine` 环境完成 `npm run build`、`npm run test:coverage`、`npm audit --audit-level=high`，结果为 `found 0 vulnerabilities`

### 3.42 前端 CI 等价校验改为 Node 20 容器链路（2026-04-15）

- 新增 `scripts/frontend-check.ps1` 与 `scripts/frontend-check.sh`，统一使用 Docker `node:20-alpine` 执行 `npm ci && npm run build && npm run test:coverage`
- 前端依赖安装写入 Docker volume（`restock-frontend-check-node-modules`、`restock-frontend-check-npm-cache`），避免污染宿主机 `frontend/node_modules`
- `scripts/check.ps1` 与 `scripts/check.sh` 的前端部分改为默认调用上述容器脚本；后端校验仍保持宿主机 Python 原生执行
- `docs/onboarding.md` 同步区分“本机开发通道”和“CI 等价校验通道”，明确本机 Node 可继续用于 `npm run dev`，但关键校验不再依赖宿主机版本
- **验证**：Node 20 容器内前端 `build` 与 `test:coverage` 已通过，消除 Windows + 非 CI Node 版本导致的本地噪音失败

### 3.41 后端镜像依赖路径修复 + 本地 dev 全栈容器验证（2026-04-15）

- `backend/Dockerfile` 运行阶段补充 `PYTHONPATH=/app:/install/lib/python3.11/site-packages`，修复使用 `pip install --prefix=/install` 后 `uvicorn`、`alembic` 启动脚本可执行但模块无法 import 的问题
- `deploy/docker-compose.dev.yml` 新增独立的本地 dev 全栈 6 服务编排：db 暴露 `5433`、Caddy 暴露 `8088`，数据目录使用 `deploy/data/pg-dev` 与 `deploy/data/caddy-dev`
- `deploy/docker-compose.dev.yml` 与 `deploy/docker-compose.yml` 为全部服务增加固定 `container_name`，本地容器统一为 `restock-dev-*`，生产容器统一为 `restock-*`
- `deploy/Caddyfile.dev` 新增本地 HTTP 反代入口，统一代理 `/api/*`、`/docs*`、`/openapi.json`、`/healthz`、`/readyz` 和前端静态页面
- `backend/alembic/versions/20260410_1300_extend_zipcode_rule_operator.py` 与 `backend/alembic/versions/20260411_1500_zipcode_rule_between_operator.py` 兼容删除历史命名约定叠加产生的 `ck_zipcode_rule_ck_zipcode_rule_operator_enum`，修复全新数据库从零迁移失败
- `deploy/docker-compose.yml` 与 `deploy/docker-compose.dev.yml` 将前端健康检查改为 `127.0.0.1:8080`，修复 Alpine `wget` 对 `localhost` 走 IPv6 时的假失败
- `deploy/.env.dev.example`、`docs/deployment.md`、`docs/onboarding.md` 同步补充本地 dev 全栈启动说明，保持生产部署入口与本地验证入口分离
- **验证**：已完成 Compose 构建、后端镜像依赖导入校验、本地全栈迁移与健康检查链路验证

### 3.40 项目审查修复（2026-04-15）

批量修复审查发现的 40 项问题，涵盖 5 个批次：
- **阻塞级**：通用 500 处理器（防堆栈泄露）、shutdown 资源释放（DB 引擎 + SaihuClient）、ORM 唯一约束对齐、部署脚本修复（rollback detached HEAD、restore_db 清库）
- **性能**：GET 端点只读会话（`db_session_readonly`）、Element Plus unplugin 基础设施、登录页 DOM 精简（2800→1200）、hasChanges 结构化比较、同步任务每 500 条周期性 commit、库存快照 90 天保留策略
- **安全**：trusted proxy 验证（rate_limit + auth）、前端容器非 root（nginx 8080）、Caddyfile 健康端点内网限制 + 请求体限制
- **健壮性**：InTransitRecord FK ondelete=SET NULL、迁移脚本文件锁
- **代码质量**：`_mapUserInfo` 运行时类型校验、AppLayout 移除 `as any`、engine API 类型化封装、401 延迟 import 避免循环依赖、Vitest 覆盖率阈值、Python 依赖 lockfile
- **部署**：容器日志轮转、CPU 限制、滚动重启、PostgreSQL 调优（-c 参数）、前端 healthcheck、备份验证
- **CI/CD**：部署工作流 CI 门控 + 并发控制 + 通知、Docker 镜像构建测试
- **监控**：`GET /api/metrics/prometheus` 基础指标端点（队列深度 + 存活），需要登录且具备 `monitor:view`；Caddy 仅对内网来源放行

### 3.38 信息总览快照缓存与 SKU+国家风险口径统一（2026-04-14）
- `backend/app/models/dashboard_snapshot.py` 与 `backend/alembic/versions/20260414_2300_add_dashboard_snapshot.py` 新增 `dashboard_snapshot` 单例缓存表，存储信息总览 payload、刷新状态、开始/完成时间和最近一次错误
- `backend/app/tasks/jobs/dashboard_snapshot.py` 新增 `refresh_dashboard_snapshot` 任务；`backend/app/api/task.py`、`backend/app/main.py` 完成任务注册，信息总览快照改由后台任务生成并写回缓存
- `backend/app/api/metrics.py` 新增 `build_dashboard_payload()`，把首行风险卡片、左侧“各国缺货风险分布”和“急需补货SKU”统一为 SKU+国家口径的实时计算结果；`GET /api/metrics/dashboard` 改为优先返回缓存快照与当前任务状态，缺少缓存时返回 `missing`，由 `POST /api/metrics/dashboard/refresh` 手动入队刷新
- `frontend/src/api/dashboard.ts`、`frontend/src/views/WorkspaceView.vue` 接入快照状态字段、刷新按钮和 `TaskProgress` 轮询；首行卡片文案同步改为“紧急国家商品 / 临近补货国家商品 / 安全国家商品 / 覆盖国家”，右侧“补货量国家分布”继续保持基于当前建议补货单
- **测试**：新增 `backend/tests/unit/test_metrics_snapshot_api.py`、`backend/tests/unit/test_dashboard_snapshot_job.py`，并更新 `backend/tests/unit/test_metrics_dashboard.py`、`frontend/src/views/__tests__/WorkspaceView.test.ts`，覆盖快照回读、无缓存自动入队、任务写回和前端刷新交互
- **经验沉淀**：信息总览这类高聚合页面应优先消费快照，以换取稳定口径、可追踪刷新链路和更低的重复计算成本

### 3.39 信息总览首行卡片切换为补货视角（2026-04-14）
- `backend/app/api/metrics.py` 在 `DashboardOverviewPayload` 中新增 `restock_sku_count`、`no_restock_sku_count`，并在 `build_dashboard_payload()` 中直接复用 `step3_country_qty + step4_total` 的现行规则统计“需补货SKU / 无需补货SKU”；当 `GET /api/metrics/dashboard` 读取到缺少新字段的旧 `dashboard_snapshot.payload` 时，接口保留默认值并返回 `missing`，由手动刷新任务修复快照
- `frontend/src/api/dashboard.ts`、`frontend/src/views/WorkspaceView.vue` 将首行卡片改为“需补货SKU / 无需补货SKU / 覆盖国家”，并移除旧的风险说明文案；下方“各国缺货风险分布”“急需补货SKU”“补货量国家分布”保持原有展示逻辑不变
- **测试**：更新 `backend/tests/unit/test_metrics_dashboard.py`、`backend/tests/unit/test_metrics_snapshot_api.py` 与 `frontend/src/views/__tests__/WorkspaceView.test.ts`，覆盖新字段返回、旧快照兼容刷新和新卡片文案渲染

### 2.6 数据管理

- **仓库国家变更级联**：修改 `warehouse.country` 时同步更新 `inventory_snapshot_latest` 对应记录，无需等下次同步
- **仓库国家支持清除**：下拉框加 `clearable`，后端 schema 支持 `null`
- **数据页 page_size 上限放宽**：所有 `/api/data/*` 端点的 `le=5000`（原 200），支持一次拉全量
- **建议单列表 page_size 上限**：`/api/suggestions` 的 `le=5000`
- **筛选项统一**：店铺/仓库/订单/库存/出库/补货发起 7 个页面的筛选项布局和高度一致
- **出库页**：原“其他出库（在途观测）”改名为“出库”；主表展示出库单id、出库仓库id、目标国家、更新时间、同步时间、出库单类型、状态，明细按“商品SKU、商品ID、可用数、采购单价”顺序展示；同步时间复用 `lastSeenAt`，状态统一按 `is_in_transit` 映射为“在途 / 完结”，并支持按“出库单类型”单选筛选
- **在途国家识别**：`sync_out_records` 不再使用 `targetFbaWarehouseId -> warehouse.country` 反推国家，而是从备注文本提取国家名（如 `20260410美国-赢捷-加州-散货-在途中` → `US`）；无法识别时保持空值
- **出库目标国家回填**：`sync_out_records` 在正常同步赛狐出库记录后，会顺带扫描历史 `target_country` 为空且备注可识别国家的出库记录，按备注规则补回目标国家，不覆盖已有值

### 2.7 任务队列系统

- **`task_run` 表**：dedupe_key 去重（partial unique index）、priority 调度、lease 心跳
- **Worker** 2 秒轮询 + 30 秒心跳 + 2 分钟租约
- **Reaper** 60 秒扫描过期任务
- **任务进度实时写入**：`current_step` / `step_detail` / `total_steps`，前端 `TaskProgress` 轮询展示；订单详情任务按条数精确展示，店铺/仓库/商品/库存/订单/出库等分页同步任务按赛狐返回 `totalPage` 展示页级百分比，不额外增加预扫描请求
- **SKIPPED 状态**：调度器尝试重复入队活跃任务时创建审计记录

### 2.8 认证与安全

- **JWT HS256**：24 小时有效，单用户 `sub="owner"`
- **登录锁定按 IP 隔离**：从全局共享改为来源 IP 粒度，优先读 `X-Forwarded-For`/`X-Real-IP`
- **新增表**：`login_attempt`（迁移 `20260409_1710_add_login_attempt.py`）
- **API 调用日志**：每次赛狐调用都写 `api_call_log`
- **角色配置页**：`RoleConfigView.vue` — 角色 CRUD + 权限矩阵编辑（按 `group_name` 分组，支持全选/反选），超管角色权限只读展示

---

## 3. 近期重大变更（2026-04-10 ~ 2026-04-28）
### 3.37 急需补货SKU过滤缺失可售天数并统一 `<1天` 展示（2026-04-14）
- `backend/app/engine/step6_timing.py` 将缺失或无效的 `sale_days` 从 urgent 判定中排除，仅对存在且可解析的国家级 `sale_days` 执行 `<= lead_time_days` 判断
- `backend/app/api/metrics.py` 调整 dashboard 的 `top_urgent_skus` 过滤逻辑，缺失 `sale_days` 的国家不再进入“急需补货SKU”列表
- `frontend/src/views/WorkspaceView.vue` 将信息总览中的国家级可售天数展示改为：缺失显示 `-`，小于 1 天统一显示 `<1天`
- **测试**：更新 `backend/tests/unit/test_engine_step6.py`、`backend/tests/unit/test_suggestion_patch.py`、`backend/tests/unit/test_metrics_dashboard.py` 与 `frontend/src/views/__tests__/WorkspaceView.test.ts`，覆盖缺失值忽略、patch 重算和 `<1天` 展示

### 3.36 信息总览急需补货SKU按国家拆行（2026-04-14）
- `backend/app/api/metrics.py` 将 `top_urgent_skus` 从“每个 urgent SKU 一行”改为“每个 urgent SKU 的每个急需国家一行”，返回字段调整为 `commodity_sku / commodity_name / main_image / country / sale_days`
- `frontend/src/views/WorkspaceView.vue` 将“急需补货SKU”列表表头改为“商品信息 / 国家 / 可售天数”，同一 SKU 可出现多行；可售天数直接展示对应国家的 `sale_days`
- **测试**：更新 `backend/tests/unit/test_metrics_dashboard.py` 与 `frontend/src/views/__tests__/WorkspaceView.test.ts`，覆盖多国家拆行、国家级可售天数和前端列表渲染

### 3.35 出库目标国家历史回填并入同步流程（2026-04-14）
- `backend/app/sync/out_records.py` 将历史 `target_country` 空值回填并入 `sync_out_records` 主流程；每次同步完赛狐出库记录后，都会复用同一套备注解析逻辑补齐历史空值行，但不覆盖已有目标国家
- `backend/app/api/sync.py`、`backend/app/api/task.py` 与 `frontend/src/config/sync.ts` 清理独立的“回填出库目标国家”任务入口，前端仍只保留“出库记录同步”按钮
- **测试**：更新 `backend/tests/unit/test_sync_out_records_job.py` 与 `backend/tests/unit/test_scheduler_api.py`，覆盖回填 helper 和主同步流程内执行回填的行为

### 3.34 出库页补充目标国家列与类型单选筛选（2026-04-14）
- `backend/app/api/data.py` 为 `GET /api/data/out-records` 新增 `type_name` 查询参数，允许按出库单类型精确筛选；`backend/tests/unit/test_data_out_records_api.py` 补充对应参数签名与过滤口径断言
- `frontend/src/api/data.ts`、`frontend/src/views/data/DataOutRecordsView.vue` 在现有风格下新增“出库单类型”单选筛选，主表列顺序调整为“出库单ID / 出库仓库ID / 目标国家 / 更新时间 / 同步时间 / 出库单类型 / 状态”，其中“目标国家”直接展示已有 `targetCountry`
- **测试**：更新 `frontend/src/views/__tests__/DataOutRecordsView.test.ts`，覆盖目标国家列渲染、出库单类型筛选选择/清空，以及新的列顺序

### 3.33 废弃采购日期字段兼容层清理（2026-04-14）
- `backend/app/engine/runner.py` 移除为旧库保留的 `suggestion_item.t_purchase` / `push_attempt_count` 等动态补默认与运行时表结构探测，建议单条目改为直接按当前 ORM schema 写入；运行引擎前需要确保环境已执行 `alembic upgrade head`
- `backend/tests/unit/test_engine_runner.py` 删除围绕旧表结构兼容写入的回归测试，仅保留当前 schema 行为与 `restock_regions` 透传校验

### 3.32 采购日期移除与紧急规则、在途国家口径调整（2026-04-14）
- `backend/app/engine/step6_timing.py` 移除采购日期计算，`urgent` 统一改为“任一正补货国家的 `sale_days <= lead_time_days`”；`backend/app/engine/runner.py` 不再写入 `suggestion_item.t_purchase`，并新增 `target_days >= lead_time_days` 的运行期保护
- `backend/app/api/suggestion.py`、`backend/app/models/suggestion.py`、`backend/app/schemas/suggestion.py` 与 `frontend/src/views/SuggestionDetailView.vue`、`frontend/src/api/suggestion.ts` 一并移除采购日期字段的存储、接口和前端编辑展示；新增迁移 `backend/alembic/versions/20260414_2100_drop_suggestion_item_t_purchase.py`
- `backend/app/schemas/config.py`、`backend/app/api/config.py` 与 `frontend/src/views/GlobalConfigView.vue` 增加“目标库存天数不能小于采购提前期”的前后端双重校验
- `backend/app/sync/out_records.py` 将在途记录国家改为从备注提取，解析失败时不再回退到仓库国家；补充对应单元测试
- **测试**：新增/更新 `backend/tests/unit/test_engine_step6.py`、`backend/tests/unit/test_suggestion_patch.py`、`backend/tests/unit/test_sync_out_records_job.py`、`backend/tests/unit/test_config_schema.py`、`backend/tests/integration/test_config_api.py`、`frontend/src/views/__tests__/GlobalConfigView.test.ts`、`frontend/src/views/__tests__/SuggestionDetailView.test.ts`、`frontend/src/views/__tests__/SuggestionListView.test.ts`

### 3.31 信息总览图例换行与风险图显示修复（2026-04-13）
- `frontend/src/components/dashboard/DashboardChartCard.vue` 将图表撑满高度的样式约束收敛到“存在 footer 的卡片”场景，避免普通图表卡片被错误压缩，恢复“各国缺货风险分布”正常显示
- `frontend/src/views/WorkspaceView.vue` 将“补货量国家分布”底部图例改为固定四列居中布局，按每行 4 个国家换行；窄屏下按现有响应式规则降为 3 列 / 2 列，保持整体居中
- **测试**：更新 `frontend/src/views/__tests__/WorkspaceView.test.ts`，覆盖国家图例四列居中布局以及 `DashboardChartCard` 的 footer 专用高度约束

### 3.30 信息总览国家分布图例布局优化（2026-04-13）
- `frontend/src/components/dashboard/DashboardChartCard.vue` 支持图表区下方附加自定义 footer 区域；当存在 footer 时，卡片内容按约 2:1 的纵向比例分配给图表和底部补充信息区
- `frontend/src/views/WorkspaceView.vue` 将“补货量国家分布”从 ECharts 内置 legend 调整为卡片底部自定义图例，环形图稳定展示在上部约 2/3 区域，底部图例位于下部约 1/3 区域并支持自动换行
- **测试**：更新 `frontend/src/views/__tests__/WorkspaceView.test.ts`，覆盖国家分布图关闭内置 legend、渲染底部自定义图例和相关布局约束

### 3.29 信息总览安全 SKU 口径与列表布局优化（2026-04-13）
- `backend/app/api/metrics.py` 调整 dashboard overview 首行风险卡片口径：`urgent_count`、`warning_count`、`safe_count` 改为基于全部启用 SKU 的最小可售天数统计，其中 `< lead_time_days` 记为“紧急”，`>= lead_time_days 且 < target_days` 记为“临近补货”，`>= target_days` 记为“安全”；下方“各国缺货风险分布”“补货量国家分布”仍保持基于当前最新 `draft/partial` 建议单
- `frontend/src/views/WorkspaceView.vue` 同步更新首行卡片提示文案，明确说明风险卡片统计对象为“全部启用 SKU”；同时移除“急需补货 SKU”卡片的固定高度，改为与右侧“补货概览”卡片等高拉伸，滚动区域占满可用内容区
- **测试**：更新 `backend/tests/unit/test_metrics_dashboard.py` 与 `frontend/src/views/__tests__/WorkspaceView.test.ts`，覆盖全部启用 SKU 风险分桶口径和急需列表拉伸布局

### 3.28 建议单商品ID自动补齐与推送状态口径修复（2026-04-13）
- `backend/app/core/commodity_id.py` 新增 SKU -> `commodity_id` 解析与建议条目推送可用性修复逻辑，按 `commodity_sku` / `seller_sku` 分层回退匹配；`backend/app/engine/runner.py` 复用该解析逻辑，生成建议单时尽量直接补齐 `commodity_id`
- `backend/app/api/suggestion.py` 在读取当前建议单/建议单详情以及手动推送前，自动为缺少 `commodity_id` 的条目重新解析并修复 `push_blocker`、`push_status`；已能补齐商品ID的旧条目刷新后会恢复为可推送
- `frontend/src/views/SuggestionListView.vue` 恢复推送状态真实语义：仅真正可推送条目显示为“待推送”并允许勾选，`blocked` 改为“待处理”独立筛选；`frontend/src/utils/status.ts` 同步状态标签文案
- **测试**：新增 `backend/tests/unit/test_commodity_id.py`，并更新 `backend/tests/unit/test_engine_runner.py`、`backend/tests/unit/test_suggestion_patch.py`、`frontend/src/views/__tests__/SuggestionListView.test.ts`、`frontend/src/utils/status.test.ts`

### 3.27 补货发起页推送标签口径收敛（2026-04-13）
- `frontend/src/views/SuggestionListView.vue` 移除商品信息卡片后的推送阻塞标签展示，并将 `blocked` 条目在前端筛选与排序口径中并入“待推送”
- `frontend/src/utils/status.ts` 将建议条目 `push_status='blocked'` 的展示文案统一为“待推送”，不再向用户暴露“不可推送”标签
- **测试**：新增 `frontend/src/views/__tests__/SuggestionListView.test.ts`，并更新 `frontend/src/utils/status.test.ts`，覆盖 blocked 并入待推送和商品信息区不再传递 blocker 标签

### 3.26 出库页筛选默认值与清空交互修正（2026-04-13）
- `frontend/src/views/data/DataOutRecordsView.vue` 将“状态”筛选默认值从“在途”改为“未筛选”，并为“状态”“国家”两个下拉补齐清空后立即重载列表的交互
- `backend/app/api/data.py` 将 `GET /api/data/out-records` 的 `is_in_transit` 查询参数默认值改为 `None`，使未传参时返回全部出库记录而不是仅返回在途记录
- **测试**：更新 `frontend/src/views/__tests__/DataOutRecordsView.test.ts` 与 `backend/tests/unit/test_data_out_records_api.py`，覆盖默认无状态筛选、状态清空和国家清空场景

### 3.25 历史记录删除与触发方式中文化（2026-04-13）
- `backend/app/api/suggestion.py` 新增 `DELETE /api/suggestions/{id}`，按建议单维度物理删除 `suggestion` 及级联明细；仅 `draft` / `partial` / `error` / `archived` 允许删除，`pushed` 返回冲突错误
- `frontend/src/api/suggestion.ts` 新增 `deleteSuggestion()`；`frontend/src/views/HistoryView.vue` 将筛选顺序调整为“SKU关键字 → 日期筛选 → 状态筛选”，操作列新增红色“删除”，确认框使用项目现有 MessageBox 风格并补充危险操作文案
- 历史记录页“触发方式”改为中文展示：`manual` 显示“手动触发”，`scheduler` 显示“自动触发”，未知值兜底显示原始文本
- **测试**：新增 `frontend/src/views/__tests__/HistoryView.test.ts`，并扩展 `backend/tests/unit/test_suggestion_patch.py` 覆盖删除接口允许/拒绝场景

### 3.24 同步时间展示统一（2026-04-13）
- `frontend/src/utils/format.ts` 将 `formatUpdateTime` 统一为 `YYYY-MM-DD HH:mm`，用于数据页“同步时间”和出库页“更新时间/同步时间”展示；对应 `frontend/src/utils/format.test.ts` 同步更新断言
- `frontend/src/views/data/DataProductsView.vue`、`DataShopsView.vue`、`DataWarehousesView.vue`、`DataInventoryView.vue` 将列表列名从“更新时间”统一调整为“同步时间”，保持原有页面结构和视觉样式不变
- `frontend/src/views/data/DataOutRecordsView.vue` 保留主表“更新时间”，新增基于 `lastSeenAt` 的“同步时间”列，并重新分配主表列宽，使长字段更宽、短字段更紧凑
- **测试**：更新 `frontend/src/views/__tests__/DataTimeLabels.test.ts` 与 `frontend/src/views/__tests__/DataOutRecordsView.test.ts`，覆盖统一命名和出库记录双时间列渲染

### 3.23 信息总览图表与风险卡片口径调整（2026-04-13）
- `backend/app/api/metrics.py` 为 dashboard overview 新增 `warning_count`、`safe_count`、`risk_country_count` 和 `country_restock_distribution`，其中右侧“补货量国家分布”改为汇总当前最新 `draft/partial` 建议单全部条目的 `country_breakdown`
- `frontend/src/api/dashboard.ts` 同步扩展 `DashboardOverview` 类型；`frontend/src/views/WorkspaceView.vue` 将首行卡片改为“紧急 SKU / 临近补货 / 安全 SKU / 覆盖国家”，左侧风险图从堆叠柱状图调整为分组柱状图
- 右侧“补货量国家分布”继续保留饼图样式，但数据源不再限制为前 10 个紧急 SKU，因此当前建议单中存在补货量的国家都会参与展示
- **测试**：更新 `backend/tests/unit/test_metrics_dashboard.py` 与 `frontend/src/views/__tests__/WorkspaceView.test.ts`，覆盖新增汇总字段、当前建议单国家补货量分布和前端图表/卡片渲染

### 3.22 信息总览改为各国缺货风险分布（2026-04-13）
- `backend/app/api/metrics.py` 将 dashboard overview 从“各国平均可售天数”调整为“各国缺货风险分布”，按当前最新 `draft/partial` 建议单的 `sale_days_snapshot` 基于全局 `lead_time_days`、`target_days` 分桶，返回各国 `urgent_count` / `warning_count` / `safe_count`
- `frontend/src/api/dashboard.ts` 同步更新 `DashboardOverview` 类型，新增 `lead_time_days` 和 `country_risk_distribution`，移除旧的 `country_stock_days` 口径
- `frontend/src/views/WorkspaceView.vue` 左侧图表替换为风险分布图，tooltip 明确展示“紧急 / 临近补货 / 安全”数量及全局阈值；右侧“补货量国家分布”饼图继续保留
- **测试**：新增 `backend/tests/unit/test_metrics_dashboard.py` 与 `frontend/src/views/__tests__/WorkspaceView.test.ts`，覆盖风险分桶、dashboard 返回结构和前端图表渲染

### 3.21 补货区域接入全局参数与引擎过滤（2026-04-13）
- `backend/app/models/global_config.py`、`backend/alembic/versions/20260414_1500_add_restock_regions_to_global_config.py` 为 `global_config` 新增 `restock_regions` JSONB 字段，默认值为 `[]`；`backend/app/main.py` 启动初始化时同步补齐默认配置
- `backend/app/core/restock_regions.py` 统一处理补货区域的规范化与可用国家集合解析；`backend/app/schemas/config.py` 复用该逻辑，对输入执行去空、去重、转大写和 2 位国家码校验
- `backend/app/engine/runner.py` 在生成建议前解析 `restock_regions`，并把允许国家集合传入 `step1_velocity` 与 `step5_warehouse_split`；`restock_regions=[]` 明确表示“全部国家参与计算”
- `backend/app/engine/runner.py` 写入的 `global_config_snapshot` 新增 `restock_regions`；历史建议不回填，仅后续新生成建议携带该快照
- `frontend/src/views/GlobalConfigView.vue` 保持原有 `PageSectionCard + el-form` 风格，在全局参数页新增“补货区域”多选控件；保存 payload、未保存变更检测和“建议重新生成补货建议单”提示均已覆盖该字段
- **测试**：新增/更新 `backend/tests/unit/test_config_schema.py`、`backend/tests/unit/test_engine_step1.py`、`backend/tests/unit/test_engine_step5.py`、`backend/tests/unit/test_engine_runner.py`、`backend/tests/integration/test_config_api.py`、`frontend/src/views/__tests__/GlobalConfigView.test.ts`，覆盖参数校验、SQL 过滤、引擎透传与前端交互

### 3.20 同步任务进度可观测增强（2026-04-13）
- `backend/app/sync/order_detail.py` 将 `sync_order_detail` / `refetch_order_detail` 的进度文案统一为“已完成 X / 失败 Y / 总数 N”，按当前目标集合精确回写，不增加额外赛狐请求
- `backend/app/saihu/endpoints/shop.py`、`warehouse.py`、`product_listing.py`、`inventory.py`、`order_list.py`、`out_records.py` 为分页迭代器补充页元信息回调；对应 `sync_*` 任务在不额外预扫的前提下，直接复用赛狐返回的 `totalPage` 输出“第 P / N 页”进度
- `frontend/src/components/TaskProgress.vue` 新增对“按条数”和“按页数/步骤”两类进度文案的解析，可在已有任务轮询接口上直接展示确定型百分比，无法解析时仍回退为不确定进度条
- **测试**：补充 `backend/tests/unit/test_sync_order_detail_job.py`、`backend/tests/unit/test_sync_product_listing_job.py`、`backend/tests/unit/test_sync_order_list.py` 与 `frontend/src/components/TaskProgress.test.ts`，覆盖精确进度、分页进度与前端回退逻辑

### 3.19 出库记录字段补齐（2026-04-13）
- `backend/app/sync/out_records.py` 在同步赛狐其他出库记录时，额外落库 `warehouseId`、`updateTime`、`type`、`typeName`，并为明细落库 `commodityId`、`perPurchase`
- `backend/alembic/versions/20260414_1300_extend_in_transit_out_record_fields.py` 为 `in_transit_record` / `in_transit_item` 补齐上述展示字段，支撑数据页直接展示源字段含义
- `backend/app/api/data.py`、`backend/app/schemas/data.py` 与 `frontend/src/api/data.ts` 补齐对应 DTO；出库记录列表默认按 `updateTime desc` 返回，并支持按出库仓库id、更新时间、出库单类型排序
- `frontend/src/views/data/DataOutRecordsView.vue` 将页面标题改为“出库”，主表和明细表按最新业务口径展示字段，状态标签统一为“在途 / 完结”
- **测试**：补充 `backend/tests/unit/test_sync_out_records_job.py`、`backend/tests/unit/test_data_out_records_api.py` 与 `frontend/src/views/__tests__/DataOutRecordsView.test.ts`，覆盖同步落库、列表排序和页面默认请求/字段渲染

### 3.18 订单详情条件批量获取（2026-04-13）

- `backend/app/api/sync.py` 的 `POST /api/sync/order-detail/refetch` 改为订单详情抓取统一入口：若存在活跃的 `refetch_order_detail`、`sync_order_detail` 或 `sync_all`，则直接返回现有任务供前端复用进度；否则再按回溯天数筛选“订单主表已存在但本地缺少详情”的全部订单并创建后台任务，不再做 500 条截断
- `backend/app/sync/order_detail.py` 的 `refetch_order_detail` 继续绕过 `order_detail_fetch_log` 的已记录过滤，直接消费接口层筛出的订单集合，但仍复用现有详情抓取、失败分类、限流与落库逻辑
- `frontend/src/components/sync/OrderDetailFetchAction.vue` 将订单页入口封装为右侧独立“详情获取”组件；`frontend/src/views/data/DataOrdersView.vue` 只负责承接任务进度和列表刷新
- **测试**：补充 `backend/tests/unit/test_scheduler_api.py`、`frontend/src/components/sync/OrderDetailFetchAction.test.ts` 与 `frontend/src/api/__tests__/sync.test.ts`，覆盖活跃任务复用、详情获取入口提示、手工触发 payload、空命中不建任务与取消手动数量上限后的全量入队

### 3.17 监控名称中文化（2026-04-13）
- `frontend/src/utils/monitoring.ts` 新增统一名称映射：赛狐接口 `endpoint`、性能监控 `request/resource` 名称统一转为中文含义，并保留原始路径用于 tooltip 排障
- `frontend/src/views/ApiMonitorView.vue` 与 `frontend/src/components/sync/FailedApiCallTable.vue` 改为在“接口监控”和“同步日志”中主显示中文接口名称，图表 tooltip 同步展示中文名和原始接口
- `frontend/src/views/PerformanceMonitorView.vue` 改为将“请求名称”“资源名称”按内部接口、页面导航、Vite 资源、静态资源分组中文化展示，同时保持按原始路径聚合，避免不同资源因中文重名被错误合并

### 3.16 全链路 Review 修复收尾（2026-04-13）
- `backend/app/sync/product_listing.py` 改为拉取全量 listing（不再强制 `match=true` + `onlineStatus=active`）；本地 `product_listing` 允许保存未匹配行，并用 `is_matched` 标识；引擎读取 `commodity_id` 时继续只消费 active + matched 的行
- `backend/app/sync/product_listing.py` 在商品同步落库后会自动补齐缺失的 `sku_config` 行；商品页可看到全部 SKU，但仅 `is_matched=true && online_status=active` 的 SKU 会被自动置为 `enabled=true` 进入引擎，其余 SKU 默认创建为禁用态
- `frontend/src/views/data/DataProductsView.vue` 改为通过统一状态映射判断 listing `online_status`；商品页现在按大小写无关方式识别 `active`，不会再把后端已标准化为小写的在售商品误显示成“不在售”
- `SuggestionDetailView` 改为支持编辑 `total_qty`、国家补货量、仓库拆分、采购时间；移除发货时间，国家补货量不再要求与总采购量一致，仓内分量仍需对齐国家补货量

### 3.15 全链路 Review 修复（2026-04-12）

审查范围：引擎链路 + 数据同步 + 任务队列 + 推送 + API + 前端 + 部署。28 项发现，16 个 Task 已修复。

**Phase 1 — 数据正确性：**
- P0-1: Step4 国内库存不参与扣减 — 确认 by design，添加业务意图注释
- P0-2: 引擎取整策略统一为 `math.ceil()`（数量）/ `round()`（日期偏移）
- P0-3: `SuggestionItemPatch` 添加 `country_breakdown` / `warehouse_breakdown` 非负校验
- P0-4: 推送失败路径添加 `push_status != 'pushed'` guard 防覆盖
- P1-1: GlobalConfig 加载后添加 `target_days > 0` 等正值校验

**Phase 2 — 健壮性：**
- P1-2: `enqueue_task` 递归重试添加深度限制（max 2）
- P1-3: OrderItem 同步改用 UPSERT + 清理旧 items
- P1-7: `parse_purchase_date` 容错（格式错误视为紧急），API 层保持严格校验
- P1-4/P1-5: 同步 overlap 窗口提取为可配置参数
- P1-6: Token 重试添加 0.3-0.7s 随机 jitter
- P1-8: Reaper 日志标注容器实例 ID

**Phase 3 — 工程质量：**
- P2-1: Step4 invariant 触发时添加结构化日志
- P2-4: 在途 90 天 cutoff 添加业务理由注释
- P2-5: `allocation_mode` 零数量语义从 `"matched"` 改为 `"zero_qty"`
- P2-6: zipcode 数值 `=`/`!=` 比较改用整数避免浮点精度
- P2-7: 推送过滤 `total_qty=0` 条目
- P2-8: `api_call_log` 写入失败添加结构化计数字段
- P3-5: `rate_limit._LIMITERS` 添加有界性说明

测试基线：169 passed（原 163 + 新增 6）

### 3.0c 认证模块云交付就绪修复（2026-04-12，云交付评分卡 M6 阶段）

- `backend/app/api/auth.py` 新增 5 类 structlog 业务事件日志（`auth_login_blocked_locked` / `auth_login_failed` / `auth_login_lockout_triggered` / `auth_login_reset_after_success` / `auth_login_success`），消除"认证模块零业务日志"缺口
- `backend/app/api/auth.py:33-41` `_get_login_source_key` 加代码注释明确对 `deploy/Caddyfile` `header_up X-Forwarded-For {remote_host}` 覆盖行为的依赖关系
- `frontend/src/views/LoginView.vue`：
  - 中文化 "Sign in to Restock" → "登录 Restock"，"Sign in" → "登录"
  - 新增 `startLockedCountdown` / `clearLockedCountdown` 消费后端 `LoginLocked.detail.locked_until`，每秒更新"账号已锁定，剩余 X 分 Y 秒"倒计时
- `docs/runbook.md` 新增第 3.4 节"JWT 密钥管理（首次生成 / 轮换 / 泄漏应急）"，约 100 行 SOP；原 3.5-3.8 顺延到 3.5-3.9
- 评分影响：M6 D5 从 2 升 3；M6 平均分 2.56 → 2.67；P0-5（JWT 轮换文档）从 ❌ 未实现升级为 ✅ 已实现；P1-6（XFF 信任源）降级到 P2（Caddy 架构已缓解）

### 3.0a Reaper 容器拓扑冗余（2026-04-11，云交付评分卡 M4 阶段）

- `deploy/docker-compose.yml` 中 scheduler 服务的 `PROCESS_ENABLE_REAPER` 从 `false` 改为 `true`
- Reaper 现在在 worker 和 scheduler 两个容器**冗余运行**，任一容器存活即可回收僵尸任务
- 双 reaper 通过 PostgreSQL 行锁 + 幂等 UPDATE 天然并发安全
- 背景：M4 审计发现"worker+reaper 共容器、backend 关 reaper"的拓扑下若 worker 容器整体 crash 则无进程回收僵尸任务（P1-M4-3）
- `docs/runbook.md` 3.2 节同步更新：检查两个容器的 reaper 日志 + 追加"强制中断 running 任务"的 fallback 说明（因当前无 cooperative cancel 机制）
- `backend/app/models/task_run.py:89` `attempt_count` 字段追加诊断 tripwire 注释

### 3.0 push 端点状态机封闭性修复（2026-04-11，云交付评分卡 M3 阶段）

- `POST /api/suggestions/{id}/push` 添加状态前置校验：`sug.status not in ("draft","partial")` 时抛 `ConflictError("建议单状态为 X,不可推送")`
- 修复点：`backend/app/api/suggestion.py:274-275`
- 背景：审计中发现 PATCH 端点严格拒绝 archived 而 push 端点不检查的不对称缺陷，可能导致对已归档/已完全推送建议单触发重复采购单
- 新增 2 个单测：`test_suggestion_push_archived_rejected` / `test_suggestion_push_pushed_rejected`，全 backend 156 单测通过
- 评分影响：M3 D6 维持 3，M3 P0-2 候选从"⚠️ 部分实现"升级为"✅ 已实现"

### 3.1 Overstock 特性移除

全栈清理：
- 删除 `frontend/src/views/OverstockView.vue`、导航入口、路由
- 删除 `backend/app/models/overstock.py` 和 `overstock_sku_mark` 表
- 删除 `suggestion_item.overstock_countries` 字段
- 删除 `/api/monitor/overstock` 端点
- 引擎 `step3_country_qty` 不再收集 overstock 数据
- initial migration 同步更新

### 3.2 架构蓝图文档

- 新增 `docs/Project_Architecture_Blueprint.md`（~700 行）
- 包含分层架构图、6 步引擎流水线详解、任务队列机制、赛狐集成模式、ADR 摘要、扩展指南

### 3.3 代码复用重构

- 抽取 `utils/format.ts` 和 `utils/warehouse.ts`，消除 14 处重复定义
- `formatTime` / `clampPage` / `warehouseTypeLabel` / `warehouseTypeTag` 统一实现

### 3.4 并发与性能优化

- **订单详情拉取**：串行改并发（`asyncio.Semaphore(3)` + `asyncio.gather`），充分利用 3 QPS 额度
- **后端端点 page_size**：5 个 data 端点 + suggestions 端点从 `le=200` 放宽到 `le=5000`
- **前端数据页**：改为一次拉取全量，前端本地分页

### 3.5 配置变更影响提示

- **全局参数**保存后：若 `target_days` / `buffer_days` / `lead_time_days` / `restock_regions` 任一变更，前端警告"建议重新生成补货建议单"
- **仓库国家**修改后：前端警告 + 同步更新库存表
- **邮编规则**变更：不加提示（仅影响仓库分配展示，不影响采购量）

### 3.6 UX 改进

- Checkbox 勾选标记改用 SVG background-image 精确居中
- Tooltip 淡出动画 300ms → 100ms，避免快速移动时堆叠
- 筛选项高度统一 32px
- 全选跨页保持 + 推送上限放宽（原 50 条上限已移除）
- 表格排序图标列宽修复

### 3.7 引擎逻辑修复

- **H4 编辑口径修正**：`total_qty` 与 `country_breakdown` 脱钩，国家补货量不再要求与总采购量一致
- **step3**：返回类型从 `tuple[dict, dict]` 简化为 `dict[str, dict[str, int]]`

### 3.8 赛狐订单详情接口特殊限流（历史记录，当前已移除）

- 历史上 `/api/order/detailByOrderId.json` 曾独立配置 QPS 覆盖。
- 当前旧订单详情抓取链路已删除，`saihu/rate_limit.py` 不再保留该 endpoint 特例；遗留日志按默认 1 QPS 口径展示。

### 3.9 zipcode_matcher 鲁棒性

- `_compare` 函数在 `value_type == "number"` 分支中初始化 `compare_values = []`
- 防止 DB 中意外存在 `number+contains` 组合导致的 `UnboundLocalError`

### 3.10 编码问题修复

- `ApiMonitorView.vue` 和 `SuggestionListView.vue` 中的乱码字符串修复
- 全项目 grep 确认 0 残留乱码

### 3.11 筛选体系完善

| 页面 | 新增筛选 |
|---|---|
| 店铺 | 关键字搜索、区域下拉 |
| 仓库 | 关键字搜索、类型下拉 |
| 订单 | 店铺下拉 |
| 库存 / 出库 | 国家文本框 → 下拉 |
| 补货发起 | 推送状态下拉 |

### 3.12 订单详情失败分类修复

`sync_order_detail` 原本把所有 `SaihuAPIError` 子类都当作永久失败写入 `order_detail_fetch_log`，导致限流 / 网络 / auth 过期等瞬时错误在一次重试预算耗尽后被永久拉黑，再也无法补拉。

- **分类器**：新增纯函数 `_is_permanent_saihu_error`，仅 `SaihuBizError` 返回 `True`；`SaihuRateLimited` / `SaihuNetworkError` / `SaihuAuthExpired` / 裸 `SaihuAPIError` 全部视为瞬时，不写日志 → 下一轮调度自动重试
- **`_fetch_one` 改造**：日志事件拆成 `order_detail_fetch_permanent_failure`（含 `saihu_code`）与 `order_detail_fetch_transient_failure` 两条，方便 ops 区分
- **测试**：`backend/tests/unit/test_sync_order_detail_classification.py` 6 个用例锁定分类规则
- **历史清理**：alembic `20260411_1000` 数据迁移一次性删除 `http_status IS NULL AND (saihu_code IS NULL OR saihu_code IN (40001, 40019))` 的误拉黑记录；downgrade 为空
- **部署提示**：执行该 migration 前建议先暂停 APScheduler（`scheduler_enabled=false`），避免 DELETE 与并发 UPSERT 抢锁

### 3.13 邮编规则新增 `between` 区间运算符

- 2026-04-11 — 邮编规则新增 `between` 区间运算符：`compare_value` 支持单段 `"000-270"` 或多段 `"000-270, 500-700"`，一条规则即可表达闭区间，仅 `value_type=number` 允许。后端迁移 `20260411_1500` 将 `zipcode_rule.operator` 由 `String(5)` 扩到 `String(10)`、`compare_value` 由 `String(50)` 扩到 `String(200)`，`operator_enum` CHECK 约束新增 `'between'`。前后端校验对齐（段数 ≤ 20；`hi ≤ 10^prefix_length - 1`）。

### 3.14 邮编规则同优先级 tied 均分

- 2026-04-11 — matcher 由 `match_warehouse(...) -> str | None` 重构为 `match_warehouses(...) -> list[str]`：按 `(priority, rule.id)` 排序后返回"首批同 priority 命中"的仓库列表，同 `warehouse_id` 去重。step5 消费端迭代 winners 按 `qty / N` 累加到 `known_counts`（类型由 `int` 改为 `float`；最终整数输出由下游 `round` + 尾仓兜底保证精确）。业务配置方式：把多条规则的 `priority` 填相同值即可触发均分，对任何 operator（`=`/`contains`/`between`…）自动适用。tied 仓中若有不在 `country_warehouses` 列表的，先过滤再按剩余数量均分。

---

## 4. 已验证

### 4.1 后端

- `cd backend && pytest -p no:cacheprovider -k "not test_workbook_writes_to_disk"`：**273 passed, 25 skipped, 1 deselected**
- `cd backend && pytest -p no:cacheprovider tests/unit/test_excel_export_service.py::test_workbook_writes_to_disk`：**1 passed**
- 关键测试：
  - `tests/unit/test_engine_step1.py` ~ `test_engine_step6.py`
  - `tests/unit/test_zipcode_matcher.py`
  - `tests/unit/test_auth_login.py`
  - `tests/unit/test_scheduler_api.py`
  - `tests/unit/test_health_endpoints.py`
  - `tests/unit/test_config_schema.py`
  - `tests/unit/test_runtime_settings.py`
  - `tests/unit/test_sku_init.py`

### 4.2 前端

- `cd frontend && cmd /c npx vue-tsc --noEmit`：类型检查通过
- `cd frontend && cmd /c npm run test`：Vitest 通过
- `cd frontend && powershell -Command "cmd /c npm run build"`：构建成功

### 4.3 SKU 配置初始化

- `product_listing_total = 304`
- `sku_config_created = 118`
- `sku_config_enabled = 118`
- 引擎验证：`suggestion_id = 1` 生成了 91 条建议

---

## 5. 后续计划

### 短期

- 继续沉淀高频页面到 `DashboardPageHeader + DataTableCard` 体系
- 监控页补充趋势型聚合接口
- 前端 vendor chunk 进一步细分

### 中期

- 数据页数据量增长后切换为 server-side 分页（当前 1-5 用户场景无压力）
- 研究 HEI（历史建议 In-Transit）窗口是否需要调整（当前 90 天）

### 长期（按需）

- 若需多机部署：引入外部分布式锁替代 `pg_advisory_xact_lock`
- 若需多 worker：评估 Celery 迁移成本

---

## 相关文档

- [架构蓝图](Project_Architecture_Blueprint.md) — 分层架构、组件职责、ADR
- [部署指南](deployment.md) — 发布流程和环境变量
- [运维手册](runbook.md) — 故障排查和监控
- [新成员入门](onboarding.md) — 本地开发和工作流
