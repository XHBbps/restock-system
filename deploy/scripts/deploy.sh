#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="$(cd "$DEPLOY_DIR/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$DEPLOY_DIR/docker-compose.yml}"
ENV_FILE="${ENV_FILE:-$DEPLOY_DIR/.env}"
BACKUP_SCRIPT="${BACKUP_SCRIPT:-$SCRIPT_DIR/pg_backup.sh}"
ROLLBACK_SCRIPT="${ROLLBACK_SCRIPT:-$SCRIPT_DIR/rollback.sh}"

# Capture current git SHA before any changes, for rollback.
PREV_SHA="$(cd "$REPO_DIR" && git rev-parse HEAD)"
echo "[deploy] previous SHA: $PREV_SHA"

rollback_on_failure() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        echo "[deploy] FAILED with exit code $exit_code — triggering rollback to $PREV_SHA" >&2
        "$ROLLBACK_SCRIPT" "$PREV_SHA" || echo "[deploy] WARNING: rollback itself failed" >&2
    fi
    exit $exit_code
}
trap rollback_on_failure EXIT

"$SCRIPT_DIR/validate_env.sh"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull db caddy || true
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d db

db_ready=0
for _ in {1..30}; do
    if docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
        pg_isready -U postgres -d replenish > /dev/null 2>&1; then
        db_ready=1
        break
    fi
    sleep 2
done

if [[ "$db_ready" -ne 1 ]]; then
    echo "database did not become ready in time" >&2
    exit 1
fi

"$BACKUP_SCRIPT"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build backend frontend
"$SCRIPT_DIR/migrate.sh"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d backend worker scheduler frontend caddy
"$SCRIPT_DIR/smoke_check.sh"

# Disable rollback trap on success
trap - EXIT
echo "[deploy] success — new revision $(cd "$REPO_DIR" && git rev-parse HEAD) live"
