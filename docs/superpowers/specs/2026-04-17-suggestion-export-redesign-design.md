# 补货建议单：推送模式 → Excel 导出 + Snapshot 版本化 设计

> 创建日期：2026-04-17
> 状态：Draft（待用户 review）
> 作者：Brainstorming session（基于 7 轮逐项确认）
> 前置上下文：[2026-04-17-deep-audit.md](2026-04-17-deep-audit.md) P0-NEW-2

---

## 1. 背景与动机

### 1.1 现状

当前系统通过 `push_saihu` 任务将补货建议条目推送到赛狐，生成采购单。推送后记录 `saihu_po_number`，依赖赛狐同步回 `in_transit_record` 才能在下一轮计算中被 `load_in_transit` 视为在途。

**已识别问题**（[deep-audit.md P0-NEW-2](2026-04-17-deep-audit.md)）：
- 推送到赛狐回流 `in_transit_record` 有 ~60 分钟 gap 窗口
- 期间若重复触发 calc_engine，已推送 SKU 会被重复报量
- 极端情况下产生重复采购单，影响供应商

### 1.2 产品侧决策

改变补货决策的**交付方式**：
- 不再对接赛狐创建采购单
- 改为**导出 Excel** 给采购员/供应商
- 通过**管理员开关**控制"新一轮补货建议何时生成"
- 每轮采购间隔约 40 天，40 天后前一轮的在途/入库数据已被赛狐正常同步，天然解决去重问题

### 1.3 此设计解决的问题

| 问题 | 如何解决 |
|---|---|
| 推送 gap 导致重复报货 | 删除推送链路；开关机制强制等待业务消化 |
| 推送失败需人工介入 | Excel 导出本地生成，无外部依赖 |
| 已推送条目无法追溯到导出时的上下文 | 引入不可变 Snapshot，完整冻结导出时状态 |
| 重新生成建议会覆盖正在处理的建议单 | 管理员开关作为粗粒度锁 |

---

## 2. 设计目标与非目标

### 2.1 目标

- ✅ 补货建议生成 → 编辑 → 勾选 → 导出 Excel 的闭环
- ✅ 不可变 Snapshot 版本化：同一建议单可产生多个导出快照
- ✅ 管理员开关控制"何时开启新一轮"
- ✅ Excel 多 Sheet 视图（SKU / SKU×国家 / SKU×国家×仓库 / 元信息）
- ✅ 完整审计：谁在何时导出、下载了几次
- ✅ 清理推送赛狐相关的全部代码（pushback / saihu.endpoints.purchase_create）

### 2.2 非目标

- ❌ 不支持回写采购单到赛狐（推送链路完全删除）
- ❌ 不保留历史 pushed 建议单数据（项目未上线，dev 数据可重建）
- ❌ 不做异步队列导出（B2 方案已否决，Excel 规模同步处理足够）
- ❌ 不提供历史 Snapshot 跨建议单的独立列表页（集中在 Tab 内查看）
- ❌ 不做 Snapshot 手动删除（immutable 审计）

---

## 3. 术语表

| 术语 | 定义 |
|---|---|
| **建议单（Suggestion）** | 引擎生成的一次完整补货计算结果，包含多个 SuggestionItem |
| **建议条目（SuggestionItem）** | 单个 SKU 的补货信息，含数量、国家分布、仓库分配 |
| **快照（Snapshot）** | 一次导出创建的不可变数据冻结包，一个建议单可产生多个快照 |
| **生成开关（Generation Toggle）** | 全局布尔开关，控制"生成补货建议"按钮是否可用 |
| **开启新一轮** | 管理员翻开关 ON 的动作，同时归档当前建议单 |

---

## 4. 数据模型变更

### 4.1 `suggestion` 表

```sql
-- 保留字段：id, created_at, triggered_by, global_config_snapshot, 
--          total_items, error_reason 等
-- 删除字段：无（仅修改 status 枚举）
-- 修改字段：status 枚举收缩
--   OLD: draft | partial | pushed | archived | error
--   NEW: draft | archived | error
--
-- 新增字段：archived_at（原有）、archived_by（新）、archived_trigger（新）
ALTER TABLE suggestion 
  ADD COLUMN archived_by INTEGER REFERENCES app_user(id),
  ADD COLUMN archived_trigger VARCHAR(20);  -- 'admin_toggle' | 'manual'
```

### 4.2 `suggestion_item` 表

```sql
-- 删除字段（全部清理）
ALTER TABLE suggestion_item
  DROP COLUMN push_status,
  DROP COLUMN push_error,
  DROP COLUMN push_attempt_count,
  DROP COLUMN push_blocker,
  DROP COLUMN saihu_po_number,
  DROP COLUMN pushed_at;

-- 新增字段
ALTER TABLE suggestion_item
  ADD COLUMN export_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- 值域：'pending' | 'exported'
  ADD COLUMN exported_snapshot_id BIGINT REFERENCES suggestion_snapshot(id),
  ADD COLUMN exported_at TIMESTAMPTZ;

-- 索引
CREATE INDEX ix_suggestion_item_export_status 
  ON suggestion_item (suggestion_id, export_status);
```

### 4.3 `suggestion_snapshot` 表（新增）

```sql
CREATE TABLE suggestion_snapshot (
  id BIGSERIAL PRIMARY KEY,
  suggestion_id INTEGER NOT NULL REFERENCES suggestion(id) ON DELETE CASCADE,
  version INTEGER NOT NULL,  -- 1, 2, 3... 该建议单内递增
  
  -- 审计
  exported_by INTEGER REFERENCES app_user(id),
  exported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  exported_from_ip VARCHAR(45),
  
  -- 内容元数据
  item_count INTEGER NOT NULL,
  note VARCHAR(200),  -- 批次备注（选填）
  global_config_snapshot JSONB NOT NULL,  -- 冻结 target/buffer/lead_time/restock_regions
  
  -- 文件生成
  generation_status VARCHAR(20) NOT NULL DEFAULT 'generating',
    -- 值域：'generating' | 'ready' | 'failed'
  file_path VARCHAR(500),  -- 相对路径，例如 2026/04/补货建议-42-v1-20260417-143052.xlsx
  file_size_bytes BIGINT,
  generation_error TEXT,
  
  -- 下载计数
  download_count INTEGER NOT NULL DEFAULT 0,
  last_downloaded_at TIMESTAMPTZ,
  
  UNIQUE (suggestion_id, version)
);

CREATE INDEX ix_suggestion_snapshot_suggestion ON suggestion_snapshot (suggestion_id);
CREATE INDEX ix_suggestion_snapshot_exported_at ON suggestion_snapshot (exported_at DESC);
```

### 4.4 `suggestion_snapshot_item` 表（新增）

```sql
CREATE TABLE suggestion_snapshot_item (
  id BIGSERIAL PRIMARY KEY,
  snapshot_id BIGINT NOT NULL REFERENCES suggestion_snapshot(id) ON DELETE CASCADE,
  
  -- 核心数据（从 suggestion_item 冻结）
  commodity_sku VARCHAR(100) NOT NULL,
  total_qty INTEGER NOT NULL,
  country_breakdown JSONB NOT NULL,  -- {US: 100, GB: 50, ...}
  warehouse_breakdown JSONB NOT NULL,  -- {US: {WH-1: 60, WH-2: 40}, ...}
  urgent BOOLEAN NOT NULL,
  
  -- 算法快照
  velocity_snapshot JSONB,  -- {US: 1.5, GB: 0.8, ...}
  sale_days_snapshot JSONB,  -- {US: 20, GB: 40, ...}
  
  -- 商品展示冻结（防商品信息事后变化）
  commodity_name VARCHAR(500),
  main_image_url VARCHAR(1000)
);

CREATE INDEX ix_snapshot_item_snapshot ON suggestion_snapshot_item (snapshot_id);
CREATE INDEX ix_snapshot_item_sku ON suggestion_snapshot_item (commodity_sku);
```

### 4.5 `excel_export_log` 表（新增）

```sql
CREATE TABLE excel_export_log (
  id BIGSERIAL PRIMARY KEY,
  snapshot_id BIGINT NOT NULL REFERENCES suggestion_snapshot(id) ON DELETE CASCADE,
  action VARCHAR(20) NOT NULL,  -- 'generate' | 'download'
  performed_by INTEGER REFERENCES app_user(id),
  performed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  performed_from_ip VARCHAR(45),
  user_agent VARCHAR(500)
);

CREATE INDEX ix_export_log_snapshot ON excel_export_log (snapshot_id, performed_at DESC);
```

### 4.6 `global_config` 表扩展

```sql
ALTER TABLE global_config
  ADD COLUMN suggestion_generation_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN generation_toggle_updated_by INTEGER REFERENCES app_user(id),
  ADD COLUMN generation_toggle_updated_at TIMESTAMPTZ;
```

### 4.7 权限体系扩展

现有权限体系：`backend/app/core/permissions.py` 维护 `REGISTRY` 硬编码列表，启动时通过 `permission_sync.py` 自动同步到 DB。

新增 2 个权限码：

```python
# backend/app/core/permissions.py 中新增
RESTOCK_NEW_CYCLE = "restock:new_cycle"
RESTOCK_EXPORT = "restock:export"

# REGISTRY 列表新增（放在 RESTOCK_OPERATE 之后）
PermDef(RESTOCK_EXPORT, "补货发起-导出", "补货发起"),
PermDef(RESTOCK_NEW_CYCLE, "补货发起-开启新一轮", "补货发起"),
```

| 权限码 | 名称 | 分组 | 说明 |
|---|---|---|---|
| `restock:export` | 补货发起-导出 | 补货发起 | 可触发 Excel 导出（独立于 `restock:operate`） |
| `restock:new_cycle` | 补货发起-开启新一轮 | 补货发起 | 可操作生成开关、归档当前单 |

超管角色自动拥有所有权限。其他角色通过 `RoleConfigView` 按需勾选。

---

## 5. 状态机

### 5.1 Suggestion 状态机

```
                 ┌──────────┐
 引擎生成 ──▶ │  draft   │
                 └────┬─────┘
                      │
                      │ 管理员翻开关 ON（有当前单时）
                      ▼
                 ┌──────────┐
                 │ archived │ （终态，可查看不可修改）
                 └──────────┘

                 ┌──────────┐
                 │  error   │ （引擎失败，可查看不可重试，重试走新的 generate）
                 └──────────┘
```

### 5.2 SuggestionItem 导出状态

```
pending ──(所属 item 被勾选导出)──▶ exported（锁定不可编辑）
```

- `exported` 为终态
- 同一 item 不能被导出两次（按 `suggestion_id + item_id` 唯一约束保证）

### 5.3 Snapshot 生成状态

```
generating ──(文件写入成功)──▶ ready
     │
     └──(文件写入失败)──▶ failed（允许重试：删 snapshot 后重新导出）
```

### 5.4 生成开关状态

```
ON ──(首次导出触发)──▶ OFF ──(admin 手动翻 ON)──▶ ON
                                    │
                                    └── 同时归档当前建议单
```

---

## 6. 核心流程

### 6.1 首次生成 + 导出

```
1. 系统初始化：
   global_config.suggestion_generation_enabled = TRUE
   无 suggestion

2. 用户点击"生成补货建议"
   ↓
3. 引擎运行，生成 suggestion (status=draft)
   ↓
4. 用户在详情页编辑、勾选 3 条 item
   ↓
5. 用户点击"导出选中 (3)"
   ↓ 打开导出对话框，填写可选备注
   ↓
6. POST /api/suggestions/{id}/snapshots
   {
     "item_ids": [1, 2, 3],
     "note": "发给供应商 A"
   }
   ↓
7. 后端:
   - 创建 snapshot (version=1, generation_status='generating')
   - 创建 snapshot_item 冻结 3 条 item
   - 更新 suggestion_item.export_status='exported', exported_snapshot_id=1
   - 同步生成 Excel 文件 → file_path
   - 更新 snapshot.generation_status='ready'
   - 若 suggestion_generation_enabled 之前为 TRUE → 翻 FALSE（首次导出触发）
   - 写 excel_export_log(action='generate')
   - 返回 snapshot 信息
   ↓
8. 前端:
   - 显示导出成功
   - Tab 区新增 "快照 v1" Tab
   - 3 条 item 在当前 Tab 内显示"已导出 v1"锁定态
   - "生成补货建议"按钮变灰
   - 管理员在开关区看到开关已翻 OFF
```

### 6.2 继续导出（同一建议单 v2, v3...）

```
1. 用户编辑剩余 pending items
   ↓
2. 勾选另外 5 条 → 导出
   ↓
3. 后端:
   - 创建 snapshot v2
   - 更新 5 条 item 的 export_status
   - 开关已是 OFF，无变化
   ↓
4. 前端新增 "快照 v2" Tab
```

### 6.3 开启新一轮

```
1. 业务消化完毕（~40 天后）
2. 管理员点开关 ON
   ↓ 二次确认对话框
3. PATCH /api/config/generation-toggle
   {
     "enabled": true
   }
   ↓
4. 后端:
   - 若当前有 draft suggestion：
     UPDATE suggestion SET status='archived', 
       archived_by=<user>, archived_trigger='admin_toggle',
       archived_at=now() WHERE status='draft'
   - UPDATE global_config SET suggestion_generation_enabled=TRUE, 
       generation_toggle_updated_by=<user>,
       generation_toggle_updated_at=now()
   ↓
5. 前端刷新:
   - "生成补货建议"按钮恢复可点
   - 归档的建议单移到历史记录页
```

### 6.4 重复下载 Excel

```
1. 用户点 Tab 中的"下载 Excel"
   ↓
2. GET /api/snapshots/{id}/download
   ↓
3. 后端:
   - 读取 snapshot.file_path
   - 流式返回文件
   - 更新 download_count += 1, last_downloaded_at=now()
   - 写 excel_export_log(action='download')
```

### 6.5 删除 draft 建议单（未导出）

```
1. 历史记录页显示 draft 单的"删除"入口
2. DELETE /api/suggestions/{id}
3. 后端校验:
   - suggestion.status 必须是 'draft'
   - 必须无关联 snapshot（count(snapshot WHERE suggestion_id=X) == 0）
   - 不满足 → 409 Conflict
4. 级联删除 suggestion + suggestion_item
```

---

## 7. 权限设计

### 7.1 新增权限码

```python
# backend/app/core/permissions.py
RESTOCK_NEW_CYCLE = "restock:new_cycle"
RESTOCK_EXPORT = "restock:export"
```

### 7.2 作业权限注册表（`backend/app/tasks/access.py`）

| 动作 | 权限码 | 说明 |
|---|---|---|
| 查看建议单 | `restock:view` | 已有 |
| 生成建议单 | `restock:operate` | 已有（需开关为 ON） |
| 编辑建议条目 | `restock:operate` | 已有 |
| **导出 Excel** | `restock:export` | 新增 |
| **翻开关 / 归档** | `restock:new_cycle` | 新增 |
| 删除 draft 单 | `restock:operate` + 无 snapshot | 已有 + 新条件 |

### 7.3 删除作业

从 `access.py` 删除：
```python
"push_saihu": ...  # 整个作业
```

---

## 8. UI/UX 设计

### 8.1 `SuggestionListView`（补货发起页）

```
┌────────────────────────────────────────────────────────┐
│ 补货建议                                                │
│                                                        │
│ ┌─────────────────┐ ┌──────────────────────────┐      │
│ │ 生成补货建议    │ │ [○] 生成开关 (仅 admin) │      │
│ └─────────────────┘ └──────────────────────────┘      │
│                     ↑右侧状态文字："可生成"或"已锁定"  │
│                                                        │
│ [筛选区]  [当前 draft 建议单展示区]                     │
└────────────────────────────────────────────────────────┘
```

**按钮禁用逻辑**：
- `global_config.suggestion_generation_enabled == FALSE` → 按钮 disabled
  - Tooltip："当前建议单已导出，请联系管理员开启新一轮"
- 无当前 draft 且开关 ON → 可点击，触发引擎

**开关可见性**：
- 有 `restock:new_cycle` 权限 → 显示 `el-switch` + 右侧状态文字
- 无权限 → 仅显示按钮

### 8.2 `SuggestionDetailView`（建议单详情页）

```
┌────────────────────────────────────────────────────────┐
│ 建议单 #42                                   [导出 (3)]│
│ ┌─────┬───────┬───────┬───────┐                        │
│ │当前 │v1     │v2     │+ v3等 │  ← Tab 栏              │
│ ├─────┴───────┴───────┴───────┘                        │
│ │                                                      │
│ │ [当前 Tab]：live items 表格（pending 可编辑 /         │
│ │             exported 锁定 + 标 "已导出 v1"）           │
│ │                                                      │
│ │ [v1 Tab]：                                            │
│ │   snapshot 元信息（导出时间、导出人、备注）            │
│ │   [下载 Excel] (已下载 5 次)                          │
│ │   冻结 items 列表（只读）                             │
│ └──────────────────────────────────────────────────────┘
```

### 8.3 导出对话框

```
┌────────────────────────────────┐
│ 导出补货建议 Excel              │
│                                │
│ 将导出 3 条 SKU                │
│                                │
│ 批次备注（可选，≤ 200 字符）：  │
│ ┌──────────────────────────┐   │
│ │ 发给 A 供应商             │   │
│ └──────────────────────────┘   │
│                                │
│          [取消]  [确认导出]    │
└────────────────────────────────┘
```

### 8.4 开关二次确认

```
┌──────────────────────────────────────────┐
│ ⚠️ 确认开启新一轮补货建议生成            │
│                                          │
│ 此操作将：                                │
│ • 归档当前建议单（#42）                   │
│ • 现有 3 个快照保留可下载，但不可再新增   │
│ • 生成按钮恢复可点击                      │
│                                          │
│ 归档后不可撤销。确认继续？                │
│                                          │
│              [取消]  [确认开启]           │
└──────────────────────────────────────────┘
```

### 8.5 `HistoryView`（历史记录页）调整

表格列：
- 建议单 ID
- 状态（draft / archived / error）
- 生成时间
- 触发方式
- **快照数量**（可点击展开）
- 操作（删除按钮：仅 draft + 无 snapshot 时显示）

展开行：
```
└─ 快照 v1 · 导出于 2026-04-15 10:30 · 导出人 alice · 下载 3 次 · 备注 "A 供应商" · [下载]
└─ 快照 v2 · 导出于 2026-04-16 14:12 · 导出人 bob   · 下载 1 次 · 备注 ""         · [下载]
```

---

## 9. Excel 导出设计

### 9.1 文件命名

```
补货建议-{suggestion_id}-v{version}-{YYYYMMDD-HHmmss}.xlsx
```

示例：`补货建议-42-v1-20260417-143052.xlsx`

### 9.2 存储路径

```
deploy/data/exports/{yyyy}/{mm}/<filename>
```

- 挂载为 Docker volume
- `suggestion_snapshot.file_path` 存相对路径（`2026/04/补货建议-42-v1-20260417-143052.xlsx`）
- 永不自动清理（与 snapshot 生命周期绑定）

### 9.3 Sheet 结构

**Sheet 1 — SKU 汇总**

| SKU | 商品名 | 主图 | 总采购量 | 紧急 | 备注 |
|---|---|---|---|---|---|
| SKU-A | 商品 A | (URL 或嵌入) | 150 | ✓ | ... |

**Sheet 2 — SKU × 国家**

| SKU | 商品名 | 国家 | 补货量 | 可售天数 | 日均销量 |
|---|---|---|---|---|---|
| SKU-A | 商品 A | US | 100 | 20 | 1.5 |
| SKU-A | 商品 A | GB | 50 | 40 | 0.8 |

**Sheet 3 — SKU × 国家 × 仓库**

| SKU | 商品名 | 国家 | 仓库 ID | 仓库名 | 分配量 |
|---|---|---|---|---|---|
| SKU-A | 商品 A | US | WH-1 | 加州仓 | 60 |
| SKU-A | 商品 A | US | WH-2 | 纽约仓 | 40 |
| SKU-A | 商品 A | GB | WH-5 | 伦敦仓 | 50 |

**Sheet 4 — 导出元信息**

```
字段              值
──────────────────────────────────────
建议单 ID         42
快照版本          v1
导出时间          2026-04-17 14:30:52
导出人            alice
批次备注          发给 A 供应商
───────────────────────────────────────
全局参数（冻结）
  target_days     30
  buffer_days     7
  lead_time_days  14
  restock_regions [US, GB]
───────────────────────────────────────
总 SKU 数         3
总补货量          150
```

### 9.4 生成实现

- 使用 `openpyxl` 库（已在 `backend/pyproject.toml`? 需确认/添加）
- 同步生成，5 秒内完成
- 并发保护：`snapshot.generation_status='generating'` + 应用层串行化
- 生成失败 → snapshot.generation_status='failed'，用户可删除 snapshot 后重试

### 9.5 下载

- `GET /api/snapshots/{id}/download` 流式返回文件
- `Content-Disposition: attachment; filename="补货建议-42-v1-20260417-143052.xlsx"`
- 下载成功后更新 `download_count` 和 `excel_export_log`

---

## 10. 迁移策略（方案 1：清空重来）

### 10.1 前提

- 项目**未上线**，无真实生产数据
- 本地/测试库可随时重建

### 10.2 Migration SQL

`backend/alembic/versions/20260418_1000_redesign_to_export_model.py`

```sql
-- 1. 清空旧数据
DELETE FROM suggestion_item;
DELETE FROM suggestion;

-- 2. 删除旧字段（suggestion_item）
ALTER TABLE suggestion_item
  DROP COLUMN push_status,
  DROP COLUMN push_error,
  DROP COLUMN push_attempt_count,
  DROP COLUMN push_blocker,
  DROP COLUMN saihu_po_number,
  DROP COLUMN pushed_at,
  DROP COLUMN commodity_id;  -- 赛狐内部 ID，仅用于推送，不再需要

-- 3. 新增字段（suggestion_item）
ALTER TABLE suggestion_item
  ADD COLUMN export_status VARCHAR(20) NOT NULL DEFAULT 'pending' 
    CHECK (export_status IN ('pending', 'exported')),
  ADD COLUMN exported_snapshot_id BIGINT,
  ADD COLUMN exported_at TIMESTAMPTZ;

CREATE INDEX ix_suggestion_item_export_status 
  ON suggestion_item (suggestion_id, export_status);

-- 4. suggestion.status 枚举收缩
ALTER TABLE suggestion DROP CONSTRAINT IF EXISTS ck_suggestion_status;
ALTER TABLE suggestion ADD CONSTRAINT ck_suggestion_status 
  CHECK (status IN ('draft', 'archived', 'error'));

-- 5. suggestion 新增归档字段
ALTER TABLE suggestion
  ADD COLUMN archived_by INTEGER REFERENCES app_user(id),
  ADD COLUMN archived_trigger VARCHAR(20);

-- 6. 新表
CREATE TABLE suggestion_snapshot (...);
CREATE TABLE suggestion_snapshot_item (...);
CREATE TABLE excel_export_log (...);

-- 7. 外键补齐（建表后）
ALTER TABLE suggestion_item
  ADD CONSTRAINT fk_exported_snapshot 
  FOREIGN KEY (exported_snapshot_id) REFERENCES suggestion_snapshot(id);

-- 8. global_config 扩展
ALTER TABLE global_config
  ADD COLUMN suggestion_generation_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN generation_toggle_updated_by INTEGER REFERENCES app_user(id),
  ADD COLUMN generation_toggle_updated_at TIMESTAMPTZ;

-- 9. 新权限码插入（若使用 DB 管理权限）
-- 注：现有权限体系若是硬编码，则在 permissions.py 中增加即可
```

### 10.3 downgrade

```sql
-- 仅恢复表结构，不恢复数据
-- AGENTS.md 已写明"alembic 不自动 downgrade"，此处 downgrade 仅用于开发时回滚
```

---

## 11. 僵尸代码清理清单

### 11.1 后端

**直接删除**：
- `backend/app/pushback/purchase.py`
- `backend/app/pushback/__init__.py`（若目录留空）
- `backend/app/saihu/endpoints/purchase_create.py`

**修改**：
- `backend/app/tasks/access.py`：
  - 删除 `push_saihu` 从 `TASK_VIEW_PERMISSIONS` 和 `TASK_MANAGE_PERMISSIONS`
- `backend/app/main.py`：
  - 删除 push_saihu 相关的 job register（若有）
- `backend/app/api/suggestion.py`：
  - 删除 `POST /api/suggestions/{id}/push` 端点
  - 删除 `push_items()` 函数
  - 新增 `POST /api/suggestions/{id}/snapshots` 端点
  - 新增 `DELETE /api/suggestions/{id}` 的 snapshot 数量校验
- `backend/app/core/commodity_id.py`：
  - **整个文件删除**。`commodity_id` 是赛狐内部 ID，仅用于推送场景。推送删除后无业务用途。
  - `suggestion_item.commodity_id` 字段也从模型删除（本次 migration 一并处理）
- `backend/app/engine/runner.py`：
  - `_archive_active` 改为不在引擎内部触发，改由开关翻 ON 时触发
  - 删除 `resolve_commodity_id_map` 调用与 `push_blocker` 相关写入
- `backend/app/engine/step2_sale_days.py`：
  - `load_in_transit` 保持只读 `in_transit_record`，不改动（40 天机制天然解决去重）

### 11.2 前端

**直接删除**：
- `frontend/src/api/suggestion.ts` 中 `pushSuggestion()` 函数
- `frontend/src/views/SuggestionListView.vue` 中"批量推送"按钮 / 推送状态筛选 / push_blocker 标签

**修改**：
- `frontend/src/views/SuggestionDetailView.vue`：
  - "批量推送" → "导出选中"
  - 新增 Tab 组件展示 snapshot 列表
- `frontend/src/views/HistoryView.vue`：
  - 新增"快照数量"列 + 展开行
  - 删除按钮的条件改为 `status == 'draft' && snapshot_count == 0`
- `frontend/src/utils/status.ts`：
  - 删除 `push_status` 映射
  - 新增 `export_status` 映射

### 11.3 测试

**删除**：
- `backend/tests/unit/test_pushback_*.py`
- `backend/tests/unit/test_saihu_purchase_create.py`
- `backend/tests/unit/test_suggestion_patch.py` 中 push 相关用例

**新增**：
- `test_snapshot_creation.py` — 创建 snapshot + 冻结 items
- `test_snapshot_excel_export.py` — Excel 文件生成内容正确性
- `test_snapshot_download.py` — 下载计数 + 日志
- `test_generation_toggle.py` — 开关逻辑
- `test_suggestion_deletion.py` — 删除校验
- `frontend/src/views/__tests__/SuggestionDetailView.test.ts` — Tab 切换 + 导出对话框

### 11.4 文档

- `docs/PROGRESS.md`：新增 §3.47 记录本次重构
- `docs/Project_Architecture_Blueprint.md`：
  - §3.1（引擎）移除"去重基于已推送建议"段落
  - §3.3（任务队列）移除 `push_saihu` 作业
  - §8 新增 ADR：ADR-7 "导出 Excel 替代推送赛狐"
- `docs/runbook.md`：新增"开关状态异常排障"
- `docs/deployment.md`：新增 `deploy/data/exports/` 目录挂载说明

---

## 12. 测试策略

### 12.1 单元测试（新增）

| 模块 | 测试点 |
|---|---|
| `snapshot.py` 创建逻辑 | version 递增、冻结字段一致、并发防重复 |
| Excel 生成 | 多 Sheet 结构、字段正确、国家/仓库分量之和 |
| 开关翻转 | 首次导出自动 OFF、admin 翻 ON 归档 |
| 删除 draft | 无 snapshot 可删、有 snapshot 拒绝 |
| 权限 | `restock:export` / `restock:new_cycle` 校验 |
| 下载计数 | download_count + 日志正确 |

### 12.2 集成测试

- 完整闭环：生成 → 编辑 → 导出 v1 → 继续编辑 → 导出 v2 → admin 翻开关 → 生成新单

### 12.3 前端测试

- 开关可见性（有/无 `new_cycle` 权限）
- Tab 切换（live / snapshot v1 / snapshot v2）
- 导出对话框（备注填入）
- 二次确认对话框
- 下载按钮

### 12.4 验收标准

- 后端 `pytest` 全绿（新增用例 + 保留用例）
- 前端 `vue-tsc + vite build + vitest` 全绿
- 手动 E2E：本地跑一次完整闭环
- Migration：全新 DB `alembic upgrade head` 成功，`alembic downgrade -1` 成功

---

## 13. 风险与开放问题

### 13.1 已知风险

| 风险 | 缓解 |
|---|---|
| Excel 生成阻塞请求线程（同步方案 B3） | 规模小（数千行 < 5 秒），超时风险低 |
| 文件系统空间膨胀 | 5 年 × 12 个月 × 2 次/月 ≈ 120 文件，每个 < 1MB，总量可控 |
| Snapshot item 数据冗余 | 小数据量可接受，换取审计完整性 |
| admin 误翻 ON 开关 | 二次确认对话框 + 操作日志（`generation_toggle_updated_by/at`） |
| Snapshot 生成失败 | `generation_status='failed'` + 允许重试 |

### 13.2 开放问题（spec review 时可能讨论）

1. **是否需要"再次生成已导出条目"**？
   - 当前设计：exported 是终态，item 锁定
   - 潜在需求：采购员发现 Excel 错了要改——现在必须整单归档重来
   - 暂定：不支持（简化 UX），遇到错误可以删除 snapshot + 重开新建议
2. **Excel 字段国际化**？
   - 当前：中文列名
   - 如果未来扩展海外使用，需要 i18n——暂不考虑
3. **Snapshot `note` 是否需要后续编辑**？
   - 当前：只读（因为 snapshot 整体 immutable）
   - 如果需要：新增 `note_history` 或改为 live note——暂定只读

### 13.3 与其他设计的关联

- **P0-NEW-2（PO → in_transit 映射缺失）**：彻底解决（推送链路删除）
- **P1-NEW-1（SuggestionListView 全量加载）**：不受影响，独立优化
- **`deep-audit.md` 其他项**：不受影响

---

## 14. 估算

### 14.1 工作量分解

| 任务 | 工作量 |
|---|---|
| Migration SQL + alembic 脚本 | 0.5 天 |
| 数据模型代码（models/schemas） | 0.5 天 |
| API 层（suggestions 新端点 + 删除 push） | 1 天 |
| Excel 生成逻辑（openpyxl） | 1 天 |
| 开关逻辑 + global_config 扩展 | 0.5 天 |
| 权限码接入 | 0.5 天 |
| 前端 SuggestionListView（开关） | 0.5 天 |
| 前端 SuggestionDetailView（Tab + 导出对话框） | 1.5 天 |
| 前端 HistoryView 调整 | 0.5 天 |
| 后端单测 + 集成测 | 1 天 |
| 前端 Vitest 补全 | 0.5 天 |
| pushback / purchase_create 清理 | 0.5 天 |
| 文档同步（PROGRESS / Blueprint / runbook） | 0.5 天 |
| **合计** | **约 9 人天** |

### 14.2 里程碑建议

建议拆分为 3 个实施 plan：

- **Plan A — 后端基础**（3 天）：migration + 模型 + API + Excel 生成
- **Plan B — 前端改造**（3 天）：三个 view 改造 + 对话框 + 测试
- **Plan C — 清理 + 文档**（2 天）：pushback 删除 + 文档同步 + 端到端验证

每个 plan 独立可验收，降低单次 PR 复杂度。

---

## 15. 下一步

1. **用户 review 本 spec**（等待确认或修改）
2. spec 通过后，运行 `superpowers:writing-plans` 生成 Plan A 的实施计划
3. Plan A 实施完成并验收后，继续 Plan B / Plan C

---

## 附录 A：API 端点清单

### 新增

| Method | Path | 权限 | 说明 |
|---|---|---|---|
| POST | `/api/suggestions/{id}/snapshots` | `restock:export` | 创建 snapshot + 生成 Excel |
| GET | `/api/suggestions/{id}/snapshots` | `restock:view` | 列出该建议单的所有 snapshot |
| GET | `/api/snapshots/{id}` | `restock:view` | 单个 snapshot 详情 |
| GET | `/api/snapshots/{id}/items` | `restock:view` | snapshot 冻结的 items |
| GET | `/api/snapshots/{id}/download` | `restock:export` | 下载 Excel |
| PATCH | `/api/config/generation-toggle` | `restock:new_cycle` | 翻开关（同时触发归档） |
| GET | `/api/config/generation-toggle` | `restock:view` | 查询开关状态 |

### 删除

| Method | Path | 原因 |
|---|---|---|
| POST | `/api/suggestions/{id}/push` | 不再推送赛狐 |

### 修改

| Method | Path | 修改 |
|---|---|---|
| DELETE | `/api/suggestions/{id}` | 新增"无 snapshot"前置校验 |
| GET | `/api/suggestions` | 响应中新增 `snapshot_count` 字段 |

---

## 附录 B：文件变动清单（实施阶段参考）

### 新增文件

- `backend/alembic/versions/20260418_*_redesign_to_export_model.py`
- `backend/app/models/suggestion_snapshot.py`
- `backend/app/models/excel_export_log.py`
- `backend/app/schemas/suggestion_snapshot.py`
- `backend/app/api/snapshot.py`（独立文件，snapshot 相关端点聚合；与 suggestion.py 解耦方便维护）
- `backend/app/services/excel_export.py`（Excel 生成工具）
- `backend/tests/unit/test_snapshot_*.py`
- `frontend/src/api/snapshot.ts`
- `frontend/src/components/SnapshotTab.vue`
- `frontend/src/components/ExportDialog.vue`
- `frontend/src/components/GenerationToggle.vue`

### 删除文件

- `backend/app/pushback/purchase.py`
- `backend/app/saihu/endpoints/purchase_create.py`
- `backend/tests/unit/test_pushback_*.py`
- `backend/tests/unit/test_saihu_purchase_create.py`

### 修改文件

- `backend/app/api/suggestion.py`
- `backend/app/core/permissions.py`
- `backend/app/tasks/access.py`
- `backend/app/engine/runner.py`
- `backend/app/models/suggestion.py`
- `backend/app/models/global_config.py`
- `frontend/src/views/SuggestionListView.vue`
- `frontend/src/views/SuggestionDetailView.vue`
- `frontend/src/views/HistoryView.vue`
- `frontend/src/api/suggestion.ts`
- `frontend/src/utils/status.ts`
- `docs/PROGRESS.md`
- `docs/Project_Architecture_Blueprint.md`

---

**Spec END**
