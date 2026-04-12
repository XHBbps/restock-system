#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$DEPLOY_DIR/docker-compose.yml}"
ENV_FILE="${ENV_FILE:-$DEPLOY_DIR/.env}"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" run --rm backend alembic upgrade head
