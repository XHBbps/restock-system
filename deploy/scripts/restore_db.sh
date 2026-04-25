#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: $0 /path/to/backup.sql.gz" >&2
    exit 1
fi

BACKUP_FILE="$1"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$DEPLOY_DIR/docker-compose.yml}"
ENV_FILE="${ENV_FILE:-$DEPLOY_DIR/.env}"

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "backup file not found: $BACKUP_FILE" >&2
    exit 1
fi

echo "[restore] ensuring db is running..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d db
sleep 3

# Pre-restore safety: validate backup integrity AND dump current DB
# before any destructive operation. Critical finding A-1 + A-5.

echo "[safety] 验证备份文件完整性..."
if ! gzip -t "$BACKUP_FILE" 2>/dev/null; then
    echo "ERROR: 备份文件 $BACKUP_FILE gzip 流损坏或不完整，已拒绝 restore。" >&2
    echo "       restore_db.sh 不会 DROP 当前数据库。请检查备份文件。" >&2
    exit 1
fi

SAFETY_DUMP="$(dirname "$BACKUP_FILE")/pre-restore-$(date +%Y%m%d_%H%M%S).sql.gz"
echo "[safety] 备份当前数据库到 $SAFETY_DUMP（防误操作兜底）..."
if ! docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
        pg_dump -U postgres replenish 2>/dev/null | gzip > "$SAFETY_DUMP"; then
    echo "WARN: 当前数据库 dump 失败（可能数据库空/不存在）；SAFETY_DUMP 被移除。" >&2
    rm -f "$SAFETY_DUMP"
    echo "      继续 restore，但无兜底副本 — 若 restore 失败无法自动回退。" >&2
    read -p "      确认继续？[y/N] " -n 1 -r REPLY
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "取消 restore。"
        exit 1
    fi
else
    # 验证 dump 文件有效
    if ! gzip -t "$SAFETY_DUMP" 2>/dev/null; then
        echo "ERROR: 兜底 dump 产出的文件损坏（SAFETY_DUMP），restore 取消。" >&2
        rm -f "$SAFETY_DUMP"
        exit 1
    fi
    echo "[safety] 兜底 dump 完成：$SAFETY_DUMP"
    echo "[safety] 如 restore 失败，可用 bash \"$0\" \"$SAFETY_DUMP\" 回退。"
fi

echo "[restore] dropping and recreating database..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
    psql -U postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='replenish' AND pid <> pg_backend_pid();" || true
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
    psql -U postgres -c "DROP DATABASE IF EXISTS replenish;"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
    psql -U postgres -c "CREATE DATABASE replenish OWNER postgres;"

echo "[restore] restoring backup: $BACKUP_FILE"
gzip -dc "$BACKUP_FILE" | docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
    psql -U postgres -d replenish

echo "[restore] done"
