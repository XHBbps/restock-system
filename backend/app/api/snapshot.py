"""Snapshot 相关 API 端点。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import UserContext, db_session, get_current_user, require_permission
from app.config import get_settings
from app.core.permissions import RESTOCK_EXPORT, RESTOCK_VIEW
from app.core.timezone import now_beijing
from app.models.excel_export_log import ExcelExportLog
from app.models.global_config import GlobalConfig
from app.models.product_listing import ProductListing
from app.models.suggestion import Suggestion, SuggestionItem
from app.models.suggestion_snapshot import SuggestionSnapshot, SuggestionSnapshotItem
from app.models.sys_user import SysUser
from app.models.warehouse import Warehouse
from app.schemas.suggestion_snapshot import (
    SnapshotCreateRequest,
    SnapshotDetailOut,
    SnapshotItemOut,
    SnapshotOut,
)
from app.services.excel_export import (
    SnapshotExportContext,
    build_excel_workbook,
    build_filename,
)

router = APIRouter(prefix="/api", tags=["snapshot"])


@router.post(
    "/suggestions/{suggestion_id}/snapshots",
    response_model=SnapshotOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_snapshot(
    suggestion_id: int,
    body: SnapshotCreateRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(RESTOCK_EXPORT)),
    db: AsyncSession = Depends(db_session),
) -> SnapshotOut:
    # 1. 建议单校验
    sug = (
        await db.execute(
            select(Suggestion).where(Suggestion.id == suggestion_id).with_for_update()
        )
    ).scalar_one_or_none()
    if sug is None:
        raise HTTPException(status_code=404, detail="建议单不存在")
    if sug.status != "draft":
        raise HTTPException(
            status_code=409, detail=f"建议单状态 {sug.status}，不可导出"
        )

    # 2. items 校验
    items = (
        (
            await db.execute(
                select(SuggestionItem).where(
                    SuggestionItem.id.in_(body.item_ids),
                    SuggestionItem.suggestion_id == suggestion_id,
                )
                .order_by(SuggestionItem.id)
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    if len(items) != len(body.item_ids):
        raise HTTPException(status_code=400, detail="部分 item 不属于该建议单")
    already = [it.id for it in items if it.export_status == "exported"]
    if already:
        raise HTTPException(status_code=409, detail=f"以下 item 已导出：{already}")

    # 3. 计算 version
    max_version = (
        await db.execute(
            select(func.coalesce(func.max(SuggestionSnapshot.version), 0)).where(
                SuggestionSnapshot.suggestion_id == suggestion_id
            )
        )
    ).scalar_one()
    next_version = int(max_version) + 1

    config = (
        await db.execute(select(GlobalConfig).where(GlobalConfig.id == 1).with_for_update())
    ).scalar_one_or_none()

    # 4. 插入 snapshot（generating）
    snapshot = SuggestionSnapshot(
        suggestion_id=suggestion_id,
        version=next_version,
        exported_by=user.id,
        exported_from_ip=request.client.host if request.client else None,
        item_count=len(items),
        note=body.note,
        global_config_snapshot=sug.global_config_snapshot,
        generation_status="generating",
    )
    db.add(snapshot)
    await db.flush()

    # 5. 拉取商品名/主图 + 仓库名
    # ProductListing 实际字段：commodity_sku, commodity_name, main_image
    skus = [it.commodity_sku for it in items]
    product_rows = (
        await db.execute(
            select(
                ProductListing.commodity_sku,
                ProductListing.commodity_name,
                ProductListing.main_image,
            ).where(ProductListing.commodity_sku.in_(skus))
        )
    ).all()
    # 同一 SKU 可能多条（多站点）；取任意一条
    product_info: dict[str, dict[str, Any]] = {}
    for sku, name, image in product_rows:
        if sku not in product_info:
            product_info[sku] = {"name": name, "image": image}

    # Warehouse 实际字段：id（pk）, name
    wh_ids: set[str] = set()
    for it in items:
        for wh_dict in it.warehouse_breakdown.values():
            wh_ids.update(wh_dict.keys())
    wh_name_map: dict[str, str] = {}
    if wh_ids:
        wh_rows = (
            await db.execute(
                select(Warehouse.id, Warehouse.name).where(
                    Warehouse.id.in_(list(wh_ids))
                )
            )
        ).all()
        wh_name_map = {str(r[0]): r[1] for r in wh_rows}

    # 6. 冻结 snapshot_item + 组装 Excel context
    snapshot_items_ctx: list[dict[str, Any]] = []
    for it in items:
        pinfo = product_info.get(it.commodity_sku, {})
        db.add(
            SuggestionSnapshotItem(
                snapshot_id=snapshot.id,
                commodity_sku=it.commodity_sku,
                total_qty=it.total_qty,
                country_breakdown=it.country_breakdown,
                warehouse_breakdown=it.warehouse_breakdown,
                urgent=it.urgent,
                velocity_snapshot=it.velocity_snapshot,
                sale_days_snapshot=it.sale_days_snapshot,
                commodity_name=pinfo.get("name"),
                main_image_url=pinfo.get("image"),
            )
        )
        snapshot_items_ctx.append({
            "commodity_sku": it.commodity_sku,
            "commodity_name": pinfo.get("name"),
            "main_image_url": pinfo.get("image"),
            "total_qty": it.total_qty,
            "urgent": it.urgent,
            "country_breakdown": it.country_breakdown,
            "warehouse_breakdown": it.warehouse_breakdown,
            "velocity_snapshot": it.velocity_snapshot,
            "sale_days_snapshot": it.sale_days_snapshot,
            "warehouse_name_map": wh_name_map,
        })

    # 7. 更新 suggestion_item 导出状态
    now = now_beijing()

    # 8. 生成 Excel 文件
    exported_at_text = now.strftime("%Y-%m-%d %H:%M:%S")
    exported_at_compact = now.strftime("%Y%m%d-%H%M%S")
    user_name = user.display_name or user.username
    ctx = SnapshotExportContext(
        suggestion_id=suggestion_id,
        version=next_version,
        exported_at_text=exported_at_text,
        exported_by_name=user_name,
        note=body.note,
        global_config=sug.global_config_snapshot,
        items=snapshot_items_ctx,
    )
    settings = get_settings()
    storage_root = Path(settings.export_storage_dir).resolve()
    year_month = now.strftime("%Y/%m")
    filename = build_filename(suggestion_id, next_version, exported_at_compact)

    try:
        target_dir = storage_root / year_month
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename
        wb = build_excel_workbook(ctx)
        wb.save(target_path)
        file_size = target_path.stat().st_size
        snapshot.file_path = str(Path(year_month) / filename).replace("\\", "/")
        snapshot.file_size_bytes = file_size
        snapshot.generation_status = "ready"
    except Exception as exc:
        snapshot.generation_status = "failed"
        snapshot.generation_error = str(exc)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Excel 生成失败：{exc}") from exc

    # 9. 文件落盘成功后，再标记 item 已导出
    await db.execute(
        update(SuggestionItem)
        .where(SuggestionItem.id.in_(body.item_ids))
        .values(
            export_status="exported",
            exported_snapshot_id=snapshot.id,
            exported_at=now,
        )
    )

    # 10. 首次导出 → 翻 toggle OFF
    if config and config.suggestion_generation_enabled:
        config.suggestion_generation_enabled = False
        config.generation_toggle_updated_by = user.id
        config.generation_toggle_updated_at = now

    # 11. 写 export_log
    db.add(
        ExcelExportLog(
            snapshot_id=snapshot.id,
            action="generate",
            performed_by=user.id,
            performed_from_ip=request.client.host if request.client else None,
            user_agent=(request.headers.get("user-agent", "") or "")[:500] or None,
        )
    )

    await db.commit()
    await db.refresh(snapshot)
    return SnapshotOut(
        id=snapshot.id,
        suggestion_id=snapshot.suggestion_id,
        version=snapshot.version,
        exported_by=snapshot.exported_by,
        exported_by_name=user_name,
        exported_at=snapshot.exported_at,
        item_count=snapshot.item_count,
        note=snapshot.note,
        generation_status=snapshot.generation_status,
        file_size_bytes=snapshot.file_size_bytes,
        download_count=snapshot.download_count,
    )


@router.get(
    "/suggestions/{suggestion_id}/snapshots",
    response_model=list[SnapshotOut],
)
async def list_snapshots(
    suggestion_id: int,
    _: None = Depends(require_permission(RESTOCK_VIEW)),
    db: AsyncSession = Depends(db_session),
) -> list[SnapshotOut]:
    rows = (
        await db.execute(
            select(
                SuggestionSnapshot,
                SysUser.display_name.label("exported_by_name"),
            )
            .outerjoin(SysUser, SysUser.id == SuggestionSnapshot.exported_by)
            .where(SuggestionSnapshot.suggestion_id == suggestion_id)
            .order_by(SuggestionSnapshot.version.asc())
        )
    ).all()
    return [
        SnapshotOut(
            id=snap.id,
            suggestion_id=snap.suggestion_id,
            version=snap.version,
            exported_by=snap.exported_by,
            exported_by_name=name,
            exported_at=snap.exported_at,
            item_count=snap.item_count,
            note=snap.note,
            generation_status=snap.generation_status,
            file_size_bytes=snap.file_size_bytes,
            download_count=snap.download_count,
        )
        for snap, name in rows
    ]


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotDetailOut)
async def get_snapshot_detail(
    snapshot_id: int,
    _: None = Depends(require_permission(RESTOCK_VIEW)),
    db: AsyncSession = Depends(db_session),
) -> SnapshotDetailOut:
    row = (
        await db.execute(
            select(
                SuggestionSnapshot,
                SysUser.display_name.label("exported_by_name"),
            )
            .outerjoin(SysUser, SysUser.id == SuggestionSnapshot.exported_by)
            .where(SuggestionSnapshot.id == snapshot_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="快照不存在")
    snap, name = row
    items = (
        (
            await db.execute(
                select(SuggestionSnapshotItem).where(
                    SuggestionSnapshotItem.snapshot_id == snapshot_id
                )
            )
        )
        .scalars()
        .all()
    )
    return SnapshotDetailOut(
        id=snap.id,
        suggestion_id=snap.suggestion_id,
        version=snap.version,
        exported_by=snap.exported_by,
        exported_by_name=name,
        exported_at=snap.exported_at,
        item_count=snap.item_count,
        note=snap.note,
        generation_status=snap.generation_status,
        file_size_bytes=snap.file_size_bytes,
        download_count=snap.download_count,
        items=[SnapshotItemOut.model_validate(it) for it in items],
        global_config_snapshot=snap.global_config_snapshot,
    )


@router.get("/snapshots/{snapshot_id}/download")
async def download_snapshot(
    snapshot_id: int,
    request: Request,
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(RESTOCK_EXPORT)),
    db: AsyncSession = Depends(db_session),
) -> FileResponse:
    snap = (
        await db.execute(
            select(SuggestionSnapshot).where(SuggestionSnapshot.id == snapshot_id)
        )
    ).scalar_one_or_none()
    if snap is None:
        raise HTTPException(status_code=404, detail="快照不存在")
    if snap.generation_status != "ready":
        raise HTTPException(status_code=409, detail="文件尚未就绪或生成失败")

    settings = get_settings()
    storage_root = Path(settings.export_storage_dir).resolve()
    file_abs = storage_root / (snap.file_path or "")
    if not snap.file_path or not file_abs.exists():
        raise HTTPException(status_code=410, detail="文件已丢失")

    # 更新下载计数
    await db.execute(
        update(SuggestionSnapshot)
        .where(SuggestionSnapshot.id == snapshot_id)
        .values(
            download_count=SuggestionSnapshot.download_count + 1,
            last_downloaded_at=now_beijing(),
        )
    )
    db.add(
        ExcelExportLog(
            snapshot_id=snapshot_id,
            action="download",
            performed_by=user.id,
            performed_from_ip=request.client.host if request.client else None,
            user_agent=(request.headers.get("user-agent", "") or "")[:500] or None,
        )
    )
    await db.commit()

    filename = Path(snap.file_path).name
    return FileResponse(
        path=file_abs,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
