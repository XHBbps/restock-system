#!/usr/bin/env bash
# Postgres 备份脚本（每日 03:00 执行）
# 使用方式：
#   crontab -e
#   0 3 * * * /opt/restock/deploy/scripts/pg_backup.sh >> /var/log/restock_backup.log 2>&1

set -euo pipefail

# 配置（可通过环境变量覆盖）
COMPOSE_FILE="${COMPOSE_FILE:-/opt/restock/deploy/docker-compose.yml}"
BACKUP_DIR="${BACKUP_DIR:-/opt/restock/deploy/data/backup}"
DB_NAME="${DB_NAME:-replenish}"
DB_USER="${DB_USER:-postgres}"

# OSS / COS 上传（可选）
OSS_BUCKET="${OSS_BUCKET:-}"
OSSUTIL="${OSSUTIL:-ossutil}"

# ----------------------------------------
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="replenish_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] backup start: $BACKUP_FILE"

# 通过 docker compose exec 在 db 容器内 dump
docker compose -f "$COMPOSE_FILE" exec -T db \
    pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --no-acl \
    | gzip -9 > "${BACKUP_DIR}/${BACKUP_FILE}"

SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_FILE}" | cut -f1)
echo "[$(date)] backup ok: $BACKUP_FILE ($SIZE)"

# 上传到对象存储（永久保留，不删本地）
if [[ -n "$OSS_BUCKET" ]]; then
    echo "[$(date)] uploading to OSS: $OSS_BUCKET"
    "$OSSUTIL" cp "${BACKUP_DIR}/${BACKUP_FILE}" "oss://${OSS_BUCKET}/backup/${BACKUP_FILE}"
    echo "[$(date)] upload ok"
fi

echo "[$(date)] done"
