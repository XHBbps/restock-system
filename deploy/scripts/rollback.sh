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

echo "[rollback] checking out $PREV_SHA"
cd "$REPO_DIR"
git checkout "$PREV_SHA"

echo "[rollback] database schema is not downgraded automatically"
echo "[rollback] restore the latest database backup before bringing services back if migrations already ran"

echo "[rollback] rebuilding images"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build backend frontend

echo "[rollback] restarting services"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d backend worker scheduler frontend caddy

echo "[rollback] done; previous revision $PREV_SHA restored"
