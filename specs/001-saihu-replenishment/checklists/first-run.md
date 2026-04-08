# 首次启动验证清单

**Purpose**: 实施完成后，第一次拉起系统的逐项验证 Checklist
**Owner**: 部署/运维（采购员可参与 5 与 6）
**Estimated time**: 完整跑一遍约 60–90 分钟（不含订单首次回填）

> 完成顺序与「Phase 检查」按从上到下执行。每完成一条勾上 `[X]`。

---

## Phase 0 — 本地构建预检（无需服务器）

目标：保证代码层面无明显错误后再上服务器。

### 0.1 后端工具链
- [ ] `cd backend && python -m venv .venv && source .venv/Scripts/activate`（Windows: `.venv\Scripts\activate`）
- [ ] `pip install -e ".[dev]"` 全部成功
- [ ] `pre-commit install` 安装钩子
- [ ] `ruff check .` 全部通过（**T137**）
- [ ] `black --check .` 全部通过（**T137**）
- [ ] `mypy app` 全部通过（**T136**）
- [ ] `pytest tests/unit -v` ≥ 50 个用例全部 PASS（覆盖签名、Step1/3/4/5、邮编匹配器）

### 0.2 前端工具链
- [ ] `cd frontend && npm install` 全部成功
- [ ] `npm run lint` `--max-warnings=0` 通过（**T139**）
- [ ] `npm run type-check` `vue-tsc --noEmit` 通过（**T138**）
- [ ] `npm run build` 生产构建成功
- [ ] 构建产物 `dist/assets/` 中首屏 JS gzip 后 < 250KB（用 `gzip -c file.js | wc -c` 验证）

### 0.3 部署配置预检
- [ ] `docker compose -f deploy/docker-compose.yml config` 无报错
- [ ] `.gitignore` 中含 `.env` 防止泄漏
- [ ] `deploy/.env.example` 已复制为 `deploy/.env` 并填写：
  - `APP_DOMAIN`（域名）
  - `DB_PASSWORD`（强密码）
  - `SAIHU_CLIENT_ID` / `SAIHU_CLIENT_SECRET`
  - `LOGIN_PASSWORD`（首次登录密码）
  - `JWT_SECRET`（`openssl rand -base64 32`）

---

## Phase 1 — 服务器部署（VPS 上执行）

### 1.1 服务器初始化
- [ ] 系统时区 `Asia/Shanghai`：`timedatectl set-timezone Asia/Shanghai`
- [ ] Docker 已安装：`docker --version`、`docker compose version`
- [ ] 防火墙仅开放 22/80/443，**不暴露 5432**
- [ ] 服务器公网 IP **已加入赛狐 OpenAPI 白名单**
- [ ] 域名 A 记录指向服务器 IP

### 1.2 拉起容器栈
- [ ] `cd /opt/restock && git pull`
- [ ] `cd deploy && docker compose up -d --build`
- [ ] `docker compose ps` 显示 4 个服务全部 `Up (healthy)`：caddy / db / backend / frontend
- [ ] `docker compose logs backend --tail 50` 看到：
  - `app_starting` → `global_config_seeded`（首次）→ `worker_started` → `reaper_started` → `scheduler_started` → `app_started`

### 1.3 HTTPS 与基础探活
- [ ] 浏览器访问 `https://your-domain.com` 返回登录页（Caddy 自动签发了 Let's Encrypt 证书）
- [ ] `curl -s https://your-domain.com/healthz` 返回 `{"status":"ok"}`
- [ ] `curl -s https://your-domain.com/docs` 返回 FastAPI Swagger HTML

---

## Phase 2 — 鉴权与基础 API

### 2.1 登录（**FR-039 ~ 041**）
- [ ] 用 `LOGIN_PASSWORD` 登录成功，返回 `access_token`
- [ ] 故意输错密码 5 次，第 6 次返回 423 锁定 10 分钟
- [ ] 等待 10 分钟后自动解锁，可正常登录
- [ ] 登录后 token 在前端 localStorage 持久化

### 2.2 任务系统空跑
- [ ] `POST /api/tasks` 入队 `{"job_name":"echo","payload":{"hi":1}}` 返回 task_id
- [ ] `GET /api/tasks/{task_id}` 几秒内 status → success
- [ ] 重复入队同一任务时 → 命中 dedupe → 返回 existing=true 复用 task_id

### 2.3 调度器存活
- [ ] 容器内 `docker compose exec backend python -c "from app.tasks.scheduler import setup_scheduler; print(setup_scheduler().get_jobs())"` 列出 8 个 job（hourly 5 个 + warehouse + archive + calc_engine）

---

## Phase 3 — 赛狐接口对齐（**有真实赛狐凭证**）

### 3.1 Token 获取
- [ ] 首次任意业务调用触发 token 获取，`docker compose logs backend | grep saihu_token_refresh_ok`
- [ ] `SELECT * FROM access_token_cache;` 看到一行带 `expires_at` 的记录（约 24h 后）

### 3.2 单接口手动同步
**进入"操作 → 手动同步/计算"页**，逐个触发并观察结果：

- [ ] **同步仓库列表**：进度条完成 → 进入"配置 → 仓库与国家"看到全部仓库（带"待指定国家"标记）
- [ ] 为每个仓库手动指定 country（CN / JP / US / ...）
- [ ] **同步在线产品信息**：进度更新 → 进入数据库 `SELECT count(*) FROM product_listing;` 看到实际记录数
- [ ] 验证 product_listing.commodity_id 字段非空（推送采购单依赖此）
- [ ] **同步库存明细**：`SELECT count(*) FROM inventory_snapshot_latest;` > 0
- [ ] **同步在途**：`SELECT count(*) FROM in_transit_record WHERE is_in_transit=true;` > 0（如果赛狐侧有在途单）
- [ ] **同步订单列表 + 详情**（首次回填，约 50 分钟）：
  - 进度条实时更新，看到"已处理 N 单"
  - **T142**：从开始到结束 ≤ 1 小时
  - 完成后 `SELECT count(*) FROM order_header;` ≈ 近 30 天订单数
  - `SELECT count(*) FROM order_detail WHERE postal_code IS NOT NULL;` > 0

### 3.3 接口监控页
- [ ] 进入"观测 → 接口监控"
- [ ] 看到每个接口的卡片：调用次数、24h 成功率、最近调用时间
- [ ] **如有失败**：可点"重试"按钮入队新任务

---

## Phase 4 — 邮编规则配置（采购员）

### 4.1 配置规则
- [ ] 进入"配置 → 邮编规则"页
- [ ] 新增至少一条规则：例 `JP / 前2位 / number / >= / 50 / 海源仓 / priority=10`
- [ ] 新增配套规则：`JP / 前2位 / number / < / 50 / 夏普仓 / priority=20`
- [ ] 列表按 priority 升序显示
- [ ] 编辑/删除按钮可正常工作

### 4.2 全局参数
- [ ] 进入"配置 → 全局参数"
- [ ] 设置 `default_purchase_warehouse_id` = 实际国内中心仓 id
- [ ] 设置 `include_tax` = `0` 或 `1`
- [ ] 保存成功

---

## Phase 5 — 规则引擎运行（最关键验证）

### 5.1 触发计算（**T141**）
- [ ] 进入"操作 → 手动同步/计算"
- [ ] 点"运行规则引擎"
- [ ] 进度条依次显示：Step 1 velocity → Step 2 sale_days → Step 3 各国补货量 → Step 4 总采购量 → Step 5 仓内分配 → Step 6 持久化建议单 → 完成
- [ ] **T141**：500 SKU 规模下 ≤ 5 分钟完成

### 5.2 查看建议单
- [ ] 进入"补货建议 → 当前建议单"
- [ ] 看到生成的建议条目，按"最早 T_采购"升序排列
- [ ] **立即采购**条目红色高亮
- [ ] 列表展示 SKU 名/图、总采购量、各国分布、最早采购日期、状态
- [ ] 点"详情"展开可看到：
  - 各国分量
  - 各仓分量
  - T_采购 / T_发货 各国
  - 积压国家列表（如有）
- [ ] **T140**：浏览器 DevTools Performance 测量首屏：FCP < 1.5s，LCP < 2.5s
- [ ] DevTools Network 检查 main bundle gzip 后 < 250KB

### 5.3 编辑建议
- [ ] 在详情页修改某条 total_qty
- [ ] 保存成功，列表更新
- [ ] 输入负数时收到错误（PATCH 校验）

### 5.4 推送至赛狐
- [ ] 在列表勾选 ≤ 50 条建议
- [ ] 点"推送至赛狐 (N)" → 弹窗确认
- [ ] 任务进度条出现，最终成功
- [ ] 失败的条目可在监控页看到原因
- [ ] **赛狐 ERP Web 端**确认：对应采购单已生成，单号与系统记录一致

---

## Phase 6 — 历史与积压

### 6.1 历史查询（US4）
- [ ] 第二天再触发一次引擎（或等次日 08:00 自动）
- [ ] 进入"补货建议 → 历史记录"
- [ ] 选择日期范围/状态过滤
- [ ] 看到前一天的建议单，点详情进入只读视图

### 6.2 积压提示（US5）
- [ ] 进入"观测 → 积压提示"
- [ ] 如有 velocity=0 + 库存>0 的 SKU → 看到列表
- [ ] 点"标为已处理" → 默认列表中消失
- [ ] 切换"显示已处理"→ 重新出现

### 6.3 接口监控持续观测
- [ ] 接口监控页每个接口 24h 成功率显示正常
- [ ] 如订单 > 50 天未拉详情 → 顶部黄色 alert（FR-004 合规警告）

---

## Phase 7 — 自动化任务验证

### 7.1 定时同步
- [ ] 等待 1 小时（或调小 sync_interval_minutes）
- [ ] 观察 `task_run` 表新增 scheduler 触发的任务
- [ ] `SELECT * FROM sync_state;` 各 job_name 的 last_success_at 在更新

### 7.2 每日 02:00 归档
- [ ] 等到次日凌晨或临时手工触发：
  ```bash
  docker compose exec backend python -c "
  import asyncio
  from app.tasks.queue import enqueue_task
  from app.db.session import async_session_factory
  async def main():
      async with async_session_factory() as db:
          await enqueue_task(db, job_name='daily_archive', trigger_source='manual')
  asyncio.run(main())
  "
  ```
- [ ] `SELECT count(*) FROM inventory_snapshot_history WHERE snapshot_date = CURRENT_DATE;` > 0

### 7.3 每日 08:00 规则引擎
- [ ] 等到次日 08:00 → `task_run` 看到 scheduler 触发的 calc_engine 任务
- [ ] 自动归档前一份 draft 建议单
- [ ] 生成新建议单

### 7.4 备份脚本
- [ ] 在服务器 crontab 加：
  ```
  0 3 * * * /opt/restock/deploy/scripts/pg_backup.sh >> /var/log/restock_backup.log 2>&1
  ```
- [ ] 手动跑一次：`bash /opt/restock/deploy/scripts/pg_backup.sh`
- [ ] `ls /opt/restock/deploy/data/backup/` 看到 `replenish_*.sql.gz`
- [ ] 如配置 OSS：`ossutil ls oss://${OSS_BUCKET}/backup/` 看到上传文件

---

## Phase 8 — 30 天稳定性观测（**T143**）

### 8.1 一周后
- [ ] `docker compose ps` 全部仍 `healthy`
- [ ] `docker compose logs backend --tail 200` 无重复 ERROR
- [ ] 接口监控页一周成功率 ≥ 99%（**SC-003**）
- [ ] 推送成功率 ≥ 98%（**SC-005**）

### 8.2 一个月后
- [ ] 容器从未自动重启（`docker compose ps` 看 STATUS 列的 Up 时长）
- [ ] `task_run` 表无积压僵尸任务（`status='running'` 且 lease_expires_at < now() 的记录数 = 0）
- [ ] **SC-007 满足**：30 天稳定无人工重启

---

## 异常排查参考

| 现象 | 可能原因 | 排查 |
|---|---|---|
| 登录 423 但密码正确 | failed_count 累积 | `UPDATE global_config SET login_failed_count=0, login_locked_until=NULL WHERE id=1;` |
| 同步任务一直 pending | Worker 没启动 | `docker compose logs backend` 看 `worker_started` 日志 |
| 任务卡 running | 心跳/租约异常 | reaper 60s 后会标记 failed |
| 赛狐 40005 IP 不在白名单 | 服务器 IP 变了 | 联系赛狐重新加白 |
| 赛狐 40019 限流 | 限流器失效 | 重启 backend |
| 推送 40014 includeTax 不合法 | global_config.include_tax 不是 "0"/"1" | UPDATE 修正 |
| 建议单为空 | sku_config 中无 enabled SKU | 检查"配置→SKU 配置" |
| 积压表为空 | 无 velocity=0 SKU 或同步未跑 | 先跑产品+库存+引擎 |

---

## 完成定义

满足以下三条即视为「首次启动验证完成」：

1. ✅ Phase 0 + 1 + 2 全部勾选（核心通路打通）
2. ✅ Phase 5 完整跑通至少 1 次（端到端业务流验证）
3. ✅ Phase 8 一周后无重大问题（短期稳定性）

完整 30 天 Phase 8 完成后，即满足 **SC-007** 验收条件，整个 spec 验收完成。
