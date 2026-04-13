#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${ENV_FILE:-$DEPLOY_DIR/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "missing env file: $ENV_FILE" >&2
    exit 1
fi

set -a
source "$ENV_FILE"
set +a

required_keys=(
    APP_DOMAIN
    APP_BASE_URL
    DB_PASSWORD
    SAIHU_CLIENT_ID
    SAIHU_CLIENT_SECRET
    LOGIN_PASSWORD
    JWT_SECRET
)

for key in "${required_keys[@]}"; do
    if [[ -z "${!key:-}" ]]; then
        echo "missing required env: $key" >&2
        exit 1
    fi
done

if [[ "${DB_PASSWORD}" == "please_change_me_use_strong_password" ]]; then
    echo "DB_PASSWORD is still using the example placeholder" >&2
    exit 1
fi

if [[ "${JWT_SECRET}" == "generate_with_openssl_rand_base64_32" ]]; then
    echo "JWT_SECRET is still using the example placeholder" >&2
    exit 1
fi

if [[ "${LOGIN_PASSWORD}" == "please_change_me" || "${LOGIN_PASSWORD}" == "your_initial_login_password" ]]; then
    echo "LOGIN_PASSWORD is still using the example placeholder" >&2
    exit 1
fi
