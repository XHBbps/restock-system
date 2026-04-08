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
- **FR-002**: 系统 MUST 通过 **GET** `/api/oauth/v2/token.json` 获取 access_token（query 参数 `client_id / client_secret / grant_type=client_credentials`），**此接口是唯一不走签名且使用 GET 的接口**
- **FR-002a**: 系统 MUST 缓存 access_token 至内存 + 持久化，按返回的 `expires_in`（毫秒）管理有效期，提前 5 分钟主动续期；收到 `40001 access_token 失效` 时 MUST 立即重新获取并重试原请求一次
- **FR-002b**: 系统 MUST NOT 频繁调用 token 接口（有频率限制），禁止每次业务请求前刷新
- **FR-003**: 系统 MUST 对每个赛狐接口独立限流至 ≤ 1 QPS（实测 40019 触发阈值）
- **FR-004**: 请求时间戳 MUST 与赛狐服务器相差 ≤ 15 分钟；nonce MUST 每次请求随机生成避免 40012 重复提交
- **FR-005**: 系统 MUST 在接口失败时自动重试，最终失败 MUST 写入 `api_call_log`
- **FR-006**: 所有赛狐请求 MUST 为 POST + `Content-Type: application/json`，公共参数拼在 URL 查询串，业务参数放 requestBody
- **FR-007**: 系统 MUST 硬编码维护 `marketplaceId → country_code → timezone` 映射表（订单列表返回长串如 `A1VC38T7YXB528`，订单详情返回二字码如 `JP`，MUST 统一转为二字码存储；每个 country_code 对应一个 IANA 时区如 `Asia/Tokyo`，来源于 `docs/saihu_api/开发指南/站点对应关系.md` + 标准站点时区）
- **FR-007a**: 系统 MUST 将赛狐返回的所有时间字段（`purchaseDate` / `lastUpdateDate` / `updateTime` 等）按订单所在站点时区解析，再**统一转换为 `Asia/Shanghai`（北京时间）存储**，避免跨时区订单的窗口边界错位
- **FR-008**: 系统 MUST 在每次赛狐调用后写入 `api_call_log`，字段含接口名、请求时间、耗时、HTTP 状态、OpenAPI code、msg、requestId

**数据同步 — 在线产品信息 (FR-009 ~ FR-012)**

- **FR-009**: 系统 MUST 定时（默认每小时）调用"获取在线产品信息"接口 `/api/order/api/product/pageList.json`，传参 `match=true` 仅拉已配对产品，上传 `onlineStatus=active` 只拉在售 listing
- **FR-010**: 每条 listing MUST 落库到 `product_listing` 表，含 `commoditySku`、`commodityId`、`shopId`、`marketplaceId`（二字码）、`sku`（sellerSku）、`parentSku`、`commodityName`、`mainImage`、`onlineStatus`、`isMatched`、`lastSyncAt`；`day7/14/30SaleNum` 字段仍落库但**仅作对账参考**，不参与 velocity 计算
- **FR-011**: 同一 `commoditySku` 在不同 listing 返回的 `commodityId` 若不一致，系统 MUST 记录告警日志但仍按 commoditySku 汇总；推送采购单时任取一条 listing 的 commodityId
- **FR-012**: 在线产品信息 MUST 支持分页抓取（pageSize ≤ 100，一页一次请求间隔 ≥ 1s）

**数据同步 — 仓库与库存 (FR-013 ~ FR-018)**

- **FR-013**: 系统 MUST 定时（默认每日）调用"查询仓库列表"接口 `/api/warehouseManage/warehouseList.json` 同步全量仓库到本地 `warehouse` 表
- **FR-014**: 仓库 MUST 识别为"国内仓 / 海外仓"：`warehouse.type = "1"` 为国内仓库（本地仓），其他类型（0默认/2FBA/3海外仓）为海外仓；`type = -1` 虚拟仓不参与计算
- **FR-015**: 仓库的国家归属（`warehouse.country`）由采购员**手动维护**。`replenishSite` 字段实测不可靠（返回 `"-"`），仅作为 UI 辅助提示
- **FR-016**: 新同步入库的仓库 MUST 标记"待指定国家"，未指定前不参与计算；UI MUST 提示待维护
- **FR-017**: 系统 MUST 定时（默认每小时）调用"查询库存明细"接口 `/api/warehouseManage/warehouseItemList.json` 同步库存快照到 `inventory_snapshot_latest` 表；字段映射：`stockAvailable → available`、`stockOccupy → reserved`（null→0）。**在途数据不从此接口取**（见 FR-017a）
- **FR-017a**: 系统 MUST 定时（默认每小时）调用"其他出库列表页"接口 `/api/warehouseInOut/outRecords.json`，传 `searchField=remark, searchValue=在途中`，分页拉取所有"单据备注包含'在途中'"的出库单
- **FR-017b**: 每条出库单 MUST 以 `saihu_out_record_id` 为主键 UPSERT 到 `in_transit_record` 表，含 `out_warehouse_no`、`target_warehouse_id`、`target_country`（通过 warehouse 映射派生）、`remark`、`is_in_transit=true`、`last_seen_at=本次同步开始时间`、`status`；出库单下的每条 item MUST UPSERT 到 `in_transit_item` 表，含 `commodity_sku`、`goods`（即 `可用数`）
- **FR-017c**: 每次同步结束后，系统 MUST 将 `in_transit_record` 中 `last_seen_at < 本次同步开始时间 AND is_in_transit=true` 的记录标记为 `is_in_transit=false`，对应在途数量自动归零（即备注中"在途中"消失/被移除）
- **FR-017d**: 规则引擎 Step 2 的在途总量 MUST 通过 `in_transit_item JOIN in_transit_record WHERE is_in_transit=true GROUP BY commodity_sku, target_country` 聚合得到，不再读取 `stockWait` 字段
- **FR-018**: `inventory_snapshot_latest` 只存最近一次同步结果（UPSERT），同时每日 02:00 整表归档到 `inventory_snapshot_history`（含 `snapshot_date`），history 永久保留

**数据同步 — 订单（服务于 Step 1 velocity + Step 5 仓内分配） (FR-019 ~ FR-024)**

- **FR-019**: Velocity 数据 MUST 由系统基于 `order_item` 自行聚合计算，**不信任赛狐在线产品信息接口的 `day*SaleNum` 字段**（未经真实测试验证、口径可能与"已发货净销量"不一致）
- **FR-020**: 订单接口同时服务于 Step 1（velocity 聚合）和 Step 5（邮编分配）。订单列表 MUST 全量拉取近 30 天（接口不支持按 SKU 过滤），订单详情仅对"已配对 SKU 相关订单"增量拉取
- **FR-021**: 系统 MUST 定时调用"订单列表"接口 `/api/order/pageList.json`，增量同步使用 `dateType=updateDateTime` + `dateStart=sync_state.last_success_at - 5min` + `dateEnd=now`（预留 5 分钟重叠防漏单），确保捕获状态变化（发货/取消/退款）；`order_header` 按 `(shop_id, amazon_order_id)` UPSERT，`order_item` 按 `(order_id, order_item_id)` UPSERT，覆盖 quantityShipped / refundNum / status 等动态字段
- **FR-022**: 订单列表不返回邮编。系统 MUST 对尚未拉过详情的订单增量调用"订单详情"接口 `/api/order/detailByOrderId.json`（需 `shopId + amazonOrderId`），返回的 `postalCode`、`countryCode`、`stateOrRegion`、`detailAddress` 落入 `order_detail` 表
- **FR-023**: 系统 MUST 维护"订单详情已拉列表" `order_detail_fetch_log`，已拉过的 (shopId, amazonOrderId) MUST NOT 重复调用
- **FR-024**: 订单邮编一经入库 MUST 永久保留，不随后续同步更新

**数据同步 — 店铺列表 (FR-025 ~ FR-026b)**

- **FR-025**: 系统 MUST 在全局参数中提供"店铺拉取模式"开关：默认为**全量模式**（订单列表不传 `shopIdList`，拉取所有店铺）
- **FR-026**: 系统 MUST 支持"指定店铺模式"：切换后调用"店铺列表"接口 `/api/shop/pageList.json` **实时拉取并缓存**到本地 `shop` 表，采购员在 UI 勾选参与同步的店铺，订单接口的 `shopIdList` 参数只传勾选项的 `shop.id`
- **FR-026a**: 店铺列表 MUST 按 `status = "0"`（默认/正常授权）过滤，`status = "1"`（授权失效）或 `"2"`（SP授权失效）的店铺 MUST 在 UI 中标记为"授权失效"且不可勾选
- **FR-026b**: 店铺缓存 MUST 提供"手动刷新"按钮，采购员在 UI 点击后调用店铺列表接口更新本地缓存；系统不做定时同步（授权状态变化频率低）

**规则引擎 — Step 1 动销速度 (FR-027 ~ FR-029)**

- **FR-027**: 系统 MUST 每日定时（默认 08:00 Asia/Shanghai）对所有已配对 SKU 执行补货计算；支持 UI 手动触发
- **FR-028 (Step 1)**: 对每个启用 `commoditySku` 的每个国家，从 `order_item` 聚合计算：
  ```
  过滤条件：
    order_header.order_status ∈ {Shipped, PartiallyShipped}
    order_header.purchase_date ∈ [昨天-29, 昨天]（不含今天）
    order_item.commodity_sku = X
    marketplace_to_country(order_header.marketplace_id) = Y

  对每条 order_item：
    effective = max(
      int(quantityShipped or 0) - int(refundNum or 0),
      0
    )

  按日期聚合：
    day7_sum  = Σ effective where date ∈ [昨天-6, 昨天]
    day14_sum = Σ effective where date ∈ [昨天-13, 昨天]
    day30_sum = Σ effective where date ∈ [昨天-29, 昨天]

  velocity[sku][国] = day7_sum/7 × 0.5
                    + day14_sum/14 × 0.3
                    + day30_sum/30 × 0.2
  ```
- **FR-028a**: 订单状态变更 MUST 在每次增量同步中通过 UPSERT 正确反映；已取消/已退款订单的 effective 自动归零
- **FR-029**: 若某 commoditySku 在某国 velocity = 0，则该 (SKU, 国家) 组合在主建议单中跳过；若该 SKU 在所有国家 velocity 均为 0 且任一仓库存 > 0，则写入积压提示表

**规则引擎 — Step 2/3/4/5/6 (FR-030 ~ FR-037)**

- **FR-030 (Step 2)**: `sale_days[国] = (海外仓可用 + 海外仓占用 + 海外仓在途) / velocity[国]`。其中：
  - 可用/占用：从 `inventory_snapshot_latest` 按 `warehouse.country` 聚合（所有非本地仓 type ≠ 1）
  - 在途：从 `in_transit_item JOIN in_transit_record WHERE is_in_transit=true` 按 `target_country` 聚合
  - 所有 null 字段按 0 处理
- **FR-031 (Step 3)**: `raw[国] = TARGET_DAYS × velocity[国] − 库存三项之和`；`country_qty[国] = max(raw, 0)`；`raw < 0` 的国家记入 `overstock_countries`（只读）
- **FR-032 (Step 4)**: `total = Σ country_qty[国] + Σ velocity[国] × BUFFER_DAYS − (本地仓可用 + 本地仓占用)`，两个 Σ 仅累加 `country_qty > 0` 的国家；本地仓在途不参与扣减；`total = max(total, 0)`
- **FR-033 (Step 5)**: 对每个 `country_qty > 0` 的国家：
  - 取**该 SKU 在该国近 30 天**已拉详情且有 `postal_code` 的订单（order_header JOIN order_detail）
  - 对每单按 `postal_code` 匹配 `zipcode_rule`（按 priority 升序遍历，首命中即归属；未命中 / 无邮编 归"未知仓"）
  - 未知仓从分母剔除
  - **情况 A**（`已知仓总件数 > 0`，常见）：按实际比例分配
    `ratio[仓] = 该仓件数 / 已知仓总件数`
    `warehouse_qty[仓] = country_qty × ratio[仓]`
    **不设样本阈值，不做小占比归零，按真实数据分配**
  - **情况 B**（`已知仓总件数 = 0`，零数据兜底）：该 SKU 在该国没有可匹配的订单
    → 均分到该国所有"已维护国家"的海外仓
    → UI 上在该 SKU 该国维度提示"零样本均分"
- **FR-034**: 邮编规则实体字段：国家、前缀截取长度、值类型 (number/string)、比较操作符 (`= / != / > / >= / < / <=`)、比较值、目标仓、priority
- **FR-034a**: 邮编匹配前 MUST 对 `postal_code` 做归一化清洗：`strip()` 去首尾空白，移除内部 `-` 与空格，再按 `prefix_length` 截取比较。涵盖所有国家邮编格式（含欧盟字母数字混合如 `"SW1A 1AA"`、日本 `"640-8453"` 等）
- **FR-035 (Step 6)**: `T_发货[国] = 今天 + round(sale_days − TARGET_DAYS)`；`T_采购[国] = T_发货 − lead_time`；lead_time 优先 SKU 级，缺省用全局；若任一国 `T_采购 ≤ 今天` 则整个 SKU 标记"立即采购"红色高亮
- **FR-036**: 每次规则引擎运行 MUST 将当时 `global_config` 整体快照写入 `suggestion.global_config_snapshot`
- **FR-037**: 规则引擎触发时：自动触发若存在 `draft/partial` 单则自动归档；手动触发须弹窗确认后归档

**配置管理 (FR-038 ~ FR-041)**

- **FR-038**: 用户 MUST 能维护 SKU 级配置：`commodity_sku`、`enabled`、`lead_time_days`（可空）
- **FR-039**: SKU 不存储商品名/类别/供应商/成本；展示时从 `product_listing.commodity_name / main_image` 读取
- **FR-040**: 用户 MUST 能维护全局参数：`BUFFER_DAYS`(30)、`TARGET_DAYS`(60)、`LEAD_TIME_DAYS`(50)、`SYNC_INTERVAL`(1h)、`CALC_CRON`(08:00)、`DEFAULT_PURCHASE_WAREHOUSE_ID`、`INCLUDE_TAX`("0"/"1")、`SHOP_SYNC_MODE`(`all`/`specific`)。`MIN_ORDER_SAMPLE` 参数已废弃不再使用（Step 5 采用"有数据就按真实比例、零数据才均分"策略，不设样本阈值）
- **FR-041**: 用户 MUST 能通过页面 UI 维护仓库→国家映射、邮编规则（新增/编辑/删除/调序）

**审核与推送 (FR-042 ~ FR-049)**

- **FR-042**: 用户 MUST 能浏览建议单，主列表按"最早 T_采购"升序排列，`T_采购 ≤ 今天` 红色高亮
- **FR-043**: 用户 MUST 能在审核阶段编辑：总采购量、各国分量、各国各仓分量、采购时间、发货时间；仅数字非负校验，不自动重算
- **FR-044**: 用户 MUST 能勾选条目一键推送至赛狐；选中项 MUST 合并为一张采购单（含多 SKU 明细）
- **FR-045**: 调用"采购单创建"接口 `/api/purchase/create.json`，必填参数：
  - `warehouseId` = 全局参数 `DEFAULT_PURCHASE_WAREHOUSE_ID`
  - `action` = `"1"`（提交）
  - `includeTax` = 全局参数 `INCLUDE_TAX`（字符串 `"0"` 或 `"1"`，**不是 true/false**）
  - `items[]` = 每条对应一个 SKU：`{ commodityId: <查 product_listing>, num: "<total_qty>" }`
  - `num` 字段 MUST 序列化为**字符串**（赛狐 schema 要求 string 类型，如 `"928"` 非 `928`）
  - 其他字段（supplierId/partyaId/paymentMethodId/purchaserId 等）第一版**不填**，由赛狐 Web 端事后补全
- **FR-045a**: 前端 MUST 限制单次推送最多 50 条 `suggestion_item`；超过时提示用户分批推送（赛狐 items 数量上限未知，50 为保守值，联调后可调）
- **FR-046**: 推送结果 MUST 按条目记录状态：成功 → 保存赛狐返回的 `purchaseOrderNo`；失败 → 保存 `code/msg`。失败支持系统自动重试（默认 3 次）+ 手动重试
- **FR-047**: 规则引擎生成 `suggestion_item` 时 MUST 预检查 `commoditySku` 是否能在 `product_listing` 中查到 `commodity_id`，查不到则在 `suggestion_item.push_blocker` 字段中标记原因（如 "未建立 commodity_id 映射"）；UI MUST 在该条目显著位置展示"无法推送"标签；用户勾选时 MUST 自动过滤或弹窗拒绝有 push_blocker 的条目
- **FR-048**: 建议单状态 MUST 支持：`draft` / `partial` / `pushed` / `archived`
- **FR-049**: 同一 SKU 展开时 MUST 展示积压国家列表（raw<0 的国家）及其库存、动销、预计消化天数

**历史与监控 (FR-050 ~ FR-054)**

- **FR-050**: 规则引擎 MUST 同步生成积压 SKU 提示表，字段含最后一次有销量的日期（来自 `product_listing` 的 day30_sale_num 最近非零的日期估算，或仅展示 last_sync_at）
- **FR-051**: 用户 MUST 能对积压记录点击"标为已处理"，默认隐藏可切回"显示全部"
- **FR-052**: 用户 MUST 能访问"接口监控页"查看各接口最近调用时间、近 24h 成功率与次数、最近错误原因，失败记录可手动重试
- **FR-053**: 用户 MUST 能按日期范围、状态、SKU 关键字查询历史建议单及明细、配置快照、推送结果
- **FR-054**: 历史建议单、库存快照、订单骨架 + 详情、api_call_log、积压记录 MUST 永久保留；历史单只读不可编辑/重推

**任务调度与执行 (FR-058a ~ FR-058h)**

- **FR-058a**: 系统 MUST 实现"Scheduler + Queue + Worker"三层任务架构：
  - **Scheduler**（APScheduler）只负责按时触发 enqueue，不直接执行业务逻辑
  - **task_run** 表同时作为队列 + 历史 + 进度记录
  - **Worker**（后台 asyncio 循环）从 task_run 领取 pending 任务执行
- **FR-058b**: 入队 MUST 通过"数据库部分唯一索引"保证幂等：对 `dedupe_key` 在 `status IN ('pending','running')` 状态下创建 UNIQUE 约束。入队时走事务 INSERT，捕获 UniqueViolation 即视为"已存在活跃任务"
- **FR-058c**: 去重行为：
  - `scheduler` 触发遇重复 → 额外插入一条 `status='skipped'` 记录留痕
  - `manual` 触发遇重复 → 返回已有任务的 `task_id`，前端复用轮询
- **FR-058d**: Worker 取任务 MUST 原子化，使用：
  ```sql
  UPDATE task_run SET status='running', worker_id=?, started_at=now(),
                       heartbeat_at=now(),
                       lease_expires_at=now()+interval '2 minutes',
                       attempt_count=attempt_count+1
  WHERE id = (
      SELECT id FROM task_run WHERE status='pending'
      ORDER BY priority, created_at
      FOR UPDATE SKIP LOCKED LIMIT 1
  ) RETURNING *;
  ```
- **FR-058e**: Worker 执行期间 MUST 每 30 秒续租：更新 `heartbeat_at = now()` 和 `lease_expires_at = now() + 2 min`，并可同步更新 `current_step / step_detail` 供前端进度展示
- **FR-058f**: 系统 MUST 每分钟运行"僵尸任务回收"：`UPDATE task_run SET status='failed', error_msg='Lease expired' WHERE status='running' AND lease_expires_at < now()`。回收后**不自动重新入队**，由业务侧决定是否触发新任务
- **FR-058g**: `task_run.status` 枚举 MUST 为：`pending / running / success / failed / skipped / cancelled`，其中 `skipped` 仅由 scheduler 去重产生，`cancelled` 为后续人工中止预留
- **FR-058h**: 前端 MUST 通过 `GET /api/tasks/{task_id}` 每 2 秒轮询任务状态，返回 `{status, current_step, step_detail, total_steps, attempt_count, error_msg, result_summary}`；任务终态后停止轮询

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
- **inventory_snapshot_latest**: `commodity_sku` / `warehouse_id` / `country` (派生自 warehouse) / `available` / `reserved` / `updated_at`（PK `(commodity_sku, warehouse_id)`）。**不存 in_transit**（在途由 in_transit_item 聚合）
- **inventory_snapshot_history**: 每日归档，字段同 latest，额外 `snapshot_date`
- **in_transit_record**: 出库单级在途追踪，`saihu_out_record_id` (PK) / `out_warehouse_no` / `target_warehouse_id` / `target_country` / `remark` / `status` / `is_in_transit` (bool) / `last_seen_at` / `created_at` / `updated_at`
- **in_transit_item**: 出库单明细，`id` (PK) / `saihu_out_record_id` (FK) / `commodity_sku` / `goods` (可用数，即在途数量)
- **order_header**: 订单骨架，`shop_id` / `amazon_order_id` (唯一) / `marketplace_id` / `country_code` / `purchase_date` / `order_status` / `last_sync_at`
- **order_item**: `order_id` FK / `order_item_id`（赛狐 orderItemId）/ `commodity_sku` / `seller_sku` / `quantity_ordered` / `quantity_shipped` / `refund_num`；PK = `(order_id, order_item_id)`
- **order_detail**: `shop_id` / `amazon_order_id` (唯一) / `postal_code` / `country_code` / `state_or_region` / `detail_address` / `fetched_at`
- **order_detail_fetch_log**: `shop_id` / `amazon_order_id` / `fetched_at`（避免重复拉详情）
- **zipcode_rule**: `id` / `country` / `prefix_length` / `value_type` (number/string) / `operator` / `compare_value` / `warehouse_id` / `priority`
- **suggestion**: `id` / `created_at` / `status` (draft/partial/pushed/archived) / `global_config_snapshot` (JSON)
- **suggestion_item**: `id` / `suggestion_id` FK / `commodity_sku` / `total_qty` / `country_breakdown` (JSON) / `warehouse_breakdown` (JSON) / `t_purchase` (JSON per country) / `t_ship` (JSON per country) / `overstock_countries` (JSON) / `urgent` (bool) / `push_status` / `saihu_po_number` / `push_error`
- **overstock_sku_mark**: `commodity_sku` / `country` / `warehouse_id` / `processed_at` / `note`
- **api_call_log**: `id` / `endpoint` / `called_at` / `duration_ms` / `http_status` / `openapi_code` / `openapi_msg` / `request_id`
- **shop**: 店铺缓存，`id` (PK, 来自赛狐) / `name` / `seller_id` / `region` (na/eu/fe) / `marketplace_id` / `status` (0/1/2) / `ad_status` / `sync_enabled` (bool, 指定店铺模式下采购员勾选) / `last_sync_at`
- **access_token_cache**: `access_token` / `acquired_at` / `expires_at`（单行）
- **sync_state**: `job_name` (PK) / `last_run_at` / `last_success_at` / `last_status` / `last_error`；供 `order_list` / `product_listing` / `out_records` 等增量任务记录"上次同步时间"
- **task_run**: `id` (PK) / `job_name` / `dedupe_key` / `status` (pending/running/success/failed/skipped/cancelled) / `trigger_source` (scheduler/manual) / `priority` / `payload` (JSONB) / `current_step` / `step_detail` / `total_steps` / `attempt_count` / `error_msg` / `result_summary` / `result_payload` (JSONB) / `worker_id` / `heartbeat_at` / `lease_expires_at` / `started_at` / `finished_at` / `created_at`。**关键约束**：`CREATE UNIQUE INDEX ON task_run(dedupe_key) WHERE status IN ('pending','running')`

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
- 赛狐 ERP OpenAPI 账号已开通以下接口：access_token / 店铺列表 / 在线产品信息 / 查询仓库列表 / 查询库存明细 / 其他出库列表 / 订单列表 / 订单详情 / 采购单创建；出口 IP 已加赛狐白名单
- 赛狐限流：每个业务接口 ≤1 QPS（实测 40019 阈值）；token 接口另有独立频率限制不可频繁调用
- access_token 默认有效期约 24 小时（实测 `expires_in ≈ 84850421ms`），系统按 expires_in 管理缓存
- 在线产品信息接口仅用于：① `match=true && onlineStatus=active` 筛选 ② 建立 `commoditySku ↔ commodityId` 映射 ③ 提供商品名/图片展示。其 `day*SaleNum` 字段存库但不参与 velocity 计算
- Velocity 数据由系统从 `order_item` 自行聚合（定义：`effective = max(quantityShipped - refundNum, 0)`，过滤 Shipped/PartiallyShipped）
- 订单增量同步按 `updateDateTime` 拉取，确保订单状态变化（发货/取消/退款）能被捕获并覆盖历史记录
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

## Backend Design Direction

### 技术栈（锁定）

| 层 | 选型 | 理由 |
|---|---|---|
| 语言/运行时 | **Python 3.11+** | I/O 密集场景、生态完整 |
| Web 框架 | **FastAPI 0.115+** | async、Pydantic v2、自动 OpenAPI |
| ORM | **SQLAlchemy 2.0 (async)** | 最成熟、类型支持好 |
| 数据库迁移 | **Alembic** | SQLA 官方配套 |
| 数据校验 | **Pydantic v2** | DTO + 配置 |
| HTTP 客户端 | **httpx** (async) | 对接赛狐 API |
| 接口限流 | **aiolimiter** | 每接口独立 1 QPS token bucket |
| 重试 | **tenacity** | 赛狐失败重试 + 指数退避 |
| 定时任务 | **APScheduler** | 嵌入 FastAPI 进程，无需 Celery |
| 配置 | **pydantic-settings** | `.env` + 类型 |
| 日志 | **structlog** | 结构化 JSON |
| 密码 | **passlib[bcrypt]** | 单用户 hash |
| JWT | **python-jose** | 会话 token |
| 测试 | **pytest + pytest-asyncio** | 官方方案 |
| Lint/Format/Type | **ruff + black + mypy** | 对应宪法 Code Style 门禁 |

### 数据库：PostgreSQL 16

- **JSONB 字段**用于：`global_config_snapshot`、`country_breakdown`、`warehouse_breakdown`、`t_purchase`、`t_ship`、`overstock_countries`
- **核心索引**：
  - `product_listing`: UNIQUE(shop_id, marketplace_id, seller_sku) + INDEX(commodity_sku, marketplace_id)
  - `inventory_snapshot_latest`: PK(commodity_sku, warehouse_id)
  - `inventory_snapshot_history`: INDEX(snapshot_date, commodity_sku)
  - `in_transit_record`: PK(saihu_out_record_id), INDEX(is_in_transit, target_country), INDEX(last_seen_at)
  - `in_transit_item`: PK(id), INDEX(saihu_out_record_id), INDEX(commodity_sku)
  - `sync_state`: PK(job_name)
  - `task_run`: PK(id), UNIQUE INDEX(dedupe_key) WHERE status IN ('pending','running'), INDEX(status, priority, created_at), INDEX(job_name, created_at DESC), INDEX(lease_expires_at) WHERE status='running'
  - `order_header`: UNIQUE(shop_id, amazon_order_id) + INDEX(purchase_date) + INDEX(country_code, purchase_date)
  - `order_detail`: UNIQUE(shop_id, amazon_order_id)
  - `suggestion`: INDEX(created_at DESC)
  - `api_call_log`: INDEX(endpoint, called_at DESC)

### 库存快照双表策略（修订 FR-018）

为避免"每小时全量快照"导致的爆炸性增长（500 SKU × 60 仓 × 24 × 365 ≈ 2.6 亿行），库存采用双表结构：

- **`inventory_snapshot_latest`**（单行/仓+SKU）
  - 每次同步 UPSERT，规则引擎运行时只读此表
  - 始终反映最近一次同步结果
  - 表体稳定（约 5000 行）
- **`inventory_snapshot_history`**
  - 每日凌晨 02:00 定时任务将 `latest` 表整体归档追加一份
  - 保留字段：`commodity_sku / warehouse_id / available / reserved / in_transit / snapshot_date`
  - 永久保留（符合 FR-054）
  - 主要用于事后回查 + 积压分析
  - 年增量约 180 万行，5 年内无压力

### 订单同步策略（落地 FR-020 ~ FR-024）

- **列表拉取**：全量拉近 30 天订单（每页 100 条，分页 ~340 次请求/次），落入 `order_header` + `order_item`
- **过滤**：对比 `product_listing.seller_sku` 提取"已配对 SKU 相关订单"的 `(shop_id, amazon_order_id)` 集合
- **详情增量**：仅对已配对相关订单调用订单详情接口拉取邮编，写入 `order_detail`；维护 `order_detail_fetch_log` 避免重复
- **首次回填**：近 30 天订单 × ~100/天 ≈ 3000 订单 → 详情 1 QPS 约 50 分钟
- **日常增量**：每日新订单 ~100 → 详情约 100 秒

### 项目结构

```
restock_system/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI 入口
│   │   ├── config.py         # pydantic-settings
│   │   ├── db/               # SQLAlchemy session + Alembic
│   │   ├── models/           # ORM models
│   │   ├── schemas/          # Pydantic DTOs
│   │   ├── api/              # 路由 (auth/suggestion/config/...)
│   │   ├── saihu/            # 赛狐 API 客户端
│   │   │   ├── client.py     # httpx + sign + 限流
│   │   │   ├── endpoints/    # 各接口封装
│   │   │   └── models.py     # 赛狐返回 DTO
│   │   ├── engine/           # 规则引擎 Step 1-6
│   │   ├── sync/             # 同步任务
│   │   ├── pushback/         # 推送采购单
│   │   ├── tasks/            # APScheduler 任务
│   │   └── core/             # 日志 / 异常 / JWT
│   ├── tests/
│   ├── alembic/
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── .env.example
├── frontend/                 # Vue 3 + Element Plus
├── deploy/
│   ├── docker-compose.yml
│   └── Caddyfile
├── docs/
├── specs/
└── .specify/
```

### 新增 FR（纳入正式条款）

- **FR-067**: 后端 MUST 使用 Python 3.11+ / FastAPI / SQLAlchemy 2.0 async / PostgreSQL 16 技术栈
- **FR-068**: 赛狐 API 客户端 MUST 使用 httpx + aiolimiter（每接口独立 token bucket）+ tenacity（指数退避重试）实现
- **FR-069**: 库存快照 MUST 按"latest 单行 + history 每日归档"双表结构存储；规则引擎只读 latest 表
- **FR-070**: 定时任务 MUST 使用 APScheduler 嵌入 FastAPI 进程作为 Scheduler 层，业务执行交由 `task_run` + Worker 机制（见 FR-058a ~ FR-058h），不引入外部消息队列或任务调度中间件
- **FR-071**: 订单同步 MUST 先全量拉列表到 `order_header/order_item`，再过滤"已配对 SKU 相关订单"后对这些订单增量调用订单详情接口

## Frontend Design Direction

### 技术栈（锁定）
- **框架**：Vue 3（组合式 API）+ Vite
- **组件库**：Element Plus（作为基础组件层，视觉上需深度定制）
- **状态管理**：Pinia
- **路由**：Vue Router
- **HTTP**：axios
- **图标**：Lucide / Iconoir（细线风格，不使用 Element 默认图标）

### 视觉风格
参考 "Ryvix" 风格 dashboard（用户 2026-04-08 提供的参考图），核心特征：

**色板**（design tokens）：
- `--bg-base: #F7F6F2`（奶油米白全局背景）
- `--bg-card: #FFFFFF`
- `--brand-primary: #2D7A6A`（墨绿，主色 / 选中 / CTA / 正向数据）
- `--brand-primary-soft: #E6F4F0`（主色 10% 填充，用于 pastel 徽章）
- `--accent-warm: #F18A65`（珊瑚橙，用于图表对比色与负向/警告数据）
- `--accent-warm-soft: #FDE9DF`
- `--text-primary: #1F2937`
- `--text-secondary: #8B94A3`
- `--border-subtle: #EEF0F4`
- `--shadow-card: 0 2px 8px rgba(0,0,0,0.04)`（极低柔和阴影）

**视觉语言**：
- 卡片圆角 16–20px，按钮/标签使用全圆 pill 形
- 极低阴影（不用深阴影，避免材质感）
- 宽松留白（卡片内部 padding ≥ 24px）
- 细线描边代替强分割线
- 徽章使用 pastel 填充 + 圆角 pill
- 选中态为圆角 pill 背景 + 白色文字
- 表格使用交替行底色 + 大行距 + 细灰列头

**布局**：
- 左侧固定侧栏约 240px（Logo + 主导航 + 次级功能）
- 顶部条含搜索、日期范围、手动刷新、头像
- 内容区响应式网格

### 页面清单（按 spec 的 User Stories 派生）

| # | 页面 | 对应 US | 复杂度 |
|---|---|---|---|
| P1 | 登录页 | - | 低 |
| P2 | 补货建议主列表 | US1 | 高 |
| P3 | 建议单详情/编辑面板 | US1 | 高 |
| P4 | 历史建议查询 | US4 | 中 |
| P5 | SKU 配置 | US2 | 低 |
| P6 | 全局参数 | US2 | 低 |
| P7 | 仓库与国家映射 | US3 | 低 |
| P8 | 邮编规则 | US3 | 中 |
| P9 | 店铺管理 | FR-026 | 低 |
| P10 | 积压提示 | US5 | 低 |
| P11 | 接口监控 | US5 | 中 |
| P12 | 手动触发面板（同步/计算） | - | 低 |

### 信息架构（左侧菜单）

```
📋 补货建议 (P2, P3)
   ├ 当前建议单
   └ 历史记录 (P4)
⚙  配置
   ├ SKU 配置 (P5)
   ├ 全局参数 (P6)
   ├ 仓库与国家 (P7)
   ├ 邮编规则 (P8)
   └ 店铺管理 (P9)
📊 观测
   ├ 积压提示 (P10)
   └ 接口监控 (P11)
🔧 操作 (P12)
```

### 响应式策略
- **桌面优先**：1440×900 为主要设计分辨率
- **适度响应式**：1024 以上保持左侧栏常驻，以下可折叠侧栏；不做完整移动端体验
- 单人内部场景，**无需触屏优化、无需深色模式**

### 国际化与主题
- **仅中文**，不做 i18n 框架（预留字符串常量文件方便未来扩展）
- **不做深色模式**

### 任务进度可视化（FR 要求）
- **手动触发同步/计算** MUST 提供实时进度反馈，展示当前执行阶段（如"拉取产品信息 → 拉取库存 → 拉取订单 → 计算 Step 1 → ... → 完成"）
- 实现方式（plan 阶段敲定）：
  - 方案 A：Server-Sent Events（SSE）后端推送阶段事件
  - 方案 B：前端轮询 `/api/task/status/{task_id}`
  - 推荐方案 B（更简单，符合 YAGNI，单用户轮询成本可忽略）
- 进度展示 UI：步骤条（step indicator）+ 当前步骤动画 + 总耗时

### 新增 FR（纳入正式条款）

- **FR-063**: 前端 MUST 使用 Vue 3 + Element Plus + Pinia + axios 技术栈
- **FR-064**: 前端 MUST 按本章"色板 / 视觉语言 / 布局"章节定义的设计 tokens 实现
- **FR-065**: 手动触发的同步/计算任务 MUST 向用户展示实时执行步骤与进度；长时间任务（>5 秒）MUST 显示当前步骤描述
- **FR-066**: 前端 MUST 为 1024px 及以上分辨率做响应式适配；低于 1024px 时侧栏可折叠但不保证完整可用性

### 实施策略
- 使用 Element Plus 作为组件地基（表格/表单/弹窗等）
- 通过 CSS 变量 + scoped 样式深度定制 Element Plus 默认外观以贴近参考图
- 复杂视觉（图表、步骤动画、徽章）可借助 `frontend-design` skill 与 agent 能力辅助设计还原

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
- "其他出库列表"接口的 `status` 字段过滤（0待确认 / 1已确认）：第一版默认不过滤，后续若发现"待确认"出库单污染在途数据再加过滤
- "在途中"关键字匹配方式：默认走接口服务端搜索 `searchField=remark, searchValue=在途中`（子串匹配）；若匹配精度不符预期，再改为客户端正则过滤
- 赛狐"采购单创建"的完整必填字段验证（当前仅知 4 个必填，supplier/partya 等留空是否可被赛狐接受需联调验证）
- 同一 commoditySku 不同 listing 的 commodityId 一致性（测试数据中未观察到冲突，暂按"任取一个 + 告警"处理）
