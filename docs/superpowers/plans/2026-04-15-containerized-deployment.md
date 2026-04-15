# 容器化部署补齐 + 首次部署指南

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐容器化部署的最后缺口（服务器初始化脚本 + 数据目录预创建 + 备份 cron），产出一条龙首次部署指南。

**Architecture:** 项目的容器化基础设施（Dockerfile、docker-compose.yml、Caddyfile、部署脚本）已全部就绪。本计划只补齐首次部署时的服务器初始化环节，不修改任何已有容器配置。

**Tech Stack:** Docker Compose / Caddy / PostgreSQL 16 / bash

---

## 现状确认

| 组件 | 状态 |
|---|---|
| backend/Dockerfile | ✅ 就绪 |
| frontend/Dockerfile | ✅ 就绪 |
| deploy/docker-compose.yml | ✅ 就绪（6 服务、健康检查、资源限制、日志轮转） |
| deploy/Caddyfile | ✅ 就绪（反代 frontend:8080、安全头、健康端点限制） |
| deploy/.env.example | ✅ 就绪 |
| deploy/scripts/deploy.sh | ✅ 就绪（备份→迁移→构建→滚动重启→smoke） |
| deploy/scripts/rollback.sh | ✅ 就绪 |
| docs/deployment.md | ✅ 就绪 |

## 缺口

| # | 缺口 | 说明 |
|---|---|---|
| 1 | 无 `init_server.sh` | 首次部署需要手动装 Docker、建目录、建 .env，无自动化脚本 |
| 2 | 数据目录未预创建 | `deploy/data/{pg,caddy,caddy-config,backup}` 不存在，首次 `pg_backup.sh` 会失败 |
| 3 | 备份 cron 未自动安装 | `backup_cron_setup.sh` 存在但需手动运行 |

---

## 文件变更总览

### 新增
- `deploy/scripts/init_server.sh` — 首次服务器初始化（装 Docker、建目录、建 .env、装 cron）

### 修改
- `docs/deployment.md` — 新增"首次部署（Day-0）"章节

---

### Task 1: 创建服务器初始化脚本

**Files:**
- Create: `deploy/scripts/init_server.sh`

- [ ] **Step 1: 创建 init_server.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# 首次服务器初始化脚本
# 用法: bash deploy/scripts/init_server.sh
#
# 前提: 已通过 SSH 登录到目标服务器，仓库已 clone 到位
# 执行内容:
#   1. 检查 Docker + Docker Compose 是否已安装
#   2. 创建运行时数据目录
#   3. 从 .env.example 生成 .env（如不存在）
#   4. 安装每日备份 cron
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== Restock System 服务器初始化 ==="

# --- 1. 检查 Docker ---
echo "[1/4] 检查 Docker..."
if ! command -v docker &>/dev/null; then
    echo "Docker 未安装。请先安装 Docker："
    echo "  curl -fsSL https://get.docker.com | sh"
    echo "  sudo usermod -aG docker \$USER"
    echo "安装后重新登录并再次运行本脚本。"
    exit 1
fi

if ! docker compose version &>/dev/null; then
    echo "Docker Compose (V2 plugin) 未安装。请安装："
    echo "  sudo apt-get install docker-compose-plugin"
    exit 1
fi

echo "  Docker $(docker --version | awk '{print $3}') ✓"
echo "  Compose $(docker compose version --short) ✓"

# --- 2. 创建数据目录 ---
echo "[2/4] 创建数据目录..."
mkdir -p "$DEPLOY_DIR/data/pg"
mkdir -p "$DEPLOY_DIR/data/caddy"
mkdir -p "$DEPLOY_DIR/data/caddy-config"
mkdir -p "$DEPLOY_DIR/data/backup"
mkdir -p "$DEPLOY_DIR/data/logs"
echo "  deploy/data/{pg,caddy,caddy-config,backup,logs} ✓"

# --- 3. 生成 .env ---
echo "[3/4] 检查 .env..."
if [[ -f "$DEPLOY_DIR/.env" ]]; then
    echo "  .env 已存在，跳过"
else
    cp "$DEPLOY_DIR/.env.example" "$DEPLOY_DIR/.env"
    echo "  已从 .env.example 复制 .env"
    echo "  ⚠️  请编辑 deploy/.env 填入实际密钥："
    echo "     - DB_PASSWORD"
    echo "     - JWT_SECRET"
    echo "     - LOGIN_PASSWORD"
    echo "     - SAIHU_CLIENT_ID / SAIHU_CLIENT_SECRET"
    echo "     - APP_DOMAIN"
fi

# --- 4. 安装备份 cron ---
echo "[4/4] 安装备份 cron..."
bash "$SCRIPT_DIR/backup_cron_setup.sh"

echo ""
echo "=== 初始化完成 ==="
echo "下一步："
echo "  1. 编辑 deploy/.env 填入实际配置"
echo "  2. 运行 bash deploy/scripts/deploy.sh 执行首次部署"
```

- [ ] **Step 2: 设置可执行权限**

```bash
chmod +x deploy/scripts/init_server.sh
```

- [ ] **Step 3: 本地验证脚本语法**

```bash
bash -n deploy/scripts/init_server.sh && echo "SYNTAX OK"
```

预期：SYNTAX OK

- [ ] **Step 4: 提交**

```bash
git add deploy/scripts/init_server.sh
git commit -m "feat: 添加服务器首次初始化脚本 init_server.sh"
```

---

### Task 2: 更新部署文档——新增 Day-0 章节

**Files:**
- Modify: `docs/deployment.md`

- [ ] **Step 1: 在 deployment.md 开头（目录之后、现有正文之前）插入 Day-0 章节**

在 `docs/deployment.md` 中找到正文开始位置，插入以下章节：

```markdown
## 首次部署（Day-0）

> 仅在全新服务器上执行一次。后续更新走 `deploy.sh`。

### 前提条件

- Ubuntu 22.04+ / Debian 12+ 云服务器（2C4G 起步）
- 已配置 SSH 登录
- 已将域名 DNS 解析到服务器 IP（Caddy 自动签发 TLS 证书需要）

### 步骤

```bash
# 1. 登录服务器，clone 仓库
ssh user@your-server
git clone https://github.com/XHBbps/restock-system.git
cd restock-system

# 2. 运行初始化脚本（检查 Docker、建目录、生成 .env、装 cron）
bash deploy/scripts/init_server.sh

# 3. 编辑 .env 填入实际配置
vim deploy/.env
# 必填：DB_PASSWORD, JWT_SECRET, LOGIN_PASSWORD, SAIHU_CLIENT_ID, SAIHU_CLIENT_SECRET, APP_DOMAIN

# 4. 首次部署（自动：拉镜像 → 启动 DB → 等就绪 → 备份 → 迁移 → 构建 → 滚动启动 → smoke）
bash deploy/scripts/deploy.sh

# 5. 验证
curl -sf https://your-domain.com/healthz  # 应返回 {"status":"ok"}
```

### 部署后检查清单

```
[ ] curl /healthz 返回 200
[ ] curl /readyz 返回 200
[ ] 浏览器打开 https://your-domain.com 可见登录页
[ ] 使用默认密码登录成功
[ ] 全局参数页可正常加载
[ ] deploy/data/backup/ 下有备份文件（次日 03:00 后检查）
```
```

- [ ] **Step 2: 提交**

```bash
git add docs/deployment.md
git commit -m "docs: deployment.md 新增首次部署（Day-0）章节"
```

---

### Task 3: 验证 + 推送

- [ ] **Step 1: 运行后端测试确认无回归**

```bash
cd backend && python -m pytest --tb=short -q
```

预期：254 passed，6 pre-existing failures

- [ ] **Step 2: 运行前端验证**

```bash
cd frontend && npx vue-tsc --noEmit
```

预期：无错误

- [ ] **Step 3: 验证 compose 配置**

```bash
cd deploy && docker compose config > /dev/null && echo "COMPOSE OK"
```

预期：COMPOSE OK

- [ ] **Step 4: 推送到 GitHub**

```bash
git push origin master
```
