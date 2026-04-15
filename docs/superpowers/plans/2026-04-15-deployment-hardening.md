# 部署能力加固 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提升项目部署安全性和可观测性，为未来迁移至阿里云做准备。

**Architecture:** 分三个子系统逐步实施：(1) Docker Secrets 替代明文 .env 管理敏感变量；(2) Sentry 前端错误追踪 + 后端集成；(3) 备份恢复自动化验证。中优先级包括 Prometheus 指标扩展、日志持久化挂载、运行时告警脚本。

**Tech Stack:** Docker Compose secrets / Sentry Python SDK + @sentry/vue / prometheus-client / shell scripts / Loki-ready logging

---

## File Structure

### 高优先级 — H1: Docker Secrets 密钥管理

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `deploy/docker-compose.yml` | 添加 `secrets:` 顶层定义 + 服务级挂载 |
| Create | `deploy/scripts/init_secrets.sh` | 从 .env 生成 Docker secret 文件的初始化脚本 |
| Modify | `backend/app/config.py` | Settings 支持从 `/run/secrets/` 读取敏感值 |
| Modify | `deploy/.env.example` | 标注哪些变量迁移到 secrets |
| Modify | `deploy/scripts/validate_env.sh` | 同时校验 .env 和 secrets 文件 |

### 高优先级 — H2: 前端 Sentry 错误追踪

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `frontend/package.json` | 添加 `@sentry/vue` 依赖 |
| Create | `frontend/src/utils/sentry.ts` | Sentry 初始化封装 |
| Modify | `frontend/src/main.ts` | 应用启动时初始化 Sentry |
| Modify | `frontend/src/api/client.ts` | Axios 拦截器上报 API 错误 |
| Modify | `frontend/.env.example` | 添加 `VITE_SENTRY_DSN` |
| Modify | `deploy/.env.example` | 添加 `SENTRY_DSN_FRONTEND` |

### 高优先级 — H3: 后端 Sentry 集成

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `backend/pyproject.toml` | 添加 `sentry-sdk[fastapi]` 依赖 |
| Create | `backend/app/core/sentry.py` | Sentry 初始化封装 |
| Modify | `backend/app/main.py` | lifespan 中初始化 Sentry |
| Modify | `backend/app/config.py` | 添加 `sentry_dsn` 配置 |
| Modify | `backend/.env.example` | 添加 `SENTRY_DSN` |

### 高优先级 — H4: 备份恢复自动验证

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `deploy/scripts/verify_backup.sh` | 恢复到临时库 + 表计数校验 + 自动清理 |
| Modify | `deploy/scripts/backup_cron_setup.sh` | 月度验证 cron |

### 中优先级 — M1: Prometheus 指标扩展

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `backend/pyproject.toml` | 添加 `prometheus-client` 依赖 |
| Create | `backend/app/core/metrics.py` | 集中定义 Prometheus Counter/Histogram/Gauge |
| Modify | `backend/app/api/metrics.py` | `/prometheus` 端点改用 prometheus-client 生成 |
| Modify | `backend/app/core/middleware.py` | 请求计数/延迟直方图中间件 |
| Modify | `deploy/Caddyfile` | `/metrics/prometheus` 内网访问限制 |

### 中优先级 — M2: 日志持久化

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `deploy/docker-compose.yml` | 增大 Docker json-file 日志保留量（100m x 10） |
| Create | `deploy/scripts/logrotate_setup.sh` | Caddy access log logrotate 配置 |

### 中优先级 — M3: 运行时告警

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `deploy/scripts/health_alert.sh` | 健康检查失败时发送告警（钉钉/飞书 webhook） |
| Modify | `deploy/scripts/backup_cron_setup.sh` | 注册健康告警 cron |

---

## Task 1: Docker Secrets — 初始化脚本

**Files:**
- Create: `deploy/scripts/init_secrets.sh`

- [ ] **Step 1: 创建 init_secrets.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail

# 从 deploy/.env 提取敏感变量，写入 Docker secrets 文件
# 用法: bash deploy/scripts/init_secrets.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${ENV_FILE:-$DEPLOY_DIR/.env}"
SECRETS_DIR="${SECRETS_DIR:-$DEPLOY_DIR/secrets}"

if [[ ! -f "$ENV_FILE" ]]; then
    echo "missing env file: $ENV_FILE" >&2
    exit 1
fi

set -a
source "$ENV_FILE"
set +a

mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

# 敏感变量列表
declare -A SECRET_VARS=(
    [db_password]="${DB_PASSWORD:-}"
    [jwt_secret]="${JWT_SECRET:-}"
    [login_password]="${LOGIN_PASSWORD:-}"
    [saihu_client_id]="${SAIHU_CLIENT_ID:-}"
    [saihu_client_secret]="${SAIHU_CLIENT_SECRET:-}"
)

for name in "${!SECRET_VARS[@]}"; do
    value="${SECRET_VARS[$name]}"
    if [[ -z "$value" ]]; then
        echo "WARNING: $name is empty, skipping" >&2
        continue
    fi
    printf '%s' "$value" > "$SECRETS_DIR/$name"
    chmod 600 "$SECRETS_DIR/$name"
    echo "[init_secrets] wrote $name"
done

echo "[init_secrets] done — secrets in $SECRETS_DIR"
echo "[init_secrets] IMPORTANT: add 'secrets/' to .gitignore if not already present"
```

- [ ] **Step 2: 确认 .gitignore 已忽略 secrets 目录**

Run: `grep -q 'deploy/secrets' .gitignore || echo 'deploy/secrets/' >> .gitignore`

- [ ] **Step 3: Commit**

```bash
git add deploy/scripts/init_secrets.sh .gitignore
git commit -m "feat: add init_secrets.sh for Docker Secrets file generation"
```

---

## Task 2: Docker Secrets — config.py 支持从文件读取

**Files:**
- Modify: `backend/app/config.py`
- Test: `backend/tests/test_config_secrets.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_config_secrets.py`:

```python
"""Test Settings reads secrets from /run/secrets/ files."""

import os
from unittest.mock import patch

import pytest


def test_settings_reads_secret_from_file(tmp_path):
    """When env var is empty but secret file exists, use file content."""
    secret_file = tmp_path / "jwt_secret"
    secret_file.write_text("file_based_secret_value")

    env = {
        "DATABASE_URL": "postgresql+asyncpg://postgres:x@localhost:5432/replenish",
        "APP_ENV": "development",
        "JWT_SECRET": "",  # empty env var
    }
    with patch.dict(os.environ, env, clear=False):
        from app.config import Settings, _read_secret_file

        value = _read_secret_file(str(secret_file))
        assert value == "file_based_secret_value"


def test_read_secret_file_missing_returns_none():
    """Missing secret file returns None."""
    from app.config import _read_secret_file

    assert _read_secret_file("/nonexistent/path/secret") is None


def test_read_secret_file_strips_whitespace(tmp_path):
    """Secret file content is stripped of trailing newlines."""
    secret_file = tmp_path / "db_password"
    secret_file.write_text("my_password\n")

    from app.config import _read_secret_file

    assert _read_secret_file(str(secret_file)) == "my_password"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_config_secrets.py -v`
Expected: FAIL — `_read_secret_file` 不存在

- [ ] **Step 3: 实现 _read_secret_file 并修改 Settings**

修改 `backend/app/config.py`，在 `class Settings` 之前添加：

```python
from pathlib import Path

SECRETS_DIR = Path("/run/secrets")


def _read_secret_file(path: str) -> str | None:
    """Read a Docker secret file, return stripped content or None."""
    p = Path(path)
    if p.is_file():
        return p.read_text().strip()
    return None
```

修改 `class Settings` 中需要 secret 支持的字段，添加 `model_validator`：

```python
from pydantic import model_validator

class Settings(BaseSettings):
    # ... existing fields ...

    @model_validator(mode="after")
    def _fill_from_secret_files(self) -> "Settings":
        """Fill empty sensitive fields from /run/secrets/ files."""
        secret_fields = {
            "db_password": "database_url",  # special: embedded in DSN
            "jwt_secret": "jwt_secret",
            "login_password": "login_password",
            "saihu_client_id": "saihu_client_id",
            "saihu_client_secret": "saihu_client_secret",
        }
        for secret_name, field_name in secret_fields.items():
            if secret_name == "db_password":
                continue  # DSN handled by Docker Compose env substitution
            secret_path = SECRETS_DIR / secret_name
            value = _read_secret_file(str(secret_path))
            if value and not getattr(self, field_name, "").strip():
                object.__setattr__(self, field_name, value)
        return self
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_config_secrets.py -v`
Expected: PASS

- [ ] **Step 5: 运行全量测试确认无回归**

Run: `cd backend && python -m pytest --tb=short -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/tests/test_config_secrets.py
git commit -m "feat: Settings supports reading secrets from /run/secrets/ files"
```

---

## Task 3: Docker Secrets — docker-compose.yml 集成

**Files:**
- Modify: `deploy/docker-compose.yml`
- Modify: `deploy/.env.example`

- [ ] **Step 1: 修改 docker-compose.yml 添加 secrets 定义**

在文件末尾 `networks:` 之后添加 `secrets:` 顶层块，并在 `x-backend-env` 锚点和各服务中挂载：

在 `deploy/docker-compose.yml` 末尾添加：

```yaml
secrets:
  jwt_secret:
    file: ./secrets/jwt_secret
  login_password:
    file: ./secrets/login_password
  saihu_client_id:
    file: ./secrets/saihu_client_id
  saihu_client_secret:
    file: ./secrets/saihu_client_secret
```

> `db_password` 不加入 compose secrets——PostgreSQL 容器仍通过 `POSTGRES_PASSWORD` 环境变量获取密码（详见上方警告）。

在 `backend` 服务中添加 `secrets` 挂载（与 `environment` 同级）：

```yaml
    secrets:
      - jwt_secret
      - login_password
      - saihu_client_id
      - saihu_client_secret
```

同样为 `worker` 和 `scheduler` 服务添加相同的 `secrets` 块。

`db` 服务**不需要挂载 secrets**（密码仍通过 `POSTGRES_PASSWORD` 环境变量注入）。

保留 `db` 的 `POSTGRES_PASSWORD` 不变（**不要改为 `POSTGRES_PASSWORD_FILE`**）：

> **警告**：在已有数据目录的部署上，将 `POSTGRES_PASSWORD` 切换为 `POSTGRES_PASSWORD_FILE` 会导致 PostgreSQL 启动失败——容器只在首次 initdb 时读取密码变量，后续启动忽略它。切换会引起密码不匹配，数据库不可访问。因此 db 服务的 `POSTGRES_PASSWORD: ${DB_PASSWORD}` 保持原样，仅为后端服务挂载 secrets。

**重要**：`x-backend-env` 中的 `DATABASE_URL` 保持不变（仍用 `${DB_PASSWORD}` 注入）。`DB_PASSWORD` 变量必须保留在 `deploy/.env` 中，因为 Docker Compose 的环境变量替换发生在容器启动前，无法读取 `/run/secrets/` 文件。数据库密码和 DSN 仍完全通过 `.env` 管理；secrets 机制仅用于后端应用层读取 `jwt_secret`、`login_password`、`saihu_client_id`、`saihu_client_secret`。

- [ ] **Step 2: 更新 deploy/.env.example 添加注释**

在 `deploy/.env.example` 顶部添加注释说明：

```bash
# ========================================
# 敏感变量建议使用 Docker Secrets 管理
# 运行 bash deploy/scripts/init_secrets.sh 从本文件生成 secret 文件
# 详见 docs/deployment.md
# ========================================
```

- [ ] **Step 3: 验证 docker-compose 配置语法**

Run: `cd deploy && docker compose config --quiet`
Expected: 无报错

- [ ] **Step 4: Commit**

```bash
git add deploy/docker-compose.yml deploy/.env.example
git commit -m "feat: docker-compose integrates Docker Secrets for sensitive variables"
```

---

## Task 4: Docker Secrets — validate_env.sh 兼容

**Files:**
- Modify: `deploy/scripts/validate_env.sh`

- [ ] **Step 1: 修改 validate_env.sh 同时校验 .env 和 secrets 文件**

将 `validate_env.sh` 中的 required_keys 校验改为"环境变量或 secret 文件至少有其一"：

在 `set +a` 之后、`required_keys` 之前添加 secrets 目录变量：

```bash
SECRETS_DIR="${SECRETS_DIR:-$DEPLOY_DIR/secrets}"
```

将 required_keys 循环改为：

```bash
# 非敏感必需变量（必须在 .env 中）
plain_keys=(APP_DOMAIN APP_BASE_URL)

for key in "${plain_keys[@]}"; do
    if [[ -z "${!key:-}" ]]; then
        echo "missing required env: $key" >&2
        exit 1
    fi
done

# 敏感变量：.env 或 secrets 文件至少有一个
secret_keys=(DB_PASSWORD JWT_SECRET LOGIN_PASSWORD SAIHU_CLIENT_ID SAIHU_CLIENT_SECRET)
secret_file_names=(db_password jwt_secret login_password saihu_client_id saihu_client_secret)

for i in "${!secret_keys[@]}"; do
    key="${secret_keys[$i]}"
    file_name="${secret_file_names[$i]}"
    env_val="${!key:-}"
    file_val=""
    if [[ -f "$SECRETS_DIR/$file_name" ]]; then
        file_val="$(cat "$SECRETS_DIR/$file_name")"
    fi
    if [[ -z "$env_val" && -z "$file_val" ]]; then
        echo "missing required secret: $key (set in .env or $SECRETS_DIR/$file_name)" >&2
        exit 1
    fi
done
```

修改占位符检测逻辑，使其同时检查 .env 值和 secret 文件内容：

```bash
# 占位符检测（从 .env 或 secret 文件读取实际值）
get_secret_value() {
    local env_key="$1" file_name="$2"
    local val="${!env_key:-}"
    if [[ -z "$val" && -f "$SECRETS_DIR/$file_name" ]]; then
        val="$(cat "$SECRETS_DIR/$file_name")"
    fi
    echo "$val"
}

db_pw="$(get_secret_value DB_PASSWORD db_password)"
if [[ "$db_pw" == "please_change_me_use_strong_password" ]]; then
    echo "DB_PASSWORD is still using the example placeholder" >&2
    exit 1
fi

jwt_val="$(get_secret_value JWT_SECRET jwt_secret)"
if [[ "$jwt_val" == "generate_with_openssl_rand_base64_32" ]]; then
    echo "JWT_SECRET is still using the example placeholder" >&2
    exit 1
fi

login_pw="$(get_secret_value LOGIN_PASSWORD login_password)"
if [[ "$login_pw" == "please_change_me" || "$login_pw" == "your_initial_login_password" ]]; then
    echo "LOGIN_PASSWORD is still using the example placeholder" >&2
    exit 1
fi
```

- [ ] **Step 2: 测试——只有 .env 时通过**

Run: `cd deploy && bash scripts/validate_env.sh` (使用现有 .env)
Expected: 通过

- [ ] **Step 3: Commit**

```bash
git add deploy/scripts/validate_env.sh
git commit -m "feat: validate_env.sh supports Docker Secrets fallback"
```

---

## Task 5: 前端 Sentry 错误追踪

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/src/utils/sentry.ts`
- Modify: `frontend/src/main.ts`
- Modify: `frontend/.env.example`

- [ ] **Step 1: 安装 @sentry/vue**

Run: `cd frontend && npm install @sentry/vue`

- [ ] **Step 2: 添加 VITE_SENTRY_DSN 到 .env.example**

在 `frontend/.env.example` 追加：

```bash
VITE_SENTRY_DSN=
```

- [ ] **Step 3: 创建 frontend/src/utils/sentry.ts**

```typescript
import type { App } from 'vue'
import type { Router } from 'vue-router'

/**
 * 初始化 Sentry 错误追踪。
 * 当 VITE_SENTRY_DSN 未设置时，静默跳过。
 */
export function initSentry(app: App, router: Router): void {
  const dsn = import.meta.env.VITE_SENTRY_DSN
  if (!dsn) return

  import('@sentry/vue').then((Sentry) => {
    Sentry.init({
      app,
      dsn,
      environment: import.meta.env.MODE,
      integrations: [Sentry.browserTracingIntegration({ router })],
      tracesSampleRate: 0.2,
      replaysSessionSampleRate: 0,
      replaysOnErrorSampleRate: 0,
    })
  })
}
```

- [ ] **Step 4: 修改 frontend/src/main.ts 初始化 Sentry**

读取当前 `main.ts` 内容，在 `app.mount('#app')` 之前添加：

```typescript
import { initSentry } from '@/utils/sentry'

// ... existing code ...

// 在 app.use(router) 之后、app.config.errorHandler 之前调用
// 必须在 errorHandler 之前，否则 Sentry 无法捕获 Vue 组件错误
initSentry(app, router)
```

- [ ] **Step 5: 验证前端构建通过**

Run: `cd frontend && npx vue-tsc --noEmit && npx vite build`
Expected: 无错误

- [ ] **Step 6: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/utils/sentry.ts frontend/src/main.ts frontend/.env.example
git commit -m "feat: integrate Sentry for frontend error tracking"
```

---

## Task 6: 前端 Axios 拦截器上报 API 错误到 Sentry

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: 在 response error 拦截器中捕获 5xx 到 Sentry**

在 `frontend/src/api/client.ts` 的 response error 拦截器中，`return Promise.reject(error)` 之前添加：

```typescript
    // 5xx 错误上报 Sentry（4xx 为业务错误，不上报）
    if (error.response && error.response.status >= 500) {
      import('@sentry/vue').then((Sentry) => {
        Sentry.captureException(error, {
          tags: {
            api_url: error.config?.url ?? 'unknown',
            http_status: String(error.response?.status),
          },
        })
      }).catch(() => {})  // Sentry 未初始化时静默
    }
```

- [ ] **Step 2: 验证构建通过**

Run: `cd frontend && npx vue-tsc --noEmit && npx vite build`
Expected: 无错误

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: report 5xx API errors to Sentry from Axios interceptor"
```

---

## Task 7: 后端 Sentry 集成

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/app/core/sentry.py`
- Modify: `backend/app/config.py`
- Modify: `backend/app/main.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_sentry_init.py`

- [ ] **Step 1: 添加依赖**

在 `backend/pyproject.toml` 的 `dependencies` 列表中添加：

```toml
"sentry-sdk[fastapi]>=2.0.0",
```

Run: `cd backend && pip install -e ".[dev]"`

- [ ] **Step 2: 在 config.py 添加 sentry_dsn 字段**

在 `backend/app/config.py` 的 `Settings` 类中添加：

```python
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.2
```

- [ ] **Step 3: 创建 backend/app/core/sentry.py**

```python
"""Sentry initialization for FastAPI backend."""

from app.config import Settings


def init_sentry(settings: Settings) -> None:
    """Initialize Sentry SDK if DSN is configured."""
    if not settings.sentry_dsn:
        return

    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
        send_default_pii=False,
    )
```

- [ ] **Step 4: 写测试**

创建 `backend/tests/test_sentry_init.py`:

```python
"""Test Sentry initialization."""

from unittest.mock import patch

from app.config import Settings


def test_init_sentry_skips_when_no_dsn():
    """init_sentry should be a no-op when sentry_dsn is empty."""
    settings = Settings(
        database_url="postgresql+asyncpg://postgres:x@localhost:5432/replenish",
        sentry_dsn="",
    )
    # init_sentry 内部 lazy import sentry_sdk，不会走到 init 调用
    from app.core.sentry import init_sentry

    # 无 DSN 时函数应直接 return，不 import sentry_sdk
    init_sentry(settings)  # 不抛异常即通过


def test_init_sentry_calls_sdk_when_dsn_set():
    """init_sentry should call sentry_sdk.init when DSN is provided."""
    settings = Settings(
        database_url="postgresql+asyncpg://postgres:x@localhost:5432/replenish",
        sentry_dsn="https://examplekey@sentry.io/123",
        app_env="production",
        sentry_traces_sample_rate=0.1,
    )
    # sentry_sdk 在 init_sentry 内部 lazy import，
    # 需要 patch 模块级别的 sentry_sdk.init
    import sentry_sdk

    with patch.object(sentry_sdk, "init") as mock_init:
        from app.core.sentry import init_sentry

        init_sentry(settings)
        mock_init.assert_called_once()
        call_kwargs = mock_init.call_args[1]
        assert call_kwargs["dsn"] == "https://examplekey@sentry.io/123"
        assert call_kwargs["environment"] == "production"
        assert call_kwargs["traces_sample_rate"] == 0.1
```

- [ ] **Step 5: 运行测试**

Run: `cd backend && python -m pytest tests/test_sentry_init.py -v`
Expected: PASS

- [ ] **Step 6: 在 main.py lifespan 中调用 init_sentry**

在 `backend/app/main.py` 的 lifespan 函数中，在应用启动阶段（`yield` 之前）添加：

在文件顶部 import 区添加（`get_settings` 已在 `main.py:21` 导入，无需重复）：

```python
from app.core.sentry import init_sentry
```

在 `lifespan` 函数中，`configure_logging()` 之后（第 82 行位置）插入：

```python
    init_sentry(get_settings())
```

- [ ] **Step 7: 更新 backend/.env.example**

追加：

```bash
# ---- Sentry ----
SENTRY_DSN=
SENTRY_TRACES_SAMPLE_RATE=0.2
```

- [ ] **Step 8: 运行全量后端测试**

Run: `cd backend && python -m pytest --tb=short -q`
Expected: all pass

- [ ] **Step 9: Commit**

```bash
git add backend/pyproject.toml backend/app/config.py backend/app/core/sentry.py backend/app/main.py backend/.env.example backend/tests/test_sentry_init.py
git commit -m "feat: integrate Sentry SDK for backend error tracking"
```

---

## Task 8: 备份恢复自动验证脚本

**Files:**
- Create: `deploy/scripts/verify_backup.sh`

- [ ] **Step 1: 创建 verify_backup.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail

# 备份恢复验证：恢复到临时数据库 → 校验表和行数 → 自动清理
# 用法: bash deploy/scripts/verify_backup.sh [backup_file]
# 若不指定 backup_file，自动选择 data/backup/ 下最新的备份

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$DEPLOY_DIR/docker-compose.yml}"
ENV_FILE="${ENV_FILE:-$DEPLOY_DIR/.env}"
BACKUP_DIR="${BACKUP_DIR:-$DEPLOY_DIR/data/backup}"
VERIFY_DB="replenish_verify"
DB_USER="${DB_USER:-postgres}"
LOG_FILE="${DEPLOY_DIR}/data/logs/backup_verify.log"

mkdir -p "$(dirname "$LOG_FILE")"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

# 确定备份文件
if [[ $# -ge 1 ]]; then
    BACKUP_FILE="$1"
else
    BACKUP_FILE="$(ls -t "$BACKUP_DIR"/replenish_*.sql.gz 2>/dev/null | head -1)"
fi

if [[ -z "$BACKUP_FILE" || ! -f "$BACKUP_FILE" ]]; then
    log "ERROR: no backup file found"
    exit 1
fi

log "verify start: $BACKUP_FILE"

cleanup() {
    log "cleanup: dropping $VERIFY_DB"
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
        psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS $VERIFY_DB;" 2>/dev/null || true
}
trap cleanup EXIT

# 1. 创建临时验证数据库
log "creating temporary database: $VERIFY_DB"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
    psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS $VERIFY_DB;"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
    psql -U "$DB_USER" -c "CREATE DATABASE $VERIFY_DB OWNER $DB_USER;"

# 2. 恢复备份到临时库
log "restoring backup to $VERIFY_DB..."
gzip -dc "$BACKUP_FILE" | docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
    psql -U "$DB_USER" -d "$VERIFY_DB" > /dev/null 2>&1

# 3. 校验关键表存在且有数据
EXPECTED_TABLES=(
    "product_listing" "sku_config" "suggestion" "suggestion_item" "task_run"
    "global_config" "role" "permission" "role_permission" "sys_user"
    "order_header" "order_item" "order_detail" "inventory_snapshot_latest"
    "warehouse" "shop" "sync_state" "api_call_log" "zipcode_rule"
)
VERIFY_OK=true

for table in "${EXPECTED_TABLES[@]}"; do
    COUNT=$(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
        psql -U "$DB_USER" -d "$VERIFY_DB" -tAc "SELECT count(*) FROM $table;" 2>/dev/null || echo "ERROR")
    if [[ "$COUNT" == "ERROR" ]]; then
        log "FAIL: table '$table' missing or inaccessible"
        VERIFY_OK=false
    else
        log "OK: table '$table' has $COUNT rows"
    fi
done

# 4. 对比生产库表数量
PROD_TABLE_COUNT=$(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
    psql -U "$DB_USER" -d replenish -tAc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';" 2>/dev/null || echo "0")
VERIFY_TABLE_COUNT=$(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
    psql -U "$DB_USER" -d "$VERIFY_DB" -tAc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';" 2>/dev/null || echo "0")

if [[ "$PROD_TABLE_COUNT" != "$VERIFY_TABLE_COUNT" ]]; then
    log "WARNING: table count mismatch — production=$PROD_TABLE_COUNT, backup=$VERIFY_TABLE_COUNT"
    VERIFY_OK=false
else
    log "OK: table count matches ($PROD_TABLE_COUNT tables)"
fi

# 5. 结论
if [[ "$VERIFY_OK" == true ]]; then
    log "RESULT: backup verification PASSED"
    exit 0
else
    log "RESULT: backup verification FAILED — check log for details"
    exit 1
fi
```

- [ ] **Step 2: Commit**

```bash
git add deploy/scripts/verify_backup.sh
git commit -m "feat: add verify_backup.sh for automated backup restore testing"
```

---

## Task 9: 备份验证 cron 注册

**Files:**
- Modify: `deploy/scripts/backup_cron_setup.sh`

- [ ] **Step 1: 读取当前 backup_cron_setup.sh**

Run: `cat deploy/scripts/backup_cron_setup.sh`

- [ ] **Step 2: 追加月度验证 cron**

在现有备份 cron 注册逻辑之后，添加月度验证任务（每月 1 日凌晨 4:00 执行）：

```bash
# 月度备份恢复验证（每月 1 日 04:00）
VERIFY_CRON="0 4 1 * * cd $DEPLOY_DIR && bash scripts/verify_backup.sh >> data/logs/backup_verify.log 2>&1"
if ! crontab -l 2>/dev/null | grep -qF "verify_backup.sh"; then
    (crontab -l 2>/dev/null; echo "$VERIFY_CRON") | crontab -
    echo "[cron] monthly backup verification registered"
else
    echo "[cron] monthly backup verification already registered"
fi
```

- [ ] **Step 3: Commit**

```bash
git add deploy/scripts/backup_cron_setup.sh
git commit -m "feat: register monthly backup verification cron job"
```

---

## Task 10: Prometheus 指标扩展 — prometheus-client 集成

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/app/core/metrics.py`

- [ ] **Step 1: 添加依赖**

在 `backend/pyproject.toml` 的 `dependencies` 列表中添加：

```toml
"prometheus-client>=0.21.0",
```

Run: `cd backend && pip install -e ".[dev]"`

- [ ] **Step 2: 创建 backend/app/core/metrics.py**

```python
"""Centralized Prometheus metrics definitions."""

from prometheus_client import Counter, Gauge, Histogram

# HTTP 请求
http_requests_total = Counter(
    "restock_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)

http_request_duration_seconds = Histogram(
    "restock_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# 任务队列
taskrun_pending = Gauge(
    "restock_taskrun_pending",
    "Number of pending tasks",
)

taskrun_running = Gauge(
    "restock_taskrun_running",
    "Number of running tasks",
)

# 应用状态
app_up = Gauge(
    "restock_up",
    "Application is up",
)
app_up.set(1)
```

- [ ] **Step 3: Commit**

```bash
git add backend/pyproject.toml backend/app/core/metrics.py
git commit -m "feat: add centralized Prometheus metrics definitions"
```

---

## Task 11: Prometheus — 中间件埋点

**Files:**
- Modify: `backend/app/core/middleware.py`
- Test: `backend/tests/test_metrics_middleware.py`

- [ ] **Step 1: 写测试**

创建 `backend/tests/test_metrics_middleware.py`:

```python
"""Test that metrics middleware records request counts and durations."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.metrics import http_requests_total


@pytest.mark.asyncio
async def test_metrics_middleware_increments_counter():
    """After a request, http_requests_total should increment."""
    from app.main import app  # 模块级单例，非工厂函数

    before_total = sum(
        m._value.get() for m in http_requests_total._metrics.values()
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/healthz")
    assert resp.status_code == 200
    after_total = sum(
        m._value.get() for m in http_requests_total._metrics.values()
    )
    assert after_total > before_total
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_metrics_middleware.py -v`
Expected: FAIL

- [ ] **Step 3: 修改 middleware.py 添加指标埋点**

在 `backend/app/core/middleware.py` 的 `RequestLoggingMiddleware.__call__` 方法中，在记录日志之后添加 Prometheus 指标：

在文件顶部添加 import：

```python
from app.core.metrics import http_request_duration_seconds, http_requests_total
```

在 `dispatch` 方法中，**两个** `duration_ms` 计算点之后都添加指标（正常响应 + 异常）：

**正常响应**（在 `log_method("http_request", ...)` 之后、`response.headers["X-Request-Id"]` 之前）：

```python
        http_requests_total.labels(
            method=request.method, endpoint=request.url.path, status=str(response.status_code)
        ).inc()
        http_request_duration_seconds.labels(
            method=request.method, endpoint=request.url.path
        ).observe(duration_ms / 1000.0)
```

**异常路径**（在 `logger.exception(...)` 之后、`return JSONResponse(500, ...)` 之前）：

```python
            http_requests_total.labels(
                method=request.method, endpoint=request.url.path, status="500"
            ).inc()
            http_request_duration_seconds.labels(
                method=request.method, endpoint=request.url.path
            ).observe(duration_ms / 1000.0)
```

> **注意**：中间件使用 `request.method` 和 `request.url.path`（Starlette Request API），不是 `scope["method"]`。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_metrics_middleware.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/middleware.py backend/tests/test_metrics_middleware.py
git commit -m "feat: instrument HTTP requests with Prometheus counters and histograms"
```

---

## Task 12: Prometheus — 改造 /prometheus 端点

**Files:**
- Modify: `backend/app/api/metrics.py`
- Modify: `deploy/Caddyfile`

- [ ] **Step 1: 改造 prometheus_metrics 端点**

将 `backend/app/api/metrics.py` 的 `prometheus_metrics` 函数（第 498-526 行）改为使用 `prometheus_client` 生成输出：

```python
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.core.metrics import taskrun_pending, taskrun_running


@router.get("/prometheus", response_class=PlainTextResponse)
async def prometheus_metrics(
    db: AsyncSession = Depends(db_session_readonly),
) -> PlainTextResponse:
    """Prometheus 格式指标端点。"""
    # 更新动态 gauge
    pending = (
        await db.execute(
            select(func.count()).select_from(TaskRun).where(TaskRun.status == "pending")
        )
    ).scalar() or 0
    running = (
        await db.execute(
            select(func.count()).select_from(TaskRun).where(TaskRun.status == "running")
        )
    ).scalar() or 0

    taskrun_pending.set(pending)
    taskrun_running.set(running)

    return PlainTextResponse(
        generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )
```

- [ ] **Step 2: 修改 Caddyfile 限制 /api/metrics/prometheus 内网访问**

在 `deploy/Caddyfile` 中，**必须在 `handle /api/*` 之前**添加一个独立的 metrics 内网限制块（因为 Caddy handle 按先后顺序匹配，`/api/*` 会先吃掉所有 `/api/` 请求）：

在 `handle /api/*` 块**之前**插入：

```caddyfile
    # Prometheus 指标端点仅内网可访问（必须在 /api/* 之前）
    @metrics_internal {
        path /api/metrics/prometheus
        remote_ip 127.0.0.1 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16
    }
    handle @metrics_internal {
        reverse_proxy backend:8000
    }
    handle /api/metrics/prometheus {
        respond 404
    }
```

- [ ] **Step 3: 运行后端测试**

Run: `cd backend && python -m pytest --tb=short -q`
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/metrics.py deploy/Caddyfile
git commit -m "feat: /prometheus endpoint uses prometheus-client, restrict to internal network"
```

---

## Task 13: 日志持久化 — Docker 日志保留 + logrotate

**Files:**
- Modify: `deploy/docker-compose.yml`
- Create: `deploy/scripts/logrotate_setup.sh`

> **背景**：后端 structlog 只写 stdout，不写文件。Docker json-file 日志驱动已自动捕获 stdout 到宿主机 `/var/lib/docker/containers/<id>/<id>-json.log`。因此不需要挂载 `/app/logs` 空目录，而是：(1) 增大 Docker 日志保留量；(2) 配置 logrotate 管理 Caddy access log。

- [ ] **Step 1: 增大 docker-compose.yml 日志保留量**

将 `x-logging` 锚点改为保留更多历史日志：

```yaml
x-logging: &default-logging
  driver: json-file
  options:
    max-size: "100m"
    max-file: "10"
```

这样每个容器最多保留 1GB 日志（10 x 100MB），足够回溯 7-14 天。

- [ ] **Step 2: 创建 logrotate 配置脚本**

创建 `deploy/scripts/logrotate_setup.sh`，仅管理 Caddy access log（Docker 自身日志由 json-file 驱动自动轮转）：

```bash
#!/usr/bin/env bash
set -euo pipefail

# 为 Caddy access log 配置 logrotate
# Docker 容器日志由 json-file 驱动的 max-size/max-file 自动管理
# 此脚本仅处理 Caddy 挂载到宿主机的 access.log

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CADDY_LOG="$DEPLOY_DIR/data/caddy/access.log"

LOGROTATE_CONF="/etc/logrotate.d/restock"

cat > "$LOGROTATE_CONF" << EOF
$CADDY_LOG {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    maxsize 100M
}
EOF

echo "[logrotate] config written to $LOGROTATE_CONF"
```

- [ ] **Step 3: 验证 docker-compose 配置**

Run: `cd deploy && docker compose config --quiet`
Expected: 无报错

- [ ] **Step 4: Commit**

```bash
git add deploy/docker-compose.yml deploy/scripts/logrotate_setup.sh
git commit -m "feat: increase Docker log retention + add Caddy logrotate setup"
```

---

## Task 14: 运行时健康告警脚本

**Files:**
- Create: `deploy/scripts/health_alert.sh`
- Modify: `deploy/scripts/backup_cron_setup.sh`
- Modify: `deploy/.env.example`

- [ ] **Step 1: 创建 health_alert.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail

# 健康检查告警：检测 /healthz 和 /readyz，失败时发送 webhook 通知
# 支持钉钉/飞书 webhook
# 用法: bash deploy/scripts/health_alert.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${ENV_FILE:-$DEPLOY_DIR/.env}"

set -a
source "$ENV_FILE"
set +a

# 通过 docker compose exec 直接在 backend 容器内检查健康端点
# 不走 Caddy：因为 (1) backend 未映射端口到宿主机
#              (2) Caddyfile 限制 /healthz 仅内网 IP
#              (3) Caddy site block 绑定 APP_DOMAIN，localhost 不匹配
COMPOSE_FILE="${COMPOSE_FILE:-$DEPLOY_DIR/docker-compose.yml}"
ALERT_WEBHOOK="${ALERT_WEBHOOK:-}"
TIMEOUT=5
LOG_FILE="${DEPLOY_DIR}/data/logs/health_alert.log"
# 用于告警消息中标识实例
INSTANCE_LABEL="${APP_BASE_URL:-https://${APP_DOMAIN:-unknown}}"

mkdir -p "$(dirname "$LOG_FILE")"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

send_alert() {
    local message="$1"
    if [[ -z "$ALERT_WEBHOOK" ]]; then
        log "ALERT (no webhook): $message"
        return
    fi

    # 钉钉 webhook 格式
    local payload
    payload=$(cat <<EOJSON
{
    "msgtype": "text",
    "text": {
        "content": "[补货系统告警] $message"
    }
}
EOJSON
    )

    curl -s -X POST "$ALERT_WEBHOOK" \
        -H "Content-Type: application/json" \
        -d "$payload" >> "$LOG_FILE" 2>&1 || log "WARNING: webhook send failed"
}

FAILED=false
FAIL_MSG=""

# 检查 liveness（通过 docker compose exec 在容器内执行 curl）
HEALTHZ=$(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T backend \
    python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz', timeout=$TIMEOUT).read()" 2>/dev/null) || HEALTHZ=""
if [[ -z "$HEALTHZ" ]]; then
    FAILED=true
    FAIL_MSG="healthz FAILED"
    log "FAIL: healthz unreachable"
fi

# 检查 readiness（通过 docker compose exec 在容器内执行）
READYZ_RESPONSE=$(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T backend \
    python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/readyz', timeout=$TIMEOUT).read().decode())" 2>/dev/null || echo '{"status":"error"}')
if echo "$READYZ_RESPONSE" | grep -q '"error"'; then
    FAILED=true
    FAIL_MSG="${FAIL_MSG:+$FAIL_MSG | }readyz FAILED: $READYZ_RESPONSE"
    log "FAIL: readyz error — $READYZ_RESPONSE"
fi

# 检查磁盘空间（< 10% 告警）
DISK_USAGE=$(df "$DEPLOY_DIR" | tail -1 | awk '{print $5}' | tr -d '%')
if [[ "$DISK_USAGE" -gt 90 ]]; then
    FAILED=true
    FAIL_MSG="${FAIL_MSG:+$FAIL_MSG | }磁盘使用率 ${DISK_USAGE}%"
    log "FAIL: disk usage ${DISK_USAGE}%"
fi

if [[ "$FAILED" == true ]]; then
    send_alert "$FAIL_MSG ($INSTANCE_LABEL)"
else
    log "OK: all checks passed"
fi
```

- [ ] **Step 2: 更新 deploy/.env.example**

追加：

```bash
# ---- 告警 Webhook（钉钉/飞书，可选）----
ALERT_WEBHOOK=
```

- [ ] **Step 3: 在 backup_cron_setup.sh 注册健康检查 cron**

在现有 cron 注册逻辑之后追加（每 5 分钟检查一次）：

```bash
# 健康检查告警（每 5 分钟）
HEALTH_CRON="*/5 * * * * cd $DEPLOY_DIR && bash scripts/health_alert.sh"
if ! crontab -l 2>/dev/null | grep -qF "health_alert.sh"; then
    (crontab -l 2>/dev/null; echo "$HEALTH_CRON") | crontab -
    echo "[cron] health alert check registered (every 5 min)"
else
    echo "[cron] health alert check already registered"
fi
```

- [ ] **Step 4: Commit**

```bash
git add deploy/scripts/health_alert.sh deploy/.env.example deploy/scripts/backup_cron_setup.sh
git commit -m "feat: add runtime health alert script with webhook notification"
```

---

## Task 15: 文档同步

**Files:**
- Modify: `docs/deployment.md`
- Modify: `docs/runbook.md`
- Modify: `docs/PROGRESS.md`

- [ ] **Step 1: 更新 docs/deployment.md**

添加以下章节：

**Docker Secrets 管理**（新增章节）：
- 说明 `init_secrets.sh` 用法
- 列出 5 个 secret 文件名和对应变量
- 说明 Settings 的 `/run/secrets/` 回退机制
- 说明 `validate_env.sh` 的兼容行为

**Sentry 错误追踪**（新增章节）：
- 前端：`VITE_SENTRY_DSN` 环境变量
- 后端：`SENTRY_DSN` 环境变量
- 说明不设置 DSN 时完全不影响运行

**告警 Webhook**（新增章节）：
- `ALERT_WEBHOOK` 环境变量
- 钉钉/飞书 webhook 格式

**备份恢复验证**（追加到备份章节）：
- `verify_backup.sh` 用法
- 月度自动验证 cron

**Prometheus 指标**（追加到监控章节）：
- `/api/metrics/prometheus` 端点改用 prometheus-client
- 新增 HTTP 请求计数/延迟指标
- 内网访问限制

- [ ] **Step 2: 更新 docs/runbook.md**

添加：
- Sentry 告警处理流程
- `health_alert.sh` 日志查看
- 备份验证失败排查

- [ ] **Step 3: 更新 docs/PROGRESS.md**

在"最近更新"区域添加条目：
- 2026-04-15: Docker Secrets 密钥管理
- 2026-04-15: Sentry 前后端错误追踪
- 2026-04-15: 备份恢复自动验证
- 2026-04-15: Prometheus 指标扩展（prometheus-client）
- 2026-04-15: 日志持久化 + logrotate
- 2026-04-15: 运行时健康告警（webhook）

- [ ] **Step 4: Commit**

```bash
git add docs/deployment.md docs/runbook.md docs/PROGRESS.md
git commit -m "docs: update deployment/runbook/progress for secrets, sentry, metrics, alerting"
```

---

## Summary

| 优先级 | Task | 内容 |
|--------|------|------|
| **高** | 1-4 | Docker Secrets 密钥管理（init 脚本 → config 支持 → compose 集成 → validate 兼容） |
| **高** | 5-6 | 前端 Sentry 错误追踪 + Axios 5xx 上报 |
| **高** | 7 | 后端 Sentry 集成 |
| **高** | 8-9 | 备份恢复自动验证 + 月度 cron |
| **中** | 10-12 | Prometheus 指标扩展（定义 → 中间件埋点 → 端点改造） |
| **中** | 13 | 日志持久化 + logrotate |
| **中** | 14 | 运行时健康告警 webhook |
| 必做 | 15 | 文档同步 |

**阿里云迁移备注：**
- Docker Secrets 机制与阿里云 ACK (K8s) 的 Secret 概念对齐，迁移时可平滑过渡到 K8s Secrets 或阿里云 KMS
- OSS 备份上传已预留 `OSS_BUCKET` + `ossutil`，阿里云上只需配置即可启用
- Sentry 可使用阿里云 ARMS 替代或自建 Sentry
- Prometheus 指标兼容阿里云 ARMS Prometheus
