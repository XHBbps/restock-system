#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$DEPLOY_DIR/docker-compose.yml}"
ENV_FILE="${ENV_FILE:-$DEPLOY_DIR/.env}"
LOCK_FILE="/tmp/restock_migrate.lock"

# 文件锁防止并发迁移
exec 200>"$LOCK_FILE"
if ! flock -n 200; then
    echo "[migrate] another migration is running, aborting" >&2
    exit 1
fi

echo "[migrate] running alembic upgrade head..."
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm backend alembic upgrade head
echo "[migrate] done"
