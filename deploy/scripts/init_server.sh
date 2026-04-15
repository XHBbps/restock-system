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
