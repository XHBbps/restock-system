#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"

cd "$ROOT_DIR/backend"
"$PYTHON_BIN" -m pytest -p no:cacheprovider
"$PYTHON_BIN" -m ruff check .

bash "$ROOT_DIR/scripts/frontend-check.sh"
