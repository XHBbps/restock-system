# Quickstart: 赛狐补货计算工具

**Target audience**: 首次部署与上手的采购员 / 运维

## 前置条件

- 云服务器：2核4G / 60GB SSD / Ubuntu 22.04（阿里云轻量 or 腾讯云轻量）
- 域名一个（指向服务器公网 IP）
- 赛狐 ERP OpenAPI 账号：`client_id` + `client_secret`（联系赛狐开通）
- 服务器公网出口 IP 已加入赛狐白名单
- 云对象存储（OSS / COS）bucket，用于每日备份

---

## 1. 服务器初始化

```bash
# 系统更新 + 非 root 用户
apt update && apt upgrade -y
adduser deploy && usermod -aG sudo deploy
su - deploy

# 安装 Docker
curl -fsSL https://get.docker.com | bash
sudo usermod -aG docker deploy

# 国内镜像加速（可选）
sudo mkdir -p /etc/docker
cat | sudo tee /etc/docker/daemon.json <<EOF
{ "registry-mirrors": ["https://docker.mirrors.ustc.edu.cn"] }
EOF
sudo systemctl restart docker

# 时区统一
sudo timedatectl set-timezone Asia/Shanghai
```

---

## 2. 安全组 / 防火墙

仅开放以下端口：

| 端口 | 来源 | 用途 |
|---:|---|---|
| 22 | 你的固定 IP | SSH |
| 80 | 0.0.0.0/0 | HTTP（Let's Encrypt 签发） |
| 443 | 0.0.0.0/0 | HTTPS 主入口 |
| 5432 | **不开放** | Postgres 仅容器内访问 |

---

## 3. 拉取代码 & 配置

```bash
cd /opt
sudo git clone <repo_url> restock
sudo chown -R deploy:deploy restock
cd restock
```

复制并编辑环境变量：

```bash
cp deploy/.env.example deploy/.env
nano deploy/.env
```

`.env` 关键项：
```
# 数据库
DB_PASSWORD=<生成的强密码>

# 赛狐
SAIHU_CLIENT_ID=<赛狐提供>
SAIHU_CLIENT_SECRET=<赛狐提供>
SAIHU_BASE_URL=https://openapi.sellfox.com

# 应用
LOGIN_PASSWORD=<首次登录密码，会 bcrypt hash 后入库>
JWT_SECRET=<openssl rand -base64 32>
APP_TIMEZONE=Asia/Shanghai

# 域名
APP_DOMAIN=your-domain.com

# 备份（可选）
OSS_BUCKET=<your-bucket>
OSS_ACCESS_KEY=<key>
OSS_ACCESS_SECRET=<secret>
```

---

## 4. 启动服务

```bash
cd deploy
docker compose up -d --build
```

首次启动会自动执行 Alembic 迁移建表 + 插入默认 `global_config`。

确认启动：
```bash
docker compose ps
docker compose logs -f backend
```

浏览器访问 `https://your-domain.com` 应看到登录页，Caddy 自动签发 Let's Encrypt 证书。

---

## 5. 首次登录与初始化流程

### 5.1 登录
用 `.env` 里的 `LOGIN_PASSWORD` 登录。登录成功后进入主界面。

### 5.2 按顺序完成初始化（推荐在"操作 → 手动同步/计算"页面逐项触发）

**Step 1 - 同步仓库列表**
- 点"同步仓库" → 观察进度条
- 完成后进入"仓库与国家"页面，为每个仓库手动指定所属国家（二字码：JP/US/GB/...）
- 国内仓会被自动识别（type=1），但如果有多个国内仓也可以统一指定为 `CN`

**Step 2 - 同步店铺列表（可选，指定店铺模式才需要）**
- 在"店铺管理"页点"手动刷新"
- 如果你想限制只拉部分店铺的订单，勾选 `sync_enabled`，然后去"全局参数"把 `shop_sync_mode` 改为 `specific`
- 否则保持默认 `all`，跳过此步

**Step 3 - 同步在线产品信息**
- 点"同步产品" → 系统会拉取所有 `match=true && onlineStatus=active` 的 listing
- 建立 `commoditySku ↔ commodityId` 映射

**Step 4 - 配置 SKU 列表**
- 进入"SKU 配置"页面
- 默认所有同步回来的 SKU 都 `enabled=true`
- 如需临时停用某些 SKU 可以取消勾选
- 可选：为关键 SKU 单独设置 `lead_time_days`（覆盖全局）

**Step 5 - 维护邮编规则**
- 进入"邮编规则"页面
- 按"国家 + 前 N 位 + 比较符 + 比较值 + 仓库"录入规则
- 示例：`JP, 前 2 位, number, >=, 50, 海源仓`；`JP, 前 2 位, number, <, 50, 夏普仓`
- 可调整 `priority` 控制匹配顺序

**Step 6 - 同步库存 / 在途 / 订单**
- 点"同步全部"（或分步点）
- 注意：订单详情首次回填受 1 QPS 限制，近 30 天订单约需 30–60 分钟
- 可在"接口监控"页实时观察调用情况

**Step 7 - 设置全局参数**
- 进入"全局参数"页面
- 设置 `DEFAULT_PURCHASE_WAREHOUSE_ID`（推送采购单的主仓）
- 设置 `INCLUDE_TAX`（"0"/"1"）
- 其他参数保持默认即可（BUFFER_DAYS=30, TARGET_DAYS=60, LEAD_TIME_DAYS=50）

**Step 8 - 首次运行规则引擎**
- 点"立即计算"
- 观察进度条：Step 1 velocity → Step 2 sale_days → ... → Step 6 timing
- 生成后查看"补货建议"列表

---

## 6. 日常使用

### 6.1 自动运行时序
- **每小时**：产品 / 库存 / 在途 / 订单同步
- **每日 02:00**：库存快照归档
- **每日 08:00**：规则引擎自动运行，生成当日建议单

### 6.2 采购员日常操作
1. 上班打开"补货建议"页
2. 查看红色高亮的"立即采购"SKU
3. 逐项核对 / 调整数量或时间
4. 勾选要推送的条目（≤ 50 条/批次）
5. 点"推送至赛狐"
6. 查看推送结果：成功项显示赛狐采购单号，失败项可重试

### 6.3 异常排查
- **同步失败**：进"接口监控"页看哪个接口挂了
- **推送失败**：看 `suggestion_item.push_error`，常见原因：`commodity_id` 未建立、赛狐参数错误
- **task 卡住**：在"任务列表"页看是否有"僵尸" running 任务（1 分钟内会被 reaper 标记 failed）

---

## 7. 数据备份与恢复

### 7.1 自动备份（每日 03:00）
备份脚本在容器内自动运行：
```bash
pg_dump -U postgres replenish > /backup/replenish_$(date +%F).dump
ossutil cp /backup/*.dump oss://${OSS_BUCKET}/backup/
```

### 7.2 手动备份
```bash
docker compose exec db pg_dump -U postgres replenish > backup_$(date +%F).sql
```

### 7.3 恢复
```bash
# 下载备份
ossutil cp oss://bucket/backup/replenish_2026-04-01.dump ./

# 停机恢复
docker compose down
docker volume rm restock_pg_data
docker compose up -d db
sleep 5
docker compose exec -T db psql -U postgres replenish < replenish_2026-04-01.dump

# 重启其他服务
docker compose up -d
```

---

## 8. 升级流程

```bash
cd /opt/restock
git pull
cd deploy
docker compose up -d --build
```

迁移会自动执行。如需回滚：
```bash
git checkout <prev-commit>
docker compose up -d --build
```

---

## 9. 常见问题

### Q: 首次同步订单很慢？
A: 订单详情接口 1 QPS，近 30 天 ~3000 单约 50 分钟，这是预期。可在"接口监控"页观察进度。

### Q: 规则引擎报错 "SKU 无 commodity_id 映射"？
A: 说明该 SKU 尚未在任何仓库同步过，或在线产品信息接口没返回其 commodity_id。先执行"同步产品"与"同步库存"。

### Q: "立即采购" 标签太多？
A: 说明目标天数（默认 60）偏激进。可在"全局参数"提高 `TARGET_DAYS`。

### Q: 账号锁定了怎么办？
A: 等 10 分钟自动解锁，或 SSH 到服务器执行：
```bash
docker compose exec db psql -U postgres replenish -c "UPDATE global_config SET login_failed_count=0, login_locked_until=NULL WHERE id=1;"
```

### Q: 忘记登录密码？
A: 生成新 bcrypt hash 后直接更新数据库：
```bash
# 在服务器上生成 hash
docker compose exec backend python -c "from passlib.hash import bcrypt; print(bcrypt.hash('新密码'))"
# 更新
docker compose exec db psql -U postgres replenish -c "UPDATE global_config SET login_password_hash='<hash>' WHERE id=1;"
```

---

## 10. 性能基线（SC 验证点）

| 指标 | 目标 | 验证方式 |
|---|---|---|
| 登录到建议列表 | ≤ 3s | 浏览器 DevTools |
| 规则引擎单批次 | ≤ 5 分钟 | task_run.finished_at - started_at |
| 同步成功率（周） | ≥ 99% | 接口监控页 |
| 推送成功率 | ≥ 98% | suggestion_item 统计 |
| 稳定运行 | 30 天无重启 | `docker compose ps` + uptime |
| 订单首次回填 | ≤ 1 小时 | task_run |
| 日常订单增量 | ≤ 10 分钟 | task_run |
