#!/usr/bin/env bash
set -euo pipefail

# Roll back the application revision and restart services.
# Database rollback is intentionally manual: restore the latest backup first if a
# migration or data change has already been applied.
#
# Usage: rollback.sh <previous-git-sha>
#
# Called automatically by deploy.sh on failure via trap, but can also be
# invoked manually to recover from a known bad revision.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_DIR="$(cd "$DEPLOY_DIR/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$DEPLOY_DIR/docker-compose.yml}"
ENV_FILE="${ENV_FILE:-$DEPLOY_DIR/.env}"

if [[ $# -lt 1 ]]; then
    echo "usage: $0 <previous-git-sha>" >&2
    exit 2
fi

PREV_SHA="$1"

set -a
source "$ENV_FILE"
set +a
GHCR_OWNER="${GHCR_OWNER,,}"
export GHCR_OWNER

echo "[rollback] checking out $PREV_SHA"
cd "$REPO_DIR"
git checkout -B "rollback-$(date +%Y%m%d-%H%M%S)" "$PREV_SHA"
IMAGE_TAG="sha-$PREV_SHA"
export IMAGE_TAG
echo "[rollback] image tag: $IMAGE_TAG"

echo "[rollback] database schema is not downgraded automatically"
echo "[rollback] if migrations already ran: restore the latest backup with deploy/scripts/restore_db.sh BEFORE bringing services back"
echo "[rollback] SOP details: docs/runbook.md §回滚 SOP"

pull_application_images() {
    local pull_timeout="${IMAGE_PULL_TIMEOUT_SECONDS:-1800}"

    echo "[rollback] pulling application images (timeout: ${pull_timeout}s)"
    if timeout "$pull_timeout" docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull backend worker scheduler frontend; then
        return 0
    fi

    if [[ "${ALLOW_LOCAL_IMAGE_BUILD:-false}" == "true" ]]; then
        echo "[rollback] WARNING: image pull failed or timed out; ALLOW_LOCAL_IMAGE_BUILD=true, building backend/frontend locally" >&2
        docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build backend frontend
        return 0
    fi

    echo "[rollback] ERROR: failed or timed out pulling application images for IMAGE_TAG=$IMAGE_TAG" >&2
    echo "[rollback] ERROR: rollback does not build application images locally by default; confirm GHCR image availability or set ALLOW_LOCAL_IMAGE_BUILD=true for manual emergency recovery" >&2
    return 1
}

pull_application_images

echo "[rollback] restarting services"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --no-build backend worker scheduler frontend caddy

echo "[rollback] done; previous revision $PREV_SHA restored"
