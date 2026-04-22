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
    GHCR_OWNER
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

if [[ "${GHCR_OWNER}" =~ [A-Z] ]]; then
    echo "GHCR_OWNER must be lowercase (for example: xhbbps)" >&2
    exit 1
fi

if [[ "${DB_PASSWORD}" == "please_change_me_use_strong_password" ]]; then
    echo "DB_PASSWORD is still using the example placeholder" >&2
    exit 1
fi

if [[ "${JWT_SECRET}" == "generate_with_openssl_rand_base64_32" \
   || "${JWT_SECRET}" == "please_change_me_32_byte_minimum_key!" ]]; then
    echo "JWT_SECRET is still using the example/default placeholder" >&2
    exit 1
fi

# JWT_SECRET 长度约束（和 app/config.py validate_settings 保持一致）
JWT_SECRET_BYTES=${#JWT_SECRET}
if [[ "$JWT_SECRET_BYTES" -lt 32 ]]; then
    echo "JWT_SECRET must be at least 32 bytes (got $JWT_SECRET_BYTES)" >&2
    exit 1
fi

if [[ "${LOGIN_PASSWORD}" == "please_change_me" || "${LOGIN_PASSWORD}" == "your_initial_login_password" ]]; then
    echo "LOGIN_PASSWORD is still using the example placeholder" >&2
    exit 1
fi

# Saihu 凭证非空（required_keys 已覆盖，此处再保一层防空白字符仅有空格）
if [[ -z "${SAIHU_CLIENT_ID// /}" ]]; then
    echo "SAIHU_CLIENT_ID must not be blank" >&2
    exit 1
fi
if [[ -z "${SAIHU_CLIENT_SECRET// /}" ]]; then
    echo "SAIHU_CLIENT_SECRET must not be blank" >&2
    exit 1
fi
