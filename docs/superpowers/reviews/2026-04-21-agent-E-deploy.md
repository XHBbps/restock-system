# Agent E — 部署 + 仓库整洁度审计

> Stage 1 / Agent E（Explore 类型，重派版）
> 问题总数：9 条 / Critical: 1 / Important: 6 / Minor: 2

---

## 问题 #1 — 根目录未跟踪的可执行文件缺少 .gitignore 规则

- 严重度：Critical
- 位置：`.gitignore` + 根目录
- 现状：`cloudflared-windows-amd64.exe`（65 MB）和 `Ai_project.lnk`（722 B）都是未跟踪文件，已进入仓库监视但未加 .gitignore。意外 push 会污染远程仓库。
- 建议：在 `.gitignore` 加入 `*.exe`、`*.lnk` 规则；同时确认 `cloudflared*.exe` 不应在仓库内，考虑改用 CI/CD 下载或 docker 卷挂载。
- 工作量：S

## 问题 #2 — 根目录 mypy 缓存未忽略导致仓库污染

- 严重度：Important
- 位置：`.gitignore`（缺失）+ `.mypy_cache/` / `backend/.mypy_cache/`
- 现状：`.gitignore` 虽然有 `.mypy_cache/` 但在第 28 行注释形式，根目录层的 `.mypy_cache/`（60 MB）和 `backend/.mypy_cache/`（20 MB）未被忽略；`git status` 未报告但仍需明确覆盖。
- 建议：确认 `.mypy_cache/` 和 `backend/.mypy_cache/` 条目在 `.gitignore` 的有效位置且未被后续 `!` 规则反转；根目录 `.mypy_cache/` 应加显式条目。
- 工作量：S

## 问题 #3 — docs/reviews 目录与 docs/superpowers/reviews 路径冲突

- 严重度：Important
- 位置：`docs/reviews/2026-04-19-full-audit.md` vs `docs/superpowers/reviews/`
- 现状：存在两份不同路径的 review 文档树；`docs/reviews/` 为上一阶段审计遗留，`docs/superpowers/reviews/` 为当前 Stage 0 产物。易造成 agent 混淆或文档分散。
- 建议：将 `docs/reviews/` 内容（如有有效信息）迁移或合并到 `docs/superpowers/reviews/`，然后删除 `docs/reviews/`；更新 `.gitignore` 若需排除。
- 工作量：S

## 问题 #4 — deploy/data/pg-local 70+ MB 数据目录用途不明

- 严重度：Minor
- 位置：`deploy/data/pg-local/`（73 MB）
- 现状：inventory 记录存在 73 MB 大小但 `docker-compose.dev.yml` 仅引用 `./data/pg-dev:`；`pg-local` 未被容器挂载，可能是历史遗留或本地开发的备用数据库。
- 建议：确认是否仍需；若已废弃，从工作区删除；若有用，加入 `.gitignore` 或 compose override。建议先 `git log -p -- deploy/data/pg-local/` 查其最后修改时间判断活跃度。
- 工作量：S

## 问题 #5 — 生产 Caddyfile 缺少 Cookie Secure 标记与 HSTS 预加载列表

- 严重度：Important
- 位置：`deploy/Caddyfile`（第 6 行 HSTS）
- 现状：HSTS 已配置 `max-age=31536000; includeSubDomains`，但缺 `preload` 指令；Caddy 未显式设置上游（backend）Cookie 的 `Secure` / `HttpOnly` / `SameSite` 属性，容器返回的会话 cookie 可能被中间人拦截。
- 建议：生产 Caddyfile 的 HSTS 加 `preload`；在 Caddy `header` 块加 `Cookie "Secure; HttpOnly; SameSite=Strict"` 针对认证 cookie，或确保后端（`backend/app/main.py`）在 FastAPI session middleware 中配置了这些安全属性。
- 工作量：M

## 问题 #6 — CI 工作流缺少部署前的分支保护检查

- 严重度：Important
- 位置：`.github/workflows/deploy.yml`（第 41-49 行）
- 现状：`check-ci` job 只验证 backend 和 frontend 两个 CI check 通过，但未检查 PR review / branch protection rule 状态；allow `workflow_dispatch` 无需 PR 直接部署，风险是绕过代码评审。
- 建议：考虑在 `deploy.yml` 增加 `check-pr-merged` 校验（若走 PR 路线）或在仓库 Settings → Branch protection 配置强制 review；如 `workflow_dispatch` 需保留（应急部署），应在文档明确标注需人工批准（可用 GitHub environment approval）。
- 工作量：M

## 问题 #7 — deploy/scripts 缺乏备份验证与回滚测试

- 严重度：Important
- 位置：`deploy/scripts/deploy.sh`（第 57 行）、`backup_cron_setup.sh`、`restore_db.sh`
- 现状：`deploy.sh` 调用 `pg_backup.sh`（存在）但无备份可用性检查；`rollback.sh` 存在但 `deploy.sh` 只在失败后调用且打印 "NOTE: database rollback is not automatic"，实际数据库不会自动回滚。
- 建议：在 `deploy.sh` 备份后验证备份文件大小 / MD5；添加可选的 pre-deploy 模拟回滚演练（dry-run）；补充文档说明 DB 回滚需手动 `restore_db.sh` 并确认 schema 一致。
- 工作量：L

## 问题 #8 — 生产 docker-compose.yml 环境变量硬编码在容器定义中

- 严重度：Important
- 位置：`deploy/docker-compose.yml`（第 9-20 行的 `x-backend-env` anchor）
- 现状：`SAIHU_CLIENT_ID`, `SAIHU_CLIENT_SECRET`, `LOGIN_PASSWORD`, `JWT_SECRET` 等敏感值引用 `${VAR_NAME}` 但源自 `.env` 文件；`.env` 应被 `.gitignore` 但若误 push 将泄露。生产 build 中无 secret rotation 机制。
- 建议：确保 `.env` 在 `.gitignore` 中（已确认）；生产部署改用 CI/CD secrets 注入或 Kubernetes Secret；在 deploy script 中验证 `JWT_SECRET` 不等于 dev 默认值；考虑加 pre-flight check `validate_env.sh` 验证所有必需的 secret 已定义。
- 工作量：M

## 问题 #9 — docs/superpowers/plans 目录未清理已完成任务

- 严重度：Minor
- 位置：`docs/superpowers/plans/`（35+ .md 文件）
- 现状：所有 plan 文件（如 `2026-04-09-*` 到 `2026-04-21-*`）仍在目录内；大多数已完成（按 session-context 记录的完成 commit）但未归档；当目录增长到 50+ 文件时搜索和导航变困难。
- 建议：创建 `docs/superpowers/plans/archived/` 目录，将完成时间 > 7 天的 plan 按月份移入；保留最近 3 个 plan 和当前正在执行的 plan 在主目录；更新 PROGRESS.md 为其建立索引。
- 工作量：S
