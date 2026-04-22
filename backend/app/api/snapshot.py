"""Snapshot APIs for procurement/restock exports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import UserContext, db_session, get_current_user, require_permission
from app.config import get_settings
from app.core.permissions import RESTOCK_EXPORT, RESTOCK_VIEW
from app.core.timezone import now_beijing
from app.models.excel_export_log import ExcelExportLog
from app.models.product_listing import ProductListing
from app.models.suggestion import Suggestion, SuggestionItem
from app.models.suggestion_snapshot import SuggestionSnapshot, SuggestionSnapshotItem
from app.models.sys_user import SysUser
from app.schemas.suggestion_snapshot import (
    SnapshotCreateRequest,
    SnapshotDetailOut,
    SnapshotItemOut,
    SnapshotOut,
)
from app.services.excel_export import (
    SnapshotExportContext,
    build_filename,
    build_procurement_workbook,
    build_restock_workbook,
)

router = APIRouter(prefix="/api", tags=["snapshot"])


@router.post(
    "/suggestions/{suggestion_id}/snapshots",
    status_code=status.HTTP_410_GONE,
)
async def create_snapshot_gone(suggestion_id: int) -> dict[str, str]:
    return {
        "message": "旧快照创建端点已废弃，请改用 /snapshots/procurement 或 /snapshots/restock",
    }


@router.post(
    "/suggestions/{suggestion_id}/snapshots/procurement",
    response_model=SnapshotOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_procurement_snapshot(
    suggestion_id: int,
    body: SnapshotCreateRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(RESTOCK_EXPORT)),
    db: AsyncSession = Depends(db_session),
) -> SnapshotOut:
    return await _create_snapshot(
        db=db,
        user=user,
        request=request,
        suggestion_id=suggestion_id,
        body=body,
        snapshot_type="procurement",
    )


@router.post(
    "/suggestions/{suggestion_id}/snapshots/restock",
    response_model=SnapshotOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_restock_snapshot(
    suggestion_id: int,
    body: SnapshotCreateRequest,
    request: Request,
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(RESTOCK_EXPORT)),
    db: AsyncSession = Depends(db_session),
) -> SnapshotOut:
    return await _create_snapshot(
        db=db,
        user=user,
        request=request,
        suggestion_id=suggestion_id,
        body=body,
        snapshot_type="restock",
    )


async def _create_snapshot(
    *,
    db: AsyncSession,
    user: UserContext,
    request: Request,
    suggestion_id: int,
    body: SnapshotCreateRequest,
    snapshot_type: str,
) -> SnapshotOut:
    suggestion = (
        await db.execute(select(Suggestion).where(Suggestion.id == suggestion_id).with_for_update())
    ).scalar_one_or_none()
    if suggestion is None:
        raise HTTPException(status_code=404, detail="建议单不存在")
    if suggestion.status != "draft":
        raise HTTPException(status_code=409, detail=f"建议单状态 {suggestion.status}，不可导出")

    items = (
        await db.execute(
            select(SuggestionItem)
            .where(SuggestionItem.id.in_(body.item_ids), SuggestionItem.suggestion_id == suggestion_id)
            .order_by(SuggestionItem.id)
            .with_for_update()
        )
    ).scalars().all()
    if len(items) != len(body.item_ids):
        raise HTTPException(status_code=422, detail="存在不属于当前建议单的条目")

    if snapshot_type == "procurement":
        invalid_items = [item.id for item in items if item.purchase_qty <= 0]
        if invalid_items:
            raise HTTPException(status_code=422, detail=f"采购快照仅允许 purchase_qty > 0 的条目：{invalid_items}")
    else:
        invalid_items = [item.id for item in items if sum((item.country_breakdown or {}).values()) <= 0]
        if invalid_items:
            raise HTTPException(status_code=422, detail=f"补货快照仅允许补货量 > 0 的条目：{invalid_items}")

    next_version = int(
        (
            await db.execute(
                select(func.coalesce(func.max(SuggestionSnapshot.version), 0)).where(
                    SuggestionSnapshot.suggestion_id == suggestion_id,
                    SuggestionSnapshot.snapshot_type == snapshot_type,
                )
            )
        ).scalar_one()
    ) + 1

    snapshot = SuggestionSnapshot(
        suggestion_id=suggestion_id,
        snapshot_type=snapshot_type,
        version=next_version,
        exported_by=user.id,
        exported_from_ip=request.client.host if request.client else None,
        item_count=len(items),
        note=body.note,
        global_config_snapshot=suggestion.global_config_snapshot,
        generation_status="generating",
    )
    db.add(snapshot)
    await db.flush()

    product_rows = (
        await db.execute(
            select(ProductListing.commodity_sku, ProductListing.commodity_name, ProductListing.main_image).where(
                ProductListing.commodity_sku.in_([item.commodity_sku for item in items])
            )
        )
    ).all()
    product_map: dict[str, tuple[str | None, str | None]] = {}
    for sku, name, image in product_rows:
        if sku not in product_map:
            product_map[sku] = (name, image)

    export_items: list[dict[str, Any]] = []
    for item in items:
        commodity_name, main_image_url = product_map.get(item.commodity_sku, (None, None))
        snapshot_item = SuggestionSnapshotItem(
            snapshot_id=snapshot.id,
            commodity_sku=item.commodity_sku,
            total_qty=item.total_qty,
            country_breakdown=item.country_breakdown,
            warehouse_breakdown=item.warehouse_breakdown,
            purchase_qty=item.purchase_qty if snapshot_type == "procurement" else None,
            purchase_date=item.purchase_date if snapshot_type == "procurement" else None,
            urgent=item.urgent,
            velocity_snapshot=item.velocity_snapshot,
            sale_days_snapshot=item.sale_days_snapshot,
            commodity_name=commodity_name,
            main_image_url=main_image_url,
        )
        db.add(snapshot_item)
        export_items.append(
            {
                "commodity_sku": item.commodity_sku,
                "commodity_name": commodity_name,
                "main_image_url": main_image_url,
                "total_qty": item.total_qty,
                "country_breakdown": item.country_breakdown,
                "warehouse_breakdown": item.warehouse_breakdown,
                "purchase_qty": item.purchase_qty,
                "purchase_date": item.purchase_date,
                "urgent": item.urgent,
                "velocity_snapshot": item.velocity_snapshot,
                "sale_days_snapshot": item.sale_days_snapshot,
            }
        )

    now = now_beijing()
    ctx = SnapshotExportContext(
        suggestion_id=suggestion_id,
        snapshot_type=snapshot_type,
        version=next_version,
        exported_at=now,
        exported_by_name=user.display_name or user.username,
        note=body.note,
        global_config=suggestion.global_config_snapshot,
        items=export_items,
    )

    settings = get_settings()
    storage_root = Path(settings.export_storage_dir).resolve()
    target_dir = storage_root / now.strftime("%Y/%m")
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = build_filename(suggestion_id, next_version, now, snapshot_type)
    target_path = target_dir / filename

    try:
        workbook = (
            build_procurement_workbook(ctx)
            if snapshot_type == "procurement"
            else build_restock_workbook(ctx)
        )
        workbook.save(target_path)
        snapshot.file_path = str((Path(now.strftime("%Y/%m")) / filename).as_posix())
        snapshot.file_size_bytes = target_path.stat().st_size
        snapshot.generation_status = "ready"
    except Exception as exc:
        snapshot.generation_status = "failed"
        snapshot.generation_error = str(exc)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Excel 生成失败：{exc}") from exc

    update_values = (
        {
            "procurement_export_status": "exported",
            "procurement_exported_snapshot_id": snapshot.id,
            "procurement_exported_at": now,
        }
        if snapshot_type == "procurement"
        else {
            "restock_export_status": "exported",
            "restock_exported_snapshot_id": snapshot.id,
            "restock_exported_at": now,
        }
    )
    await db.execute(update(SuggestionItem).where(SuggestionItem.id.in_(body.item_ids)).values(**update_values))

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
        snapshot_type=snapshot.snapshot_type,
        version=snapshot.version,
        exported_by=snapshot.exported_by,
        exported_by_name=user.display_name or user.username,
        exported_at=snapshot.exported_at,
        item_count=snapshot.item_count,
        note=snapshot.note,
        generation_status=snapshot.generation_status,
        file_size_bytes=snapshot.file_size_bytes,
        download_count=snapshot.download_count,
    )


@router.get("/suggestions/{suggestion_id}/snapshots", response_model=list[SnapshotOut])
async def list_snapshots(
    suggestion_id: int,
    type: str | None = Query(default=None, pattern="^(procurement|restock)$"),
    _: None = Depends(require_permission(RESTOCK_VIEW)),
    db: AsyncSession = Depends(db_session),
) -> list[SnapshotOut]:
    stmt = (
        select(SuggestionSnapshot, SysUser.display_name.label("exported_by_name"))
        .outerjoin(SysUser, SysUser.id == SuggestionSnapshot.exported_by)
        .where(SuggestionSnapshot.suggestion_id == suggestion_id)
    )
    if type:
        stmt = stmt.where(SuggestionSnapshot.snapshot_type == type)
    rows = (await db.execute(stmt.order_by(SuggestionSnapshot.version.desc()))).all()
    return [
        SnapshotOut(
            id=snapshot.id,
            suggestion_id=snapshot.suggestion_id,
            snapshot_type=snapshot.snapshot_type,
            version=snapshot.version,
            exported_by=snapshot.exported_by,
            exported_by_name=exported_by_name,
            exported_at=snapshot.exported_at,
            item_count=snapshot.item_count,
            note=snapshot.note,
            generation_status=snapshot.generation_status,
            file_size_bytes=snapshot.file_size_bytes,
            download_count=snapshot.download_count,
        )
        for snapshot, exported_by_name in rows
    ]


@router.get("/snapshots/{snapshot_id}", response_model=SnapshotDetailOut)
async def get_snapshot_detail(
    snapshot_id: int,
    _: None = Depends(require_permission(RESTOCK_VIEW)),
    db: AsyncSession = Depends(db_session),
) -> SnapshotDetailOut:
    row = (
        await db.execute(
            select(SuggestionSnapshot, SysUser.display_name.label("exported_by_name"))
            .outerjoin(SysUser, SysUser.id == SuggestionSnapshot.exported_by)
            .where(SuggestionSnapshot.id == snapshot_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="快照不存在")
    snapshot, exported_by_name = row
    items = (
        await db.execute(select(SuggestionSnapshotItem).where(SuggestionSnapshotItem.snapshot_id == snapshot_id))
    ).scalars().all()
    return SnapshotDetailOut(
        id=snapshot.id,
        suggestion_id=snapshot.suggestion_id,
        snapshot_type=snapshot.snapshot_type,
        version=snapshot.version,
        exported_by=snapshot.exported_by,
        exported_by_name=exported_by_name,
        exported_at=snapshot.exported_at,
        item_count=snapshot.item_count,
        note=snapshot.note,
        generation_status=snapshot.generation_status,
        file_size_bytes=snapshot.file_size_bytes,
        download_count=snapshot.download_count,
        items=[SnapshotItemOut.model_validate(item) for item in items],
        global_config_snapshot=snapshot.global_config_snapshot,
    )


@router.get("/snapshots/{snapshot_id}/download")
async def download_snapshot(
    snapshot_id: int,
    request: Request,
    user: UserContext = Depends(get_current_user),
    _: None = Depends(require_permission(RESTOCK_EXPORT)),
    db: AsyncSession = Depends(db_session),
) -> FileResponse:
    snapshot = (
        await db.execute(select(SuggestionSnapshot).where(SuggestionSnapshot.id == snapshot_id))
    ).scalar_one_or_none()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="快照不存在")
    if snapshot.generation_status != "ready":
        raise HTTPException(status_code=409, detail="文件尚未就绪或生成失败")

    settings = get_settings()
    storage_root = Path(settings.export_storage_dir).resolve()
    file_abs = storage_root / (snapshot.file_path or "")
    if not snapshot.file_path or not file_abs.exists():
        # 若 retention 已标记 file_purged_at，返回更明确的 410 原因供前端展示
        purged_at = (
            await db.execute(
                select(ExcelExportLog.file_purged_at)
                .where(ExcelExportLog.snapshot_id == snapshot_id)
                .where(ExcelExportLog.action == "generate")
                .where(ExcelExportLog.file_purged_at.is_not(None))
                .order_by(ExcelExportLog.file_purged_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if purged_at is not None:
            raise HTTPException(
                status_code=410,
                detail=f"该版本已过期清理（保留期 {settings.retention_exports_days} 天）",
            )
        raise HTTPException(status_code=410, detail="文件已丢失")

    await db.execute(
        update(SuggestionSnapshot)
        .where(SuggestionSnapshot.id == snapshot_id)
        .values(download_count=SuggestionSnapshot.download_count + 1, last_downloaded_at=now_beijing())
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

    return FileResponse(
        path=file_abs,
        filename=Path(snapshot.file_path).name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
