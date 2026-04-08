# Phase 0 Research: 赛狐补货计算工具

**Date**: 2026-04-08
**Branch**: 001-saihu-replenishment
**Spec**: [./spec.md](./spec.md)

本阶段的研究任务来自 spec.md 的技术决策点。规格讨论过程中已经对绝大多数技术选型做了充分论证，本文件汇总这些决策并补充实施细节。

---

## R1. 后端语言 / Web 框架

**Decision**: Python 3.11+ / FastAPI 0.115+

**Rationale**:
- 核心工作是 I/O 密集（赛狐 API 调用 1 QPS 限流下的大量等待），`asyncio` + `httpx` 高度契合
- Pydantic v2 对赛狐接口的 80+ 字段返回结构做类型校验，符合"失败快速"原则
- 自动 OpenAPI 文档减少前后端联调成本
- 单机 2C4G 资源足够（FastAPI + PG 实测约 500MB 内存）

**Alternatives considered**:
- **Go (Gin/Echo)**: 单二进制、低内存，但业务代码样板多，1-5 人内部系统无需极致性能
- **Node.js (Fastify)**: async 模型相当，但对 ERP 类数据建模的生态支持弱于 Python
- **SQLite 替代 PG**: JSONB 支持差，UI + 同步任务并发写易锁表

---

## R2. ORM / 迁移

**Decision**: SQLAlchemy 2.0 async + Alembic

**Rationale**:
- SQLAlchemy 2.0 原生 async 支持成熟（async_session/async_scoped_session）
- mypy 类型支持好（配合 `Mapped[T]`），契合宪法 Code Style 门禁
- Alembic 是 SQLA 官方配套，自动迁移生成对本项目 20 张表够用

**Alternatives considered**:
- **SQLModel**: Pydantic + SQLA 合并体，代码更短，但 mypy 支持弱、迭代缓慢
- **Tortoise ORM**: async-native，但生态小、第三方集成少

---

## R3. 赛狐 API 客户端

**Decision**: httpx + aiolimiter（每接口独立 token bucket）+ tenacity（指数退避）+ 自定义签名模块

**Rationale**:
- `httpx.AsyncClient` 支持 HTTP/1.1 + 连接池，能复用连接减少握手开销
- `aiolimiter.AsyncLimiter(max_rate=1, time_period=1)` 每接口独立实例，完美对应"每接口 1 QPS"
- `tenacity` 提供声明式重试策略（指数退避、特定异常触发）
- 签名算法（HmacSHA256 按参数名排序）封装为独立模块 `saihu/sign.py`

**关键设计**:
```python
# 每接口独立 limiter
_limiters: dict[str, AsyncLimiter] = {}

async def call(endpoint: str, body: dict) -> dict:
    limiter = _limiters.setdefault(endpoint, AsyncLimiter(1, 1))
    async with limiter:
        # 签名 + 发请求
        ...
```

**Alternatives considered**:
- **requests + 线程池**: 同步模型不适合大量等待场景
- **全局限流**: 会让慢接口阻塞快接口

---

## R4. 时间字段时区处理

**Decision**: marketplaceId → country → IANA timezone 硬编码映射表；赛狐返回时间按"站点当地"解析，统一转 Asia/Shanghai 存储

**Rationale**:
- 赛狐 test sample 显示 `purchaseDate: "2026-04-08 10:11:15"` 裸时间字符串不带时区信息
- 不同站点订单混合统计时按统一时区才能保证窗口边界一致
- Asia/Shanghai 符合单一采购员的直觉
- `docs/saihu_api/开发指南/站点对应关系.md` 已列 21 个站点，可直接扩展时区列

**实施要点**:
```python
# marketplace.py
MARKETPLACE_TO_COUNTRY: dict[str, str] = {
    "A1VC38T7YXB528": "JP",
    "ATVPDKIKX0DER": "US",
    # ... 21 个站点
}

COUNTRY_TO_TIMEZONE: dict[str, str] = {
    "JP": "Asia/Tokyo",
    "US": "America/Los_Angeles",
    "GB": "Europe/London",
    "DE": "Europe/Berlin",
    # ...
}

def to_beijing(raw: str, marketplace_id: str) -> datetime:
    country = MARKETPLACE_TO_COUNTRY[marketplace_id]
    tz = ZoneInfo(COUNTRY_TO_TIMEZONE[country])
    dt_local = datetime.fromisoformat(raw).replace(tzinfo=tz)
    return dt_local.astimezone(ZoneInfo("Asia/Shanghai"))
```

**Alternatives considered**:
- **假设全部为北京时间**: 简单但跨站点统计错位
- **存 UTC + 显示时转换**: 增加前端复杂度
- **存原始字符串**: 每次查询都要转换，性能与一致性风险

---

## R5. 任务调度 / 执行分层

**Decision**: APScheduler（仅定时入队）+ PostgreSQL task_run 表（队列+历史+进度）+ 单 Worker 异步循环

**Rationale**:
- 符合 YAGNI：不引入 Redis、Celery、RabbitMQ
- Postgres 部分唯一索引 `WHERE status IN ('pending','running')` 天然实现"同键唯一活跃"约束
- `UPDATE ... FOR UPDATE SKIP LOCKED` 保证多 Worker 原子 claim（虽然第一版只有 1 个 Worker）
- 心跳 + 租约机制处理 Worker 异常退出场景
- task_run 表同时承担进度记录，前端轮询 `GET /api/tasks/{id}` 即可

**关键约束 SQL**:
```sql
CREATE UNIQUE INDEX task_run_active_dedupe
ON task_run (dedupe_key)
WHERE status IN ('pending', 'running');
```

**Worker 原子 claim**:
```sql
UPDATE task_run
SET status='running', worker_id=?, started_at=now(),
    heartbeat_at=now(), lease_expires_at=now()+interval '2 minutes',
    attempt_count=attempt_count+1
WHERE id = (
    SELECT id FROM task_run WHERE status='pending'
    ORDER BY priority, created_at
    FOR UPDATE SKIP LOCKED LIMIT 1
)
RETURNING *;
```

**Alternatives considered**:
- **纯 asyncio.Lock**: 不能持久化进度，重启丢失
- **Celery + Redis**: 过度工程化
- **APScheduler 直接执行业务**: 无统一进度入口，UI 难以展示

---

## R6. 订单增量同步策略

**Decision**: `dateType=updateDateTime` + `dateStart = sync_state.last_success_at - 5min` + UPSERT `(shop_id, amazon_order_id)` / `(order_id, order_item_id)`

**Rationale**:
- `updateDateTime` 而不是 `createDateTime` 能捕获退款/取消/发货量变化
- 5 分钟重叠防止边界漏单
- `order_item` 的 `orderItemId` 在订单生命周期内不变，作为 PK 一部分支持稳定 UPSERT

**Alternatives considered**:
- **createDateTime**: 漏掉状态变更
- **增量 + 全量定期对账**: 对账复杂度 > 收益（数据量小）

---

## R7. 订单详情增量拉取

**Decision**: 列表拉全量 → 过滤 "已配对 SKU 相关订单" → 对未拉过详情的订单调用详情接口

**Rationale**:
- 详情接口 1 QPS 是最严格的瓶颈
- 只拉"已配对 SKU 相关"能把 3000 单 × 1s ≈ 50 分钟的首次回填控制在可接受范围
- `order_detail_fetch_log` 表记录 `(shop_id, amazon_order_id)` 已拉列表避免重复

**首次 vs 日常性能**:
- 首次：3000 单 ≈ 50 分钟
- 日常增量：~100 单/天 ≈ 100 秒

---

## R8. 在途数据源

**Decision**: 其他出库列表接口（`searchField=remark, searchValue=在途中`）+ `in_transit_record / in_transit_item` 双表 + `last_seen_at` 老化

**Rationale**:
- 库存明细的 `stockWait` 字段语义不明确（可能包含所有待到货，不只是"在途中"业务标记）
- 用户业务侧明确用"其他出库 + 备注含'在途中'"作为权威来源
- 每次同步前记录 `sync_start_time`，结束后 `UPDATE in_transit_record SET is_in_transit=false WHERE last_seen_at < sync_start_time` 处理"在途中"标签消失场景
- 保留 is_in_transit=false 的记录供审计

**Alternatives considered**:
- **stockWait 字段**: 口径不符，用户否决
- **TRUNCATE + INSERT**: 丢失历史，不便审计

---

## R9. Step 1 velocity 数据源

**Decision**: 从 `order_item` 按日期聚合，公式 `effective = max(quantityShipped - refundNum, 0)`，过滤 `orderStatus ∈ {Shipped, PartiallyShipped}`

**Rationale**:
- 在线产品信息接口的 `day7/14/30SaleNum` 字段未经实测验证，口径不明
- 从订单聚合 → 完全可控的定义（"已发货净数量"）
- 订单本来就为 Step 5 邮编同步，零额外 API 成本

**Alternatives considered**:
- **信任 day*SaleNum**: 风险高，用户否决
- **quantityOrdered - refundNum**: 包含未发货订单，夸大销量
- **quantityShipped without refundNum**: 退货后库存回仓，仍算销量会重复

---

## R10. Step 5 仓内分配

**Decision**: 该 SKU 该国订单的邮编分布（无样本阈值）；零数据兜底为该国已维护海外仓均分

**Rationale**:
- MIN_ORDER_SAMPLE 阈值在小 SKU 场景频繁触发均分，反而丢失有效信号
- 即使 1 单数据也是真实客户地理分布，不应抹掉
- 唯一无法决策的场景是"零样本"（详情未拉、或规则未覆盖），此时均分是合理兜底

**Alternatives considered**:
- **按国家整体订单（方案 Y）**: 丢失 SKU 个性
- **混合方案（Z 三段式）**: 复杂度与收益不成比例

---

## R11. 前端框架

**Decision**: Vue 3 + Element Plus + Pinia + Vite + axios

**Rationale**:
- Source Doc 明确建议 Vue 3 + Element Plus
- Element Plus 的表格 / 表单 / 弹窗 / 树组件开箱即用，适合后台管理系统
- Pinia 是 Vue 3 官方推荐状态管理
- 需要深度 CSS 定制以贴近 Ryvix 风格参考图（通过 SCSS 变量 + scoped 样式）

**Alternatives considered**:
- **React + Ant Design**: 组件生态更大但重
- **Vue 3 + Naive UI**: 更现代但团队熟悉度低
- **纯 Tailwind + 自研组件**: 开发成本过高

---

## R12. 前端视觉风格还原

**Decision**: Ryvix 风格 design tokens（奶油米白 + 墨绿 + 珊瑚橙 + 大圆角 + 低阴影 + 宽松留白）；基于 Element Plus 组件地基深度定制

**Rationale**:
- 用户提供了参考图（两张 Ryvix Dashboard），风格明确
- Element Plus 提供完整组件，降低自研成本
- CSS 变量统一定义 tokens，所有组件 scoped 样式引用 tokens，方便后续主题迭代

**Design Tokens**（见 spec.md Frontend Design Direction 章节）

---

## R13. 前端任务进度轮询

**Decision**: 前端每 2 秒轮询 `GET /api/tasks/{task_id}` 直到终态

**Rationale**:
- 单用户场景，轮询成本可忽略
- 比 SSE/WebSocket 简单得多，符合 YAGNI
- 任务数据落 task_run 表，与 UI 天然一致

**Alternatives considered**:
- **Server-Sent Events**: 需要长连接管理
- **WebSocket**: 单用户场景 overkill

---

## R14. 密码与 JWT

**Decision**: passlib[bcrypt] 单用户密码 hash + python-jose JWT（HS256 + 24h 过期）

**Rationale**:
- 单用户场景不需要 OAuth / SSO
- bcrypt 是行业标准密码 hash
- HS256 + 单密钥足够，不需要 RS256 非对称

---

## R15. 部署方式

**Decision**: Docker Compose 单机（Caddy + Frontend + Backend + Postgres）

**Rationale**:
- 2核4G 轻量服务器足够
- Caddy 自动 HTTPS（Let's Encrypt）免维护
- 单机无需 k8s 的运维复杂度
- `docker compose up -d` 即可启动，回滚也简单

---

## R16. 备份策略

**Decision**: 每日 03:00 `pg_dump` → 上传云对象存储（OSS / COS）→ **永久保留不清理**

**Rationale**:
- 数据量小（预计 1 年内 ≤ 3GB 压缩），对象存储成本极低
- 用户明确要求永久保留（复盘价值优先）
- 恢复流程：下载备份 → `docker compose down` → `pg_restore` → 重启

---

## 研究完成状态

- [x] R1–R16 全部决策有明确来源（spec 讨论记录 + 真实测试样例 + 宪法门禁）
- [x] 无遗留 NEEDS CLARIFICATION
- [x] 可以进入 Phase 1 Design & Contracts
