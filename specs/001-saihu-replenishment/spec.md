# Feature Specification: 赛狐补货计算工具

**Feature Branch**: `001-saihu-replenishment`
**Created**: 2026-04-07
**Last Updated**: 2026-04-08 (接口对齐后重构)
**Status**: Draft (modules 1–8 + API reconciliation 确认完成)
**Input**: 对接赛狐 ERP，定时拉取订单/库存/在途数据，按规则计算 SKU 级建议采购量与采购时间，人工审核后一键回写赛狐生成采购单
**Source Docs**:
- 业务设计：`2026-04-07-saihu-replenishment-design.md`
- 赛狐接口：`docs/saihu_api/` 含 7 份接口文档 + 7 份真实测试样例

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 查看每日补货建议并审核推送 (Priority: P1)

每天上班后，采购员打开系统看到按采购日期排序的补货建议列表，当日及之前到期的 SKU 红色高亮（"立即采购"），逐项核对（可编辑全部字段）后勾选条目一键推送至赛狐生成采购单。

**Why this priority**: 工具核心价值——把每天 1–2 小时的手工 Excel 计算压缩到 15 分钟以内的审核动作。

**Independent Test**: 预置已配对 SKU 的在线产品信息、库存快照、仓库国家映射，触发一次计算，前端看到按 T_采购 排序的建议列表，勾选推送后赛狐侧出现对应采购单。

**Acceptance Scenarios**:

1. **Given** 规则引擎已运行生成当日草稿建议单，**When** 采购员打开"补货建议"页面，**Then** 看到所有 SKU 按最早 T_采购 升序排列，`T_采购 ≤ 今天` 的行红色高亮标记"立即采购"
2. **Given** 建议列表已展示，**When** 采购员勾选 N 个条目点击"推送至赛狐"，**Then** 系统将选中项合并为一张采购单调用赛狐接口，成功的条目状态变为"已推送"并展示赛狐采购单号
3. **Given** 采购员审核某条建议，**When** 修改总采购量、各国分量、各仓分量或采购/发货时间，**Then** 新值落库不自动重算，推送时以用户编辑值为准

### User Story 2 - 维护 SKU 配置与全局参数 (Priority: P2)

采购员维护单 SKU 的提前期覆盖与启用开关，维护全局参数（周转天数、目标库存天数、默认提前期、样本阈值、同步/计算频率）。

**Why this priority**: 参数变更频率低，但影响所有计算。

**Independent Test**: 修改一个 SKU 的 lead_time，重新触发计算，该 SKU 的 T_采购 按新提前期变化。

**Acceptance Scenarios**:

1. **Given** 采购员进入 SKU 配置页，**When** 修改某 SKU 的 `lead_time_days` 并保存，**Then** 下次规则引擎运行时该 SKU 的 T_采购 按新提前期计算
2. **Given** 采购员进入全局参数页，**When** 修改 TARGET_DAYS 从 60 改为 75，**Then** 下次计算所有国家按 75 天目标计算

### User Story 3 - 维护仓库→国家映射与邮编规则 (Priority: P2)

采购员：① 从赛狐同步仓库列表后手动为每个仓库指定所属国家（因 `replenishSite` 字段实测不可靠）；② 按"国家 + 邮编前 N 位 + 比较操作符 + 比较值"表达式维护邮编→仓库规则。

**Acceptance Scenarios**:

1. **Given** 同步发现新仓库，**When** 仓库入库，**Then** 被标记为"待指定国家"，在未指定国家前不参与计算
2. **Given** 邮编规则已维护，**When** Step 5 执行，**Then** 各订单按 priority 从小到大匹配规则，命中即归属该仓，全部未命中归"未知仓"
3. **Given** 某国近 30 天"已知仓订单件数" < 10，**When** Step 5 执行，**Then** country_qty 在该国已维护国家的所有海外仓之间均分

### User Story 4 - 查询历史补货建议 (Priority: P3)

采购员按日期范围、状态、SKU 关键字查询历史建议单，查看当时的完整明细、配置快照、推送结果。

**Acceptance Scenarios**:

1. **Given** 系统已运行多日，**When** 采购员选择日期范围，**Then** 列出对应日期的建议单列表
2. **Given** 选中一份历史单，**When** 点击详情，**Then** 展示完整明细、当时的全局配置快照、每条推送结果，且全部只读

### User Story 5 - 查看积压提示与赛狐接口监控 (Priority: P3)

采购员有两个独立的只读观测页面：
1. **积压提示页**：展示"库存 > 0 且各国 velocity 均为 0"的 SKU
2. **接口监控页**：展示赛狐各接口最近调用时间/成功率/错误原因，失败记录可手动重试

**Acceptance Scenarios**:

1. **Given** 某 SKU 在某国库存 > 0 但 velocity = 0，**When** 采购员打开积压提示页，**Then** 看到该 SKU / 国家 / 仓库 / 当前库存 / 最后一次有销量的日期（来自 product_listing 的最近非零日销量）
2. **Given** 采购员点击"标为已处理"，**Then** 下次刷新该记录默认隐藏；可切换"显示全部"
3. **Given** 采购员打开接口监控页，**When** 查看某接口最近 24h 数据，**Then** 看到调用次数、成功率、最近一次结果、最近错误原因，失败记录可手动重试

### Edge Cases

- 赛狐接口调用失败（限流 40019 / token 40001 / 超时等）：自动重试，最终失败落 `api_call_log`，保留上一次成功快照
- 推送部分成功部分失败：成功项标记"已推送"+ 采购单号，失败项标记"推送失败"+ 错误原因，允许手动或自动重试
- 某 commoditySku 在某国 velocity = 0：从补货建议主表跳过；若全球所有国 velocity 都为 0 且库存 > 0 则写入积压提示表
- 订单本地无邮编（详情尚未拉取或拉取失败）：在 Step 5 归为"未知仓"，不参与分配
- 仓库未指定国家：不参与任何计算，UI 提示待维护
- 规则引擎触发时已有未归档建议单：自动触发时自动归档旧单；手动触发时弹窗确认后归档
- 赛狐接口返回字段为 `null`（如 `stockOccupy`、`stockWait`、`refundNum`）：MUST 一律按 0 处理
- 同一 commoditySku 在不同 listing 的 commodityId 不一致：按 commoditySku 汇总不关心，推送采购单时任取一个
- 在线产品信息接口返回 `match != true` 的产品：系统 MUST 过滤，不参与任何计算
- 公网密码被暴力破解：登录失败 5 次锁定 10 分钟
- 服务器数据丢失：每日数据库快照永久备份至对象存储可恢复

## Requirements *(mandatory)*

### Functional Requirements

**赛狐 API 客户端 (FR-001 ~ FR-008)**

- **FR-001**: 系统 MUST 实现赛狐统一请求签名（HmacSHA256），签名字段为 `access_token / client_id / method / nonce / timestamp / url` 按键名排序后用 `&` 拼接，HMAC 秘钥为 client_secret
- **FR-002**: 系统 MUST 缓存 `access_token`，仅在收到 `40001 access_token 失效` 时重新获取
- **FR-003**: 系统 MUST 对每个赛狐接口独立限流至 ≤ 1 QPS（实测 40019 触发阈值）
- **FR-004**: 请求时间戳 MUST 与赛狐服务器相差 ≤ 15 分钟；nonce MUST 每次请求随机生成避免 40012 重复提交
- **FR-005**: 系统 MUST 在接口失败时自动重试，最终失败 MUST 写入 `api_call_log`
- **FR-006**: 所有赛狐请求 MUST 为 POST + `Content-Type: application/json`，公共参数拼在 URL 查询串，业务参数放 requestBody
- **FR-007**: 系统 MUST 硬编码维护 `marketplaceId → country_code` 映射表（订单列表返回长串如 `A1VC38T7YXB528`，订单详情返回二字码如 `JP`，MUST 统一转为二字码存储）
- **FR-008**: 系统 MUST 在每次赛狐调用后写入 `api_call_log`，字段含接口名、请求时间、耗时、HTTP 状态、OpenAPI code、msg、requestId

**数据同步 — 在线产品信息 (FR-009 ~ FR-012)**

- **FR-009**: 系统 MUST 定时（默认每小时）调用"获取在线产品信息"接口 `/api/order/api/product/pageList.json`，传参 `match=true` 仅拉已配对产品，上传 `onlineStatus=active` 只拉在售 listing
- **FR-010**: 每条 listing MUST 落库到 `product_listing` 表，含 `commoditySku`、`commodityId`、`shopId`、`marketplaceId`（二字码）、`sku`（sellerSku）、`parentSku`、`commodityName`、`mainImage`、`day7SaleNum`、`day14SaleNum`、`day30SaleNum`、`onlineStatus`、`isMatched`、`lastSyncAt`
- **FR-011**: 同一 `commoditySku` 在不同 listing 返回的 `commodityId` 若不一致，系统 MUST 记录告警日志但仍按 commoditySku 汇总；推送采购单时任取一条 listing 的 commodityId
- **FR-012**: 在线产品信息 MUST 支持分页抓取（pageSize ≤ 100，一页一次请求间隔 ≥ 1s）

**数据同步 — 仓库与库存 (FR-013 ~ FR-018)**

- **FR-013**: 系统 MUST 定时（默认每日）调用"查询仓库列表"接口 `/api/warehouseManage/warehouseList.json` 同步全量仓库到本地 `warehouse` 表
- **FR-014**: 仓库 MUST 识别为"国内仓 / 海外仓"：`warehouse.type = "1"` 为国内仓库（本地仓），其他类型（0默认/2FBA/3海外仓）为海外仓；`type = -1` 虚拟仓不参与计算
- **FR-015**: 仓库的国家归属（`warehouse.country`）由采购员**手动维护**。`replenishSite` 字段实测不可靠（返回 `"-"`），仅作为 UI 辅助提示
- **FR-016**: 新同步入库的仓库 MUST 标记"待指定国家"，未指定前不参与计算；UI MUST 提示待维护
- **FR-017**: 系统 MUST 定时（默认每小时）调用"查询库存明细"接口 `/api/warehouseManage/warehouseItemList.json` 同步库存快照到 `inventory_snapshot` 表；字段映射：`stockAvailable → available`、`stockOccupy → reserved`、`stockWait → in_transit`（任何字段为 null 时按 0 处理）
- **FR-018**: 库存快照 MUST 保留时间戳，不覆盖历史；后续计算使用最新一次成功快照

**数据同步 — 订单（仅服务于 Step 5 仓内分配） (FR-019 ~ FR-024)**

- **FR-019**: 销量数据 MUST 从"在线产品信息"接口的 `day7SaleNum / day14SaleNum / day30SaleNum` 字段获取，**不再从订单聚合**
- **FR-020**: 订单接口仅用于 Step 5 的邮编→仓库分配统计，同步范围 MUST 限定为"近 30 天"且"对应 product_listing 中已配对 SKU 的店铺/站点"
- **FR-021**: 系统 MUST 定时调用"订单列表"接口 `/api/order/pageList.json`，必传 `dateStart/dateEnd/dateType=createDateTime`，拉取订单骨架到 `order_header` 表
- **FR-022**: 订单列表不返回邮编。系统 MUST 对尚未拉过详情的订单增量调用"订单详情"接口 `/api/order/detailByOrderId.json`（需 `shopId + amazonOrderId`），返回的 `postalCode`、`countryCode`、`stateOrRegion`、`detailAddress` 落入 `order_detail` 表
- **FR-023**: 系统 MUST 维护"订单详情已拉列表" `order_detail_fetch_log`，已拉过的 (shopId, amazonOrderId) MUST NOT 重复调用
- **FR-024**: 订单邮编一经入库 MUST 永久保留，不随后续同步更新

**数据同步 — 店铺列表（预留） (FR-025 ~ FR-026)**

- **FR-025**: 系统 MUST 在全局参数中提供"店铺拉取模式"开关：默认为**全量模式**（订单列表不传 `shopIdList`，拉取所有店铺）
- **FR-026**: 系统 MUST 预留"指定店铺模式"：切换后调用"店铺列表接口"（待接入）实时拉取店铺清单并缓存，采购员勾选参与同步的店铺；接口文档齐备前该模式在 UI 上置灰标注"待接入"

**规则引擎 — Step 1 动销速度 (FR-027 ~ FR-029)**

- **FR-027**: 系统 MUST 每日定时（默认 08:00 Asia/Shanghai）对所有已配对 SKU 执行补货计算；支持 UI 手动触发
- **FR-028 (Step 1)**: 对每个 `commoditySku` 的每个国家：
  ```
  listings = product_listing 中 commodity_sku=X 且 marketplace→country=Y 的所有 listing
  day7_sum  = Σ listing.day7SaleNum
  day14_sum = Σ listing.day14SaleNum
  day30_sum = Σ listing.day30SaleNum
  velocity[国] = day7_sum/7 × 0.5 + day14_sum/14 × 0.3 + day30_sum/30 × 0.2
  ```
- **FR-029**: 若某 commoditySku 在某国 velocity = 0，则该 (SKU, 国家) 组合在主建议单中跳过；若该 SKU 在所有国家 velocity 均为 0 且任一仓库存 > 0，则写入积压提示表

**规则引擎 — Step 2/3/4/5/6 (FR-030 ~ FR-037)**

- **FR-030 (Step 2)**: `sale_days[国] = (海外仓可用 + 海外仓占用 + 海外仓在途) / velocity[国]`，库存按仓库国家归属聚合，各字段 null 按 0 处理
- **FR-031 (Step 3)**: `raw[国] = TARGET_DAYS × velocity[国] − 库存三项之和`；`country_qty[国] = max(raw, 0)`；`raw < 0` 的国家记入 `overstock_countries`（只读）
- **FR-032 (Step 4)**: `total = Σ country_qty[国] + Σ velocity[国] × BUFFER_DAYS − (本地仓可用 + 本地仓占用)`，两个 Σ 仅累加 `country_qty > 0` 的国家；本地仓在途不参与扣减；`total = max(total, 0)`
- **FR-033 (Step 5)**: 对每个 `country_qty > 0` 的国家：
  - 取该国近 30 天已拉详情的订单
  - 对每单按 `postalCode` 匹配 `zipcode_rule`（按 priority 升序遍历，首命中即归属；未命中 / 无邮编 归"未知仓"）
  - 未知仓从分母剔除；`ratio = 该仓件数 / 该国已知仓总件数`
  - 若已知仓总件数 < `MIN_ORDER_SAMPLE`(10)，则在该国已维护国家的所有海外仓间均分
  - 不对小占比仓做归零处理
  - `warehouse_qty[国][仓] = country_qty[国] × ratio`
- **FR-034**: 邮编规则实体字段：国家、前缀截取长度、值类型 (number/string)、比较操作符 (`= / != / > / >= / < / <=`)、比较值、目标仓、priority
- **FR-035 (Step 6)**: `T_发货[国] = 今天 + round(sale_days − TARGET_DAYS)`；`T_采购[国] = T_发货 − lead_time`；lead_time 优先 SKU 级，缺省用全局；若任一国 `T_采购 ≤ 今天` 则整个 SKU 标记"立即采购"红色高亮
- **FR-036**: 每次规则引擎运行 MUST 将当时 `global_config` 整体快照写入 `suggestion.global_config_snapshot`
- **FR-037**: 规则引擎触发时：自动触发若存在 `draft/partial` 单则自动归档；手动触发须弹窗确认后归档

**配置管理 (FR-038 ~ FR-041)**

- **FR-038**: 用户 MUST 能维护 SKU 级配置：`commodity_sku`、`enabled`、`lead_time_days`（可空）
- **FR-039**: SKU 不存储商品名/类别/供应商/成本；展示时从 `product_listing.commodity_name / main_image` 读取
- **FR-040**: 用户 MUST 能维护全局参数：`BUFFER_DAYS`(30)、`TARGET_DAYS`(60)、`LEAD_TIME_DAYS`(50)、`MIN_ORDER_SAMPLE`(10)、`SYNC_INTERVAL`(1h)、`CALC_CRON`(08:00)、`DEFAULT_PURCHASE_WAREHOUSE_ID`、`INCLUDE_TAX`("0"/"1")、`SHOP_SYNC_MODE`(`all`/`specific`)
- **FR-041**: 用户 MUST 能通过页面 UI 维护仓库→国家映射、邮编规则（新增/编辑/删除/调序）

**审核与推送 (FR-042 ~ FR-049)**

- **FR-042**: 用户 MUST 能浏览建议单，主列表按"最早 T_采购"升序排列，`T_采购 ≤ 今天` 红色高亮
- **FR-043**: 用户 MUST 能在审核阶段编辑：总采购量、各国分量、各国各仓分量、采购时间、发货时间；仅数字非负校验，不自动重算
- **FR-044**: 用户 MUST 能勾选条目一键推送至赛狐；选中项 MUST 合并为一张采购单（含多 SKU 明细）
- **FR-045**: 调用"采购单创建"接口 `/api/purchase/create.json`，必填参数：
  - `warehouseId` = 全局参数 `DEFAULT_PURCHASE_WAREHOUSE_ID`
  - `action` = `"1"`（提交）
  - `includeTax` = 全局参数 `INCLUDE_TAX`（字符串 `"0"` 或 `"1"`，**不是 true/false**）
  - `items[]` = 每条对应一个 SKU：`{ commodityId: <查 product_listing>, num: <total_qty> }`
  - 其他字段（supplierId/partyaId/paymentMethodId/purchaserId 等）第一版**不填**，由赛狐 Web 端事后补全
- **FR-046**: 推送结果 MUST 按条目记录状态：成功 → 保存赛狐返回的 `purchaseOrderNo`；失败 → 保存 `code/msg`。失败支持系统自动重试（默认 3 次）+ 手动重试
- **FR-047**: 若某 commoditySku 在 `product_listing` 中查不到 `commodityId`，推送该条目 MUST 失败并提示"SKU 尚未建立 commodityId 映射，请先确保该 SKU 至少同步过一次在线产品信息"，不阻塞其他条目
- **FR-048**: 建议单状态 MUST 支持：`draft` / `partial` / `pushed` / `archived`
- **FR-049**: 同一 SKU 展开时 MUST 展示积压国家列表（raw<0 的国家）及其库存、动销、预计消化天数

**历史与监控 (FR-050 ~ FR-054)**

- **FR-050**: 规则引擎 MUST 同步生成积压 SKU 提示表，字段含最后一次有销量的日期（来自 `product_listing` 的 day30_sale_num 最近非零的日期估算，或仅展示 last_sync_at）
- **FR-051**: 用户 MUST 能对积压记录点击"标为已处理"，默认隐藏可切回"显示全部"
- **FR-052**: 用户 MUST 能访问"接口监控页"查看各接口最近调用时间、近 24h 成功率与次数、最近错误原因，失败记录可手动重试
- **FR-053**: 用户 MUST 能按日期范围、状态、SKU 关键字查询历史建议单及明细、配置快照、推送结果
- **FR-054**: 历史建议单、库存快照、订单骨架 + 详情、api_call_log、积压记录 MUST 永久保留；历史单只读不可编辑/重推

**安全与规模 (FR-055 ~ FR-058)**

- **FR-055**: 系统 MUST 通过单用户密码登录控制访问，会话基于 token
- **FR-056**: 系统 MUST 在连续登录失败 5 次后锁定账号 10 分钟
- **FR-057**: 系统 MUST 通过 HTTPS 提供服务
- **FR-058**: 系统 MUST 支持中等规模：100–500 启用 SKU × 4–5 目标国家 × 6–10 海外仓；核心接口 ≥ 20 QPS（内部 1–5 用户场景）

### Key Entities

- **sku_config**: `commodity_sku` (PK) / `enabled` / `lead_time_days` (可空)
- **global_config**: 单行 KV 存所有全局参数（含默认主仓、含税标记、店铺模式）
- **warehouse**: `id` (PK, 来自赛狐 warehouse.id) / `name` / `type` (1国内/0默认/2FBA/3海外) / `country` (手动维护，可空) / `replenish_site_raw` (原始值仅供参考) / `last_sync_at`
- **product_listing**: `id` (PK) / `commodity_sku` / `commodity_id` / `shop_id` / `marketplace_id` (二字码) / `seller_sku` / `parent_sku` / `commodity_name` / `main_image` / `day7_sale_num` / `day14_sale_num` / `day30_sale_num` / `is_matched` / `online_status` / `last_sync_at`。唯一索引 `(shop_id, marketplace_id, seller_sku)`；普通索引 `(commodity_sku, marketplace_id)`
- **inventory_snapshot**: `commodity_sku` / `warehouse_id` / `country` (派生自 warehouse) / `available` / `reserved` / `in_transit` / `snapshot_at`
- **order_header**: 订单骨架，`shop_id` / `amazon_order_id` (唯一) / `marketplace_id` / `country_code` / `purchase_date` / `order_status` / `last_sync_at`
- **order_item**: `order_id` FK / `commodity_sku` / `seller_sku` / `quantity_ordered` / `quantity_shipped` / `refund_num`
- **order_detail**: `shop_id` / `amazon_order_id` (唯一) / `postal_code` / `country_code` / `state_or_region` / `detail_address` / `fetched_at`
- **order_detail_fetch_log**: `shop_id` / `amazon_order_id` / `fetched_at`（避免重复拉详情）
- **zipcode_rule**: `id` / `country` / `prefix_length` / `value_type` (number/string) / `operator` / `compare_value` / `warehouse_id` / `priority`
- **suggestion**: `id` / `created_at` / `status` (draft/partial/pushed/archived) / `global_config_snapshot` (JSON)
- **suggestion_item**: `id` / `suggestion_id` FK / `commodity_sku` / `total_qty` / `country_breakdown` (JSON) / `warehouse_breakdown` (JSON) / `t_purchase` (JSON per country) / `t_ship` (JSON per country) / `overstock_countries` (JSON) / `urgent` (bool) / `push_status` / `saihu_po_number` / `push_error`
- **overstock_sku_mark**: `commodity_sku` / `country` / `warehouse_id` / `processed_at` / `note`
- **api_call_log**: `id` / `endpoint` / `called_at` / `duration_ms` / `http_status` / `openapi_code` / `openapi_msg` / `request_id`

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 采购员每日补货决策耗时从 ≥1 小时降至 ≤15 分钟
- **SC-002**: 系统在用户登录后 3 秒内展示当日补货建议列表
- **SC-003**: 数据同步任务成功率 ≥ 99%（一周窗口）
- **SC-004**: 规则引擎对单批次（500 SKU 规模）计算 MUST 在 5 分钟内完成
- **SC-005**: 推送至赛狐的采购单创建成功率 ≥ 98%，失败可在 UI 明确看到原因并重试
- **SC-006**: 关键交互接口 P95 响应时间 < 500ms（遵循宪法 Performance Standards）
- **SC-007**: 系统稳定运行 30 天无需人工重启
- **SC-008**: 订单详情增量拉取：首次回填（近 30 天 ≤ 3000 单）在 1 小时内完成，日常增量在 10 分钟内完成

## Assumptions

- 单一采购员使用，无角色权限模型
- 部署于公网云服务器（2核4G），HTTPS + 密码登录
- 赛狐 ERP OpenAPI 账号已开通以下接口：access_token / 在线产品信息 / 查询仓库列表 / 查询库存明细 / 订单列表 / 订单详情 / 其他出库列表（备用）/ 采购单创建；出口 IP 已加赛狐白名单
- 赛狐限流：每个接口 ≤1 QPS（实测 40019 阈值）；token 15 分钟时效
- 在线产品信息接口返回的 `day7/14/30SaleNum` 是赛狐已算好的销量口径，系统直接信任
- 只处理 `match=true && onlineStatus=active` 的 listing
- 数据同步默认每小时一次；规则引擎默认每日 08:00 北京时间
- 全局参数默认值：BUFFER=30、TARGET=60、LEAD=50、MIN_SAMPLE=10
- 订单邮编从订单详情接口获得，已拉的 (shopId, amazonOrderId) 永不重复拉
- marketplaceId 两套格式：订单列表返回长串、订单详情返回二字码，系统统一转二字码存储
- 数据库每日凌晨 03:00 快照备份至对象存储，永久保留不清理
- 应用日志保留最近 90 天
- 自动推送重试次数默认 3 次
- 第一版不做：多用户/权限、自动调拨、全自动下单、邮件/微信告警、CI/CD、多事业部隔离、CSV 导入/导出、首次运行引导向导
- 采购单创建只提交 4 个必填字段（warehouseId/action/includeTax/items），其他 ID 留空待赛狐 Web 端人工补全

## Dependencies

- 赛狐 ERP OpenAPI：client_id、client_secret、access_token 获取端点、出口 IP 已加白
- 域名 + Let's Encrypt HTTPS 证书
- 云对象存储（OSS/COS）用于数据库备份

## Notes / Deferred

**已对齐的接口字段**（基于 `docs/saihu_api/测试示例/`）：
- 签名算法、公共参数、公共错误码已明确
- 订单列表 `marketplaceId` 返回长串（`A1VC38T7YXB528`），订单详情返回二字码（`JP`）
- 订单详情实测返回 `postalCode/countryCode/stateOrRegion/detailAddress`（文档描述过时）
- `stockOccupy/stockWait/refundNum` 可能为 `null`，按 0 处理
- `warehouse.replenishSite` 实测返回 `"-"`，不可作为国家来源
- `purchase.create` 的 `includeTax` 必须是 `"0"/"1"` 字符串（传 `"false"` 被拒 40014）
- 在线产品信息筛选 `match=true` 可直接获得"已配对"产品

**推迟到 plan 阶段或后续迭代**：
- **店铺列表接口**：文档尚未提供，"指定店铺模式"UI 先置灰
- **其他出库列表**作为在途数据备用方案，待 `stockWait` 口径不符时启用
- 赛狐"采购单创建"的完整必填字段验证（当前仅知 4 个必填，supplier/partya 等留空是否可被赛狐接受需联调验证）
- 同一 commoditySku 不同 listing 的 commodityId 一致性（测试数据中未观察到冲突，暂按"任取一个 + 告警"处理）
