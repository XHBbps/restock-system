# Full Audit Report — 2026-04-19

> 续审时间：2026-04-20  
> 审查方式：主 agent 本地只读审查；尝试并行派发 3 个子审查器，但本轮因超时/模型可用性未形成可采信结论，以下 findings 全部来自主审查二次实证。

## 1. 总览

- 本轮确认待修改项 8 条：P1 × 6，P2 × 2
- 覆盖重点：后端导出链路、补货建议/历史列表、Dashboard 快照展示、Plan A 死代码残留
- 未发现需要按“小团队 + 单机部署”尺度上升到分布式改造级别的问题

## 2. 待修改项

### [P1] Dashboard 仍使用已删除的 `pushed_count` 字段，首页进度会显示 `NaN/undefined`
- **分类**：功能完整度 / 交互体验
- **子系统**：前端 Dashboard + 后端指标契约
- **证据**
  - 文件：`frontend/src/api/dashboard.ts:29`
  - 文件：`frontend/src/views/WorkspaceView.vue:101`
  - 文件：`backend/app/api/metrics.py:64`
  - 代码片段：
    ```ts
    export interface DashboardOverview {
      suggestion_item_count: number
      pushed_count: number
    }
    ```
    ```vue
    ? Math.round((data.pushed_count / data.suggestion_item_count) * 100)
    <span class="progress-text">已推送 {{ data.pushed_count }} / 总计 {{ data.suggestion_item_count }}</span>
    ```
    ```py
    class DashboardOverviewPayload(BaseModel):
        suggestion_item_count: int
        exported_count: int = 0
    ```
- **影响**：Plan A 已把“推送”改成“导出”，后端只返回 `exported_count`。当前首页会把 `undefined` 参与百分比计算，进度条和文案都可能失真。
- **最小修复**：前端 `DashboardOverview` 与 `WorkspaceView.vue` 全部改读 `exported_count`，文案改为“已导出”；同步修正对应测试 mock。
- **二次验证**：已

### [P1] 历史记录页“未提交/已导出”筛选仍是前端二次过滤，分页总数与列表内容会错位
- **分类**：交互体验 / 逻辑漏洞
- **子系统**：前端历史页 + 后端建议单列表
- **证据**
  - 文件：`frontend/src/views/HistoryView.vue:124`
  - 文件：`frontend/src/views/HistoryView.vue:136`
  - 文件：`frontend/src/views/HistoryView.vue:142`
  - 文件：`backend/app/api/suggestion.py:79`
  - 代码片段：
    ```ts
    const resp = await listSuggestions({
      status: resolveBackendStatus(displayStatus.value),
      page: page.value,
      page_size: pageSize.value,
    })
    const filtered = resp.items.filter((row) => {
      if (ds === 'pending') return row.snapshot_count === 0
      if (ds === 'exported') return row.snapshot_count > 0
      return true
    })
    rows.value = filtered
    total.value = resp.total
    ```
    ```py
    if status:
        base = base.where(Suggestion.status == status)
    total = (await db.execute(count_stmt)).scalar_one()
    ```
- **影响**：筛“未提交/已导出”时，后端统计的是全部 `draft`，前端只过滤当前页数据。结果会出现“页码/总数看起来还有数据，但当前页为空或条数明显偏少”。
- **最小修复**：把派生状态过滤下沉到后端查询（基于 `snapshot_count` / `EXISTS snapshot`），让 `items` 与 `total` 使用同一口径。
- **二次验证**：已

### [P1] 导出失败时已先把条目标记为 `exported`，会把条目永久卡死在“已导出但文件失败”
- **分类**：功能完整度 / 逻辑漏洞
- **子系统**：后端快照导出链路
- **证据**
  - 文件：`backend/app/api/snapshot.py:171`
  - 文件：`backend/app/api/snapshot.py:211`
  - 文件：`backend/app/api/suggestion.py:186`
  - 文件：`backend/app/api/snapshot.py:354`
  - 代码片段：
    ```py
    await db.execute(
        update(SuggestionItem)
        .where(SuggestionItem.id.in_(body.item_ids))
        .values(export_status="exported", exported_snapshot_id=snapshot.id, exported_at=now)
    )
    ...
    except Exception as exc:
        snapshot.generation_status = "failed"
        snapshot.generation_error = str(exc)
        await db.commit()
    ```
    ```py
    if item.export_status == "exported":
        raise ValidationFailed("已导出的条目不可编辑")
    ```
    ```py
    if snap.generation_status != "ready":
        raise HTTPException(status_code=409, detail="文件尚未就绪或生成失败")
    ```
- **影响**：一旦 `wb.save()` 或目录/磁盘写入失败，快照会记为 `failed`，但条目已被改成 `exported`。此后条目既不能编辑，也不能重新导出，形成业务死锁。
- **最小修复**：把 `SuggestionItem.export_status` 的更新延后到文件成功落盘之后；或者在异常分支显式回滚条目的导出标记。
- **二次验证**：已

### [P1] 快照创建缺少行级锁，和“开启新周期/并发导出”会发生竞态
- **分类**：逻辑漏洞 / 并发安全
- **子系统**：后端快照导出链路 + 生成开关
- **证据**
  - 文件：`backend/app/api/snapshot.py:53`
  - 文件：`backend/app/api/snapshot.py:83`
  - 文件：`backend/app/api/config.py:215`
  - 文件：`backend/app/models/suggestion_snapshot.py:28`
  - 代码片段：
    ```py
    sug = (
        await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id))
    ).scalar_one_or_none()
    ...
    max_version = (
        await db.execute(
            select(func.coalesce(func.max(SuggestionSnapshot.version), 0)).where(
                SuggestionSnapshot.suggestion_id == suggestion_id
            )
        )
    ).scalar_one()
    ```
    ```py
    if patch.enabled:
        await db.execute(
            update(Suggestion)
            .where(Suggestion.status == "draft")
            .values(status="archived", archived_trigger="admin_toggle")
        )
    ```
    ```py
    UniqueConstraint("suggestion_id", "version", name="uq_snapshot_suggestion_version")
    ```
- **影响**：
  - 两个并发导出请求会先后读到同一个 `max(version)`，后发请求可能撞上唯一约束，返回 500；
  - 导出校验通过后，如果管理员同时“开启新周期”把 draft 批量归档，当前请求仍可能继续为已归档建议单创建快照，破坏周期边界。
- **最小修复**：对 `Suggestion` 主记录和目标 `SuggestionItem` 加 `SELECT ... FOR UPDATE`；版本号生成改成“锁内计算 + 插入”，并把唯一约束冲突转成业务 409。
- **二次验证**：已

### [P1] 登录失败计数在并发下会丢增量，降低锁定阈值的实际约束力
- **分类**：逻辑漏洞 / 安全
- **子系统**：后端认证
- **证据**
  - 文件：`backend/app/api/auth.py:126`
  - 代码片段：
    ```py
    current_failed = attempt.failed_count if attempt is not None else 0
    new_count = current_failed + 1
    ...
    stmt = stmt.on_conflict_do_update(
        index_elements=[LoginAttempt.source_key],
        set_={
            "failed_count": failed_count,
            "locked_until": locked_until,
            "updated_at": now,
        },
    )
    ```
- **影响**：多个并发错误登录如果都基于同一个旧 `failed_count` 计算，就会互相覆盖写入；对公网暴露场景下，这会让暴力尝试更容易绕过锁定节奏。
- **最小修复**：把失败次数改成数据库端原子递增；或先 `SELECT ... FOR UPDATE` 锁定该来源行，再计算并写回。
- **二次验证**：已

### [P1] Reaper 回收后，原 Worker 仍能无条件把任务终态覆盖回 `success/failed`
- **分类**：逻辑漏洞 / 任务队列
- **子系统**：后端 TaskRun 队列
- **证据**
  - 文件：`backend/app/tasks/reaper.py:64`
  - 文件：`backend/app/tasks/worker.py:205`
  - 代码片段：
    ```py
    UPDATE task_run
    SET status = 'failed'
    WHERE status = 'running'
      AND lease_expires_at < now()
    ```
    ```py
    await db.execute(
        update(TaskRun)
        .where(TaskRun.id == task_id)
        .values(status="success", finished_at=now_beijing())
    )
    ```
- **影响**：若心跳短暂失联，reaper 先把任务判死，原 worker 仍可能继续执行并把状态改回成功；此时去重已释放，新的同类任务也可能已入队，最终造成状态失真甚至重复副作用。
- **最小修复**：worker 的心跳、进度、终态更新都带上 `status='running'` 与 `worker_id` 条件，并在更新不到行时主动停止后续执行。
- **二次验证**：已

### [P2] 修改 `calc_enabled` 不会立即 reload scheduler，自动计算开关无法实时生效
- **分类**：功能完整度
- **子系统**：后端配置 / 调度器
- **证据**
  - 文件：`backend/app/api/config.py:167`
  - 文件：`backend/app/tasks/scheduler.py:120`
  - 代码片段：
    ```py
    if {"sync_interval_minutes", "calc_cron", "scheduler_enabled"} & updates.keys():
        await reload_scheduler()
    ```
    ```py
    if calc_enabled:
        scheduler.add_job(..., id="trigger_calc_engine")
    else:
        scheduler.remove_job("trigger_calc_engine")
    ```
- **影响**：用户在全局配置里关闭/开启自动计算后，现有 APScheduler 作业不会立刻增删，直到其他调度字段变更或服务重启才会同步。
- **最小修复**：把 `calc_enabled` 加入 reload 触发集合，并补一条“开关切换即刻增删 `trigger_calc_engine`”的测试。
- **二次验证**：已

### [P2] Plan A 之后仍残留 `partial/pushed` 旧状态分支，容易误导后续维护
- **分类**：代码质量 / 死代码残留
- **子系统**：后端建议单与 Dashboard 查询
- **证据**
  - 文件：`backend/app/api/suggestion.py:31`
  - 文件：`backend/app/api/suggestion.py:136`
  - 文件：`backend/app/api/suggestion.py:274`
  - 文件：`backend/app/api/metrics.py:327`
  - 文件：`backend/app/engine/runner.py:263`
  - 代码片段：
    ```py
    SUGGESTION_STATUS_SORT_ORDER: dict[str, int] = {
        "draft": 0,
        "partial": 1,
        "pushed": 2,
        "archived": 3,
        "error": 4,
    }
    ```
    ```py
    .where(Suggestion.status.in_(("draft", "partial")))
    ```
    ```py
    if sug.status == "pushed":
        raise ConflictError("已推送的建议单不可删除")
    ```
- **影响**：虽然当前枚举已收敛为 `draft / archived / error`，但运行路径仍保留旧状态判断；这会持续误导维护者，也让后续排障误以为系统还存在推送态。
- **最小修复**：清理 `partial/pushed` 相关排序、查询和文案残留，统一为导出模型口径。
- **二次验证**：已

## 3. 不构成 finding 但值得记录

- `403 toast` 抑制范围目前仅发现于 `frontend/src/api/config.ts:171` 的 `getGenerationToggle()`，没有看到进一步扩散。
- `restock_regions=[]` 在 `backend/app/core/restock_regions.py:25` 会被解析为 `None`（即“全部国家”），与文档口径一致。
- Reaper / heartbeat 基础不变式存在：`backend/app/tasks/worker.py:48` 已显式防止“心跳频率过低导致误杀”。

## 4. 本轮建议优先顺序

1. 先修 `snapshot.py` 的两条导出链路问题（失败回滚 + 并发锁）
2. 再修认证失败计数与 TaskRun reaper 终态竞争
3. 然后修 Dashboard `pushed_count → exported_count` 与历史页派生状态分页
4. 最后补 `calc_enabled` reload 与 `partial/pushed` 死代码清理

自检通过
