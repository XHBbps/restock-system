#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${ENV_FILE:-$DEPLOY_DIR/.env}"

set -a
source "$ENV_FILE"
set +a

BASE_URL="${SMOKE_BASE_URL:-${APP_BASE_URL:-https://${APP_DOMAIN}}}"
LIVENESS_URL="${BASE_URL%/}/healthz"
READINESS_URL="${BASE_URL%/}/readyz"
SMOKE_RESOLVE_LOCAL="${SMOKE_RESOLVE_LOCAL:-true}"

CURL_ARGS=(--fail --silent --show-error --max-time 5)
if [[ "$SMOKE_RESOLVE_LOCAL" == "true" && -n "${APP_DOMAIN:-}" ]]; then
    CURL_ARGS+=(--resolve "${APP_DOMAIN}:80:127.0.0.1" --resolve "${APP_DOMAIN}:443:127.0.0.1")
fi

retry_curl() {
    local url="$1"
    local max_attempts="${2:-10}"
    local delay="${3:-3}"
    local attempt=1
    while (( attempt <= max_attempts )); do
        if curl "${CURL_ARGS[@]}" "$url" > /dev/null; then
            echo "[smoke] OK: $url (attempt $attempt)"
            return 0
        fi
        echo "[smoke] attempt $attempt/$max_attempts failed for $url, retrying in ${delay}s..." >&2
        sleep "$delay"
        (( attempt++ ))
    done
    echo "[smoke] FAILED after $max_attempts attempts: $url" >&2
    return 1
}

retry_curl "$LIVENESS_URL"
retry_curl "$READINESS_URL"

echo "smoke check passed for $BASE_URL"
