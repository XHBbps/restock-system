#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
DOCKER_BIN="${DOCKER_BIN:-docker}"

get_local_node_version() {
  if command -v node >/dev/null 2>&1; then
    node -v
    return 0
  fi
  return 1
}

if ! command -v "$DOCKER_BIN" >/dev/null 2>&1; then
  echo "Docker is required for frontend checks. Please install and start Docker." >&2
  exit 1
fi

if ! "$DOCKER_BIN" info >/dev/null 2>&1; then
  echo "Docker is not running or this session cannot access the Docker engine." >&2
  exit 1
fi

if LOCAL_NODE_VERSION="$(get_local_node_version 2>/dev/null)"; then
  echo "Detected local Node ${LOCAL_NODE_VERSION}. Frontend checks will run in Docker Node 20."
else
  echo "No local Node detected. Frontend checks will run in Docker Node 20."
fi

"$DOCKER_BIN" run --rm \
  -e CI=1 \
  -v "$FRONTEND_DIR:/app" \
  -v restock-frontend-check-node-modules:/app/node_modules \
  -v restock-frontend-check-npm-cache:/root/.npm \
  -w /app \
  node:20-alpine \
  sh -lc "npm ci && npm run build && npm run test:coverage"
