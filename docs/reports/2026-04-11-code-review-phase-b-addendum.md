# Code Review Phase B Addendum（2026-04-11）

> **关联工作**：本报告是 `docs/superpowers/plans/2026-04-11-code-review-fixes.md` Phase B 的产出
> **目的**：补跑首轮 review 中被 CodeRabbit rate limit 拦截的 3 个目录切片
> **工具**：CodeRabbit CLI 0.4.1（通过 WSL 调用，--plain -t uncommitted 模式）

---

## 切片执行情况

| 切片 | 文件数 | 状态 | findings |
|---|---|---|---|
| `backend/alembic` | 7 | ✅ 完成 | **1** |
| `deploy` | 4 | ✅ 完成 | **1** |
| `backend/tests` | 18 | 🔄 重试中（rate limit cooldown） | 待补 |

---

## 🔴/🟡/🔵 Findings 清单

### F-B1. `backend/alembic/versions/20260409_0935_add_allocation_snapshot.py` — 文档与代码不一致

- **类型**：Info（文档腐烂）
- **位置**：`backend/alembic/versions/20260409_0935_add_allocation_snapshot.py:3-5`
- **问题**：模块顶部 docstring 写的 `Revises: 20260408_1500`，但代码 `down_revision` 实际是 `0001_initial`。docstring 与运行时行为不一致。
- **影响**：不影响功能（Alembic 只看 `down_revision` 变量），但维护时容易困惑。
- **修复**：二选一
  - **选 A**（推荐）：把 docstring 改为与变量一致：
    ```diff
    -Revises: 20260408_1500
    +Revises: 0001_initial
    ```
  - **选 B**：把 `down_revision` 改为 `20260408_1500_initial`（**风险高，会改变迁移链**，不推荐）
- **优先级**：P3
- **建议**：选 A，搭车下次小修

### F-B2. `deploy/scripts/restore_db.sh` — 数据库未就绪 race condition

- **类型**：Warning（脚本竞态）
- **位置**：`deploy/scripts/restore_db.sh:20-22`
- **问题**：脚本先 `docker compose up -d db` 启动数据库容器，紧接着就 `psql` 灌数据。但容器启动 ≠ PostgreSQL 接受连接，可能在数据库还没 ready 时就开始灌入，触发连接失败。
- **复现概率**：冷启动（容器从镜像首次启动）时高，热启动时低。
- **修复**（CodeRabbit 建议，已采纳）：
  ```diff
   docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d db
  +
  +echo "Waiting for database to be ready..."
  +until docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db pg_isready -U postgres; do
  +    sleep 1
  +done
  +
   gzip -dc "$BACKUP_FILE" | docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T db \
       psql -U postgres -d replenish
  ```
- **建议增强**：加 timeout 防止无限等待（30s 上限）
- **优先级**：P2（部署脚本，影响灾备恢复路径的可靠性）

### F-B3. `backend/tests` 切片 — 待补

- **状态**：在第二次尝试时仍被 rate limit 拦截，约 30 分钟后再补
- **预期范围**：18 个测试文件（test_engine_*、test_health_endpoints、test_suggestion_patch 等）
- **重试命令**：
  ```bash
  wsl
  export PATH="$HOME/.local/bin:$PATH"
  cd /mnt/e/Ai_project/restock_system
  coderabbit review --plain -t uncommitted --dir backend/tests > /tmp/cr-tests.txt 2>&1
  tail -50 /tmp/cr-tests.txt
  ```

---

## 修复建议汇总

| 优先级 | finding | 工作量 | 命令/动作 |
|---|---|---|---|
| **P2** | F-B2 restore_db.sh 加 pg_isready 等待 | 5 min | 直接编辑 deploy/scripts/restore_db.sh |
| **P3** | F-B1 alembic docstring 修正 | 2 min | 直接编辑 docstring |
| **P3** | F-B3 重跑 backend/tests 切片 | 5 min + 等 | 30 min cooldown 后再跑 |

---

## 与 Phase A / Phase C 的关系

- **Phase A**（已完成）：修复了 Critical 与 Warning 级别的 6 个 finding（C-1 SQL bug、C-2 mojibake、W-1/2/3 frontend guards、I-1 CSS、Task 4 .gitattributes、Task 6 gitignore），8 个 commit
- **Phase B**（本报告）：补跑了被 rate limit 拦截的 3 个切片中的 2 个，发现 2 个新 finding（1 Warning + 1 Info），都是设计/部署层面的小问题
- **Phase C**（`2026-04-11-engine-manual-review.md`）：人工评审引擎 6 步，0 Critical / 2 Warning（设计权衡）/ 5 Info

**整体收敛趋势**：项目代码质量稳定，所有 Phase 加起来无 Critical 阻塞，Warning 级别的问题都属于"应该改但不紧急"的范畴。
