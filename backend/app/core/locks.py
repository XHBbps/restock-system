"""PostgreSQL advisory lock 键值集中定义。

所有 `pg_advisory_xact_lock` 用到的键都应在此文件常量化，避免散落在
各业务模块导致键值冲突或复用不清。键值设计规范：

- 使用 7 位十进制数（易于人工分配，Postgres bigint 空间充裕）
- 首位定性：7 = business engine，后续可扩 6 = sync、5 = retention 等
- 后 6 位递增，同一域内连续分配
"""

# 补货建议生成（engine/runner.run_engine）串行化。
ENGINE_RUN_ADVISORY_LOCK_KEY = 7429001
