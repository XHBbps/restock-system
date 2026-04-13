#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$DEPLOY_DIR/docker-compose.yml}"
ENV_FILE="${ENV_FILE:-$DEPLOY_DIR/.env}"
BACKUP_DIR="${BACKUP_DIR:-$DEPLOY_DIR/data/backup}"
DB_NAME="${DB_NAME:-replenish}"
DB_USER="${DB_USER:-postgres}"
OSS_BUCKET="${OSS_BUCKET:-}"
OSSUTIL="${OSSUTIL:-ossutil}"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="replenish_${TIMESTAMP}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] backup start: $BACKUP_FILE"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
    pg_dump -U "$DB_USER" -d "$DB_NAME" --no-owner --no-acl \
    | gzip -9 > "${BACKUP_DIR}/${BACKUP_FILE}"

SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_FILE}" | cut -f1)
echo "[$(date)] backup ok: $BACKUP_FILE ($SIZE)"

if [[ -n "$OSS_BUCKET" ]]; then
    echo "[$(date)] uploading to OSS: $OSS_BUCKET"
    "$OSSUTIL" cp "${BACKUP_DIR}/${BACKUP_FILE}" "oss://${OSS_BUCKET}/backup/${BACKUP_FILE}"
    echo "[$(date)] upload ok"
fi

# Retain only last 30 days of local backups
find "$BACKUP_DIR" -name "replenish_*.sql.gz" -mtime +30 -delete
echo "[$(date)] cleaned backups older than 30 days"

echo "[$(date)] done"
