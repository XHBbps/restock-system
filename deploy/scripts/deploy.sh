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
IMAGE_TAG="${IMAGE_TAG:-sha-$PREV_SHA}"
export IMAGE_TAG
echo "[deploy] image tag: $IMAGE_TAG"

set -a
source "$ENV_FILE"
set +a
GHCR_OWNER="${GHCR_OWNER,,}"
export GHCR_OWNER
echo "[deploy] ghcr owner: $GHCR_OWNER"

rollback_on_failure() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        echo "[deploy] FAILED with exit code $exit_code; rolling application services back to $PREV_SHA" >&2
        echo "[deploy] NOTE: database rollback is not automatic. Restore the latest backup before re-running migrations if schema changes were applied." >&2
        "$ROLLBACK_SCRIPT" "$PREV_SHA" || echo "[deploy] WARNING: rollback itself failed" >&2
    fi
    exit $exit_code
}
trap rollback_on_failure EXIT

pull_application_images() {
    local pull_timeout="${IMAGE_PULL_TIMEOUT_SECONDS:-1800}"

    echo "[deploy] pulling application images (timeout: ${pull_timeout}s)"
    if timeout "$pull_timeout" docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull backend worker scheduler frontend; then
        return 0
    fi

    if [[ "${ALLOW_LOCAL_IMAGE_BUILD:-false}" == "true" ]]; then
        echo "[deploy] WARNING: image pull failed or timed out; ALLOW_LOCAL_IMAGE_BUILD=true, building backend/frontend locally" >&2
        docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build backend frontend
        return 0
    fi

    echo "[deploy] ERROR: failed or timed out pulling application images for IMAGE_TAG=$IMAGE_TAG" >&2
    echo "[deploy] ERROR: production deploy does not build application images locally by default; wait for GHCR publish or set ALLOW_LOCAL_IMAGE_BUILD=true for manual emergency recovery" >&2
    return 1
}

"$SCRIPT_DIR/validate_env.sh" || exit 1

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
pull_application_images
"$SCRIPT_DIR/migrate.sh"
echo "[deploy] rolling update: backend"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --no-deps --no-build backend
sleep 5

echo "[deploy] rolling update: worker"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --no-deps --no-build worker
sleep 3

echo "[deploy] rolling update: scheduler"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --no-deps --no-build scheduler
sleep 3

echo "[deploy] rolling update: frontend"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --no-deps --no-build frontend
sleep 3

echo "[deploy] rolling update: caddy"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --no-deps caddy
"$SCRIPT_DIR/smoke_check.sh"

# Disable rollback trap on success.
trap - EXIT
echo "[deploy] success; new revision $(cd "$REPO_DIR" && git rev-parse HEAD) live"
