# CI/CD 设计文档

**日期：** 2026-04-16  
**范围：** CI 问题修复 + 两阶段 CD 加固与演进  
**项目规模：** 1-5 名内部用户

---

## 1. 背景与目标

### 当前问题

1. **CI 失败**：`backend/tests/unit/test_metrics_snapshot_api.py` 中 2 个单元测试失败。
   根本原因：`app/api/metrics.py` 的 `get_dashboard_overview` 在快照缺失或过期时未自动调用 `enqueue_task`，但测试已按新行为写好。

2. **deploy.yml `check-ci` 有缺陷**：
   - 未使用 `filter: 'latest'`，可能命中旧的失败记录
   - 默认 `per_page: 30`，check run 较多时可能截断

### 目标

- 修复 CI，使所有单元测试通过
- 加固 `deploy.yml` 的 `check-ci` 逻辑
- 为后续迁移到 GHCR 预构建镜像流水线奠定基础

---

## 2. 第一阶段：CI 修复 + deploy.yml 加固

### 2.1 修复 `get_dashboard_overview` 自动入队逻辑

**文件：** `backend/app/api/metrics.py`

在以下两种情况下补全 `enqueue_task` 调用：

**情况 A — 快照不存在**（当前 `metrics.py:462-468`）

```
修前：返回 snapshot_status="missing"，不入队
修后：调用 enqueue_task(dedupe_key=REFRESH_DASHBOARD_JOB_NAME, trigger_source="auto")
      用返回的 task_id 设置 snapshot_task_id，返回 snapshot_status="refreshing"
```

**情况 B — 快照存在但缺少新字段**（`needs_refresh=True`，`metrics.py:454-460`）

```
修前：active_task 为 None 且 needs_refresh 时返回 snapshot_status="missing"，不入队
修后：active_task 为 None 且 needs_refresh 时调用 enqueue_task(...)
      返回 snapshot_status="refreshing"，snapshot_task_id=新任务id
```

**边界处理：**
- `dedupe_key` 复用现有 `REFRESH_DASHBOARD_JOB_NAME`，并发请求幂等，不会重复入队
- `trigger_source` 必须用 `"manual"`（`enqueue_task` 硬校验只接受 `"scheduler"` 或 `"manual"`，传 `"auto"` 会抛 `ValueError`）；用 `payload={"triggered_by": "auto_dashboard_refresh"}` 区别于手动刷新的 `"manual_refresh"`
- 修复后现有 2 个失败测试通过，其余 258 个测试不受影响

### 2.2 修复 deploy.yml `check-ci` 步骤

**文件：** `.github/workflows/deploy.yml`

将 `check-ci` job 中的 `github-script` 改为：

```javascript
const ref = '${{ github.event.inputs.ref }}';
const checkRuns = await github.paginate(github.rest.checks.listForRef, {
  owner: context.repo.owner,
  repo: context.repo.repo,
  ref: ref,
  filter: 'latest',   // 只取每个 suite 最近一次，天然排除旧失败记录
  per_page: 100,
});

const ciBackend  = checkRuns.find(c => c.name === 'backend');
const ciFrontend = checkRuns.find(c => c.name === 'frontend');

if (!ciBackend || ciBackend.conclusion !== 'success') {
  core.setFailed(`Backend CI has not passed for ref ${ref}`);
}
if (!ciFrontend || ciFrontend.conclusion !== 'success') {
  core.setFailed(`Frontend CI has not passed for ref ${ref}`);
}
core.info('CI checks passed');
```

**关键变更：**
- `filter: 'latest'`：API 层面只返回每个 check suite 最新一次的 run，解决旧记录问题
- `per_page: 100`：避免默认 30 条截断
- `github.paginate`：自动翻页，彻底消除分页截断风险

### 2.3 改善部署通知

**文件：** `.github/workflows/deploy.yml`

`Notify deploy result` 步骤的 webhook payload 加入上下文字段：

```bash
curl -sf -X POST "${{ secrets.DEPLOY_NOTIFY_WEBHOOK }}" \
  -H "Content-Type: application/json" \
  -d "{
    \"text\": \"Deploy ${STATUS} | ref: ${REF} | by: ${{ github.actor }} | run: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}\"
  }" || true
```

### 2.4 Secrets 文档化

在 `docs/deployment.md` 补充 GitHub Actions secrets 清单：

| Secret | 必填 | 说明 |
|--------|------|------|
| `DEPLOY_HOST` | ✅ | 服务器 IP 或域名 |
| `DEPLOY_USER` | ✅ | SSH 登录用户名 |
| `DEPLOY_SSH_KEY` | ✅ | SSH 私钥（完整内容） |
| `DEPLOY_PATH` | ✅ | 服务器上仓库根目录绝对路径 |
| `DEPLOY_NOTIFY_WEBHOOK` | 可选 | 飞书 / Slack webhook URL |

**不改动的部分：**
- 触发方式保持 `workflow_dispatch`（手动）
- `deploy.sh` 脚本逻辑不变
- SSH 连接方式不变

---

## 3. 第二阶段：GHCR 镜像流水线（后续实施）

### 3.1 目标

将 `docker build` 从服务器移至 CI，服务器只做 `docker pull` + `docker compose up`，部署时间从数分钟压缩到约 30 秒。

### 3.2 ci.yml 新增 `publish` job

在 CI 三个 job（backend / frontend / docker-build）全部通过后，新增：

```yaml
publish:
  needs: [backend, frontend, docker-build]
  if: github.ref == 'refs/heads/master'
  runs-on: ubuntu-latest
  permissions:
    contents: read
    packages: write
  steps:
    - uses: actions/checkout@v4
    - name: Log in to GHCR
      uses: docker/login-action@v3
      with:
        registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}   # 内置，无需额外配置
    - name: Build and push backend
      uses: docker/build-push-action@v6
      with:
        context: ./backend
        push: true
        tags: |
          ghcr.io/${{ github.repository_owner }}/restock-backend:sha-${{ github.sha }}
          ghcr.io/${{ github.repository_owner }}/restock-backend:latest
    - name: Build and push frontend
      uses: docker/build-push-action@v6
      with:
        context: ./frontend
        push: true
        tags: |
          ghcr.io/${{ github.repository_owner }}/restock-frontend:sha-${{ github.sha }}
          ghcr.io/${{ github.repository_owner }}/restock-frontend:latest
```

**Tag 策略：** `sha-<完整commit hash>` + `latest`。不引入 semver，保持简单。

### 3.3 docker-compose.yml 改动

`worker` 和 `scheduler` 与 `backend` 共用同一镜像（均引用 `x-backend-build` 别名），三个服务都需要加 `image:` 字段。`build:` 保留供本地开发使用。  
`GHCR_OWNER` 通过 `deploy/.env` 注入（值为 GitHub 用户名，如 `XHBbps`）：

```yaml
backend:
  image: ghcr.io/${GHCR_OWNER}/restock-backend:${IMAGE_TAG:-latest}
  build: *backend-build
  # ... 其余不变

worker:
  image: ghcr.io/${GHCR_OWNER}/restock-backend:${IMAGE_TAG:-latest}
  build: *backend-build
  # ... 其余不变

scheduler:
  image: ghcr.io/${GHCR_OWNER}/restock-backend:${IMAGE_TAG:-latest}
  build: *backend-build
  # ... 其余不变

frontend:
  image: ghcr.io/${GHCR_OWNER}/restock-frontend:${IMAGE_TAG:-latest}
  build:
    context: ../frontend
    dockerfile: Dockerfile
  # ... 其余不变
```

`IMAGE_TAG` 默认 `latest`，deploy.yml SSH script 在 checkout 后通过 `git rev-parse HEAD` 解析。

### 3.4 deploy.yml + deploy.sh 改动

**deploy.yml SSH script**：在 `git pull` 后导出 `IMAGE_TAG`，其余不变。`$ENV_FILE` / `$COMPOSE_FILE` 均在 `deploy.sh` 内部定义，不能在 SSH script 中提前引用：

```bash
set -euo pipefail
cd "${{ secrets.DEPLOY_PATH }}"
git fetch --all --tags
git checkout "${{ github.event.inputs.ref }}"
git pull --ff-only origin "${{ github.event.inputs.ref }}"
export IMAGE_TAG="sha-$(git rev-parse HEAD)"   # cd 已完成，无需 -C
bash deploy/scripts/deploy.sh
```

**deploy.sh**：将第 48 行的 `build` 替换为 `pull`，同时补上 `worker` / `scheduler`（它们共享 backend 镜像，一次 pull 即可，但显式列出意图更清晰）：

```bash
# 旧（删除）：
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build backend frontend

# 新（替换）：
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" pull backend worker scheduler frontend
```

> `IMAGE_TAG` 由 SSH script `export` 传入，`deploy.sh` 作为子进程自动继承。`docker compose` 通过 compose 文件中的 `${IMAGE_TAG:-latest}` 读取该值。

### 3.5 触发策略（可选）

第二阶段默认仍保持手动 `workflow_dispatch`。如需自动上线，可在 deploy.yml 追加：

```yaml
on:
  workflow_dispatch:
    # ... 现有配置保留
  push:
    tags:
      - 'v*'   # 打 tag = 明确的"我要上这个版本"信号
```

打 tag 触发比 push master 触发更可控，适合小团队。**此项为可选，不在第二阶段强制实施。**

### 3.6 所需新增配置

| 项目 | 类型 | 说明 |
|------|------|------|
| `GITHUB_TOKEN` | Actions 内置 secret | 无需手动配置，GHCR 登录用 |
| `GHCR_OWNER` | `deploy/.env` 环境变量 | GitHub 用户名（如 `XHBbps`），docker-compose image 引用用 |

无需引入任何付费服务或外部依赖。

---

## 4. 实施顺序

```
第一阶段（当下）
  T1. 修复 get_dashboard_overview 自动入队逻辑（metrics.py）
  T2. 修复 deploy.yml check-ci（filter+per_page+paginate）
  T3. 改善部署通知 webhook payload
  T4. 在 docs/deployment.md 补充 secrets 清单

第二阶段（有服务器后）
  T5. ci.yml 新增 publish job（GHCR build & push）
  T6. docker-compose.yml 加 image: 字段
  T7. deploy.yml SSH script 改为 pull 镜像
  T8. deploy.sh 删除 docker compose build 行
  T9. （可选）deploy.yml 加 push: tags: ['v*'] 触发
```

---

## 5. 验证标准

| 检查点 | 通过条件 |
|--------|----------|
| CI backend job | pytest 全部通过（含修复后的 2 个测试） |
| CI frontend job | build + test:coverage + audit 全部通过 |
| deploy.yml check-ci | 手动触发后正确识别 backend/frontend CI 状态 |
| 第二阶段 publish job | GHCR 上可见 `sha-<hash>` 和 `latest` 两个 tag |
| 第二阶段部署 | 服务器无需 docker build，pull 后容器正常启动 |
