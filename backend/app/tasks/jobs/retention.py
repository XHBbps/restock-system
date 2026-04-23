"""Retention purge job (task_run / inventory_history / exports / stuck_generating)。

Cron 触发时间：每天 04:00（由 scheduler 注册），也可手动 enqueue。

四连：
- `purge_task_run`：task_run 表的 success/failed/skipped/cancelled 记录
  超过 retention_task_run_days（默认 90 天）删除。保留 pending/running（活跃状态）。
- `purge_inventory_history`：inventory_snapshot_history 超过
  retention_inventory_history_days（默认 180 天，原 daily_archive 90 天；
  配置可调）删除。daily_archive 02:00 跑的 retention 也会做，此处是兜底
  （幂等，无数据冗余风险）。
- `purge_exports`：excel_export_log 关联的 snapshot 文件超过
  retention_exports_days（默认 60 天）删除磁盘 Excel，并把对应 log 的
  file_purged_at 写 now。留 log 行作审计，下载端点据此返回 410 Gone。
- `purge_stuck_generating`：suggestion_snapshot.generation_status='generating'
  超过 retention_stuck_generating_hours（默认 1 小时）的行标为 failed + 写
  generation_error。兜底 OOM / worker 被 kill 留下的永久 generating 行。
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.core.timezone import now_beijing
from app.db.session import async_session_factory
from app.models.excel_export_log import ExcelExportLog
from app.models.inventory import InventorySnapshotHistory
from app.models.suggestion_snapshot import SuggestionSnapshot
from app.models.task_run import TaskRun
from app.tasks.jobs import JobContext, register

logger = get_logger(__name__)


async def purge_task_run(db: AsyncSession, days: int) -> int:
    """清理 task_run 终态行超过 `days` 的记录，返回删除行数。"""
    if days <= 0:
        return 0
    cutoff = now_beijing() - timedelta(days=days)
    result = await db.execute(
        delete(TaskRun).where(
            TaskRun.status.in_(("success", "failed", "skipped", "cancelled")),
            TaskRun.created_at < cutoff,
        )
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


async def purge_inventory_history(db: AsyncSession, days: int) -> int:
    """清理 inventory_snapshot_history 超过 `days` 的记录，返回删除行数。"""
    if days <= 0:
        return 0
    cutoff_date = (now_beijing() - timedelta(days=days)).date()
    result = await db.execute(
        delete(InventorySnapshotHistory).where(
            InventorySnapshotHistory.snapshot_date < cutoff_date
        )
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


async def purge_exports(
    db: AsyncSession,
    days: int,
    storage_root: Path,
) -> int:
    """清理磁盘 Excel + 标记 excel_export_log.file_purged_at，返回处理行数。

    处理逻辑：
    1. 查 excel_export_log.action='generate' 且 performed_at 超过 `days`
       且 file_purged_at IS NULL 的所有记录（同一 snapshot 可能多条 log，
       按 snapshot_id 去重）。
    2. 对每个 snapshot 读取 SuggestionSnapshot.file_path，删磁盘文件
       （不存在则跳过），随后把该 snapshot 所有 generate log 的
       file_purged_at 写 now（同一 snapshot 只清一次）。
    """
    if days <= 0:
        return 0
    cutoff = now_beijing() - timedelta(days=days)
    rows = (
        await db.execute(
            select(ExcelExportLog.snapshot_id)
            .where(ExcelExportLog.action == "generate")
            .where(ExcelExportLog.performed_at < cutoff)
            .where(ExcelExportLog.file_purged_at.is_(None))
            .distinct()
        )
    ).scalars().all()
    if not rows:
        return 0

    snapshot_ids = list(rows)
    snapshot_rows = (
        await db.execute(
            select(SuggestionSnapshot.id, SuggestionSnapshot.file_path).where(
                SuggestionSnapshot.id.in_(snapshot_ids)
            )
        )
    ).all()

    now = now_beijing()
    purged_count = 0
    for snapshot_id, file_path in snapshot_rows:
        if file_path:
            file_abs = (storage_root / file_path).resolve()
            # 防止 path traversal：删文件前验证仍位于 storage_root 下
            try:
                file_abs.relative_to(storage_root.resolve())
            except ValueError:
                logger.warning(
                    "retention_skip_escaped_path",
                    snapshot_id=snapshot_id,
                    file_path=file_path,
                )
                continue
            if file_abs.exists():
                try:
                    file_abs.unlink()
                except OSError as exc:
                    logger.warning(
                        "retention_unlink_failed",
                        snapshot_id=snapshot_id,
                        file_path=str(file_abs),
                        error=str(exc),
                    )
                    continue
        await db.execute(
            update(ExcelExportLog)
            .where(ExcelExportLog.snapshot_id == snapshot_id)
            .where(ExcelExportLog.action == "generate")
            .where(ExcelExportLog.file_purged_at.is_(None))
            .values(file_purged_at=now)
        )
        purged_count += 1
    return purged_count


async def purge_stuck_generating(db: AsyncSession, hours: int) -> int:
    """把卡在 generation_status='generating' 超过 N 小时的 snapshot 标 failed。

    进程崩 / OOM / worker 被 docker stop 会留下永远 generating 的 snapshot，
    本函数提供兜底清理。
    """
    if hours <= 0:
        return 0
    cutoff = now_beijing() - timedelta(hours=hours)
    result = await db.execute(
        update(SuggestionSnapshot)
        .where(SuggestionSnapshot.generation_status == "generating")
        .where(SuggestionSnapshot.exported_at < cutoff)
        .values(
            generation_status="failed",
            generation_error=f"stuck in generating > {hours}h, cleaned by retention",
        )
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


@register("retention_purge")
async def retention_purge_job(ctx: JobContext) -> None:
    """每天 04:00 Cron 清理 task_run / inventory_history / exports / stuck_generating。"""
    settings = get_settings()
    storage_root = Path(settings.export_storage_dir).resolve()
    await ctx.progress(current_step="开始清理 task_run", total_steps=4)

    async with async_session_factory() as db:
        deleted_task = await purge_task_run(db, settings.retention_task_run_days)
        await db.commit()
    logger.info("retention_purge_task_run", deleted=deleted_task)
    await ctx.progress(
        current_step="清理 inventory_snapshot_history",
        step_detail=f"task_run 删 {deleted_task} 行",
    )

    async with async_session_factory() as db:
        deleted_inv = await purge_inventory_history(
            db, settings.retention_inventory_history_days
        )
        await db.commit()
    logger.info("retention_purge_inventory_history", deleted=deleted_inv)
    await ctx.progress(
        current_step="清理 exports 磁盘 + log",
        step_detail=f"inventory_history 删 {deleted_inv} 行",
    )

    async with async_session_factory() as db:
        purged_exports = await purge_exports(
            db, settings.retention_exports_days, storage_root
        )
        await db.commit()
    logger.info("retention_purge_exports", purged=purged_exports)

    async with async_session_factory() as db:
        stuck_failed = await purge_stuck_generating(
            db, settings.retention_stuck_generating_hours
        )
        await db.commit()
    logger.info("retention_purge_stuck_generating", failed=stuck_failed)

    await ctx.progress(
        current_step="完成",
        step_detail=(
            f"task_run {deleted_task} / inventory_history {deleted_inv} / "
            f"exports {purged_exports} / stuck_generating {stuck_failed}"
        ),
    )
