"""订单信息匹配确认导入后台任务。"""

from __future__ import annotations

from sqlalchemy import update

from app.core.exceptions import NotFound, ValidationFailed
from app.core.timezone import now_beijing
from app.db.session import async_session_factory
from app.models.order_info_match_import import OrderInfoMatchImportFile
from app.services.order_edit import (
    apply_parsed_order_info_match,
    parse_order_info_match_workbook,
    parse_requested_fields,
)
from app.tasks.jobs import JobContext, register

JOB_NAME = "order_info_match_apply"


@register(JOB_NAME)
async def order_info_match_apply_job(ctx: JobContext) -> None:
    file_id = ctx.payload.get("file_id")
    user_id = ctx.payload.get("user_id")
    if not isinstance(file_id, int) or not isinstance(user_id, int):
        raise ValidationFailed("订单信息匹配导入任务参数缺失")

    await ctx.progress(current_step="排队中", step_detail="准备读取导入文件", total_steps=3)
    async with async_session_factory() as db:
        import_file = await db.get(OrderInfoMatchImportFile, file_id)
        if import_file is None:
            raise NotFound("订单信息匹配导入文件不存在")
        now = now_beijing()
        if import_file.expires_at <= now:
            await _consume_import_file(file_id)
            raise ValidationFailed("订单信息匹配导入文件已过期，请重新上传")
        if import_file.consumed_at is not None or not import_file.content:
            raise ValidationFailed("订单信息匹配导入文件已被消费，请重新上传")

        fields = parse_requested_fields(import_file.fields)
        content = bytes(import_file.content)

    updated = 0
    total = 0
    try:
        await ctx.progress(current_step="解析文件", step_detail="正在校验 Excel 内容", total_steps=3)
        async with async_session_factory() as db:
            parsed = await parse_order_info_match_workbook(db, fields=fields, content=content)

        await ctx.progress(current_step="写入订单", step_detail="已处理 0 / 总数 0", total_steps=3)

        async def report_progress(done: int, count: int) -> None:
            nonlocal total
            total = count
            await ctx.progress(current_step="写入订单", step_detail=f"已处理 {done} / 总数 {count}")

        async with async_session_factory() as db:
            updated = await apply_parsed_order_info_match(
                db,
                parsed=parsed,
                user_id=user_id,
                progress_callback=report_progress,
            )
        await ctx.progress(
            current_step="完成",
            step_detail=f"已处理 {updated} / 总数 {total}",
            result_summary=f"已更新 {updated} 条订单",
            result_payload={"updatedOrderCount": updated},
        )
    finally:
        await _consume_import_file(file_id)


async def _consume_import_file(file_id: int) -> None:
    async with async_session_factory() as db:
        await db.execute(
            update(OrderInfoMatchImportFile)
            .where(OrderInfoMatchImportFile.id == file_id)
            .values(content=b"", consumed_at=now_beijing())
        )
        await db.commit()
