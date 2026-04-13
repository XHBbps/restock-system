#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python}"
NPM_BIN="${NPM_BIN:-npm}"

cd "$ROOT_DIR/backend"
"$PYTHON_BIN" -m pytest -p no:cacheprovider
"$PYTHON_BIN" -m ruff check .

cd "$ROOT_DIR/frontend"
"$NPM_BIN" run build
"$NPM_BIN" test
