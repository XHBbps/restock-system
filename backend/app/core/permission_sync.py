"""启动时权限注册表同步到 DB。"""

import sqlalchemy.exc
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.permissions import REGISTRY
from app.models.permission import Permission

logger = get_logger(__name__)


async def sync_permissions(db: AsyncSession) -> None:
    """将 REGISTRY 同步到 permission 表，幂等可重入。"""
    try:
        existing = {
            row.code: row
            for row in (await db.execute(select(Permission))).scalars().all()
        }
    except (sqlalchemy.exc.ProgrammingError, sqlalchemy.exc.OperationalError):
        logger.warning("permission_sync_skipped", reason="permission table does not exist yet")
        await db.rollback()
        return

    registry_codes = set()
    for idx, perm_def in enumerate(REGISTRY):
        registry_codes.add(perm_def.code)
        stmt = pg_insert(Permission).values(
            code=perm_def.code,
            name=perm_def.name,
            group_name=perm_def.group_name,
            sort_order=idx,
            active=True,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Permission.code],
            set_={
                "name": perm_def.name,
                "group_name": perm_def.group_name,
                "sort_order": idx,
                "active": True,
            },
        )
        await db.execute(stmt)

    # Mark removed permissions as inactive
    for code, row in existing.items():
        if code not in registry_codes and row.active:
            await db.execute(
                update(Permission)
                .where(Permission.code == code)
                .values(active=False)
            )
            logger.info("permission_deactivated", code=code)

    await db.commit()
    logger.info("permission_sync_complete", total=len(REGISTRY))
