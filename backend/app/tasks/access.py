"""Task access registry shared by task APIs and queue entry points."""

from app.core.exceptions import Forbidden
from app.core.permissions import HOME_REFRESH, RESTOCK_OPERATE, SYNC_OPERATE, SYNC_VIEW

TASK_VIEW_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "sync_product_listing": (SYNC_VIEW, SYNC_OPERATE),
    "sync_warehouse": (SYNC_VIEW, SYNC_OPERATE),
    "sync_inventory": (SYNC_VIEW, SYNC_OPERATE),
    "sync_out_records": (SYNC_VIEW, SYNC_OPERATE),
    "sync_order_list": (SYNC_VIEW, SYNC_OPERATE),
    "sync_order_detail": (SYNC_VIEW, SYNC_OPERATE),
    "refetch_order_detail": (SYNC_VIEW, SYNC_OPERATE),
    "sync_shop": (SYNC_VIEW, SYNC_OPERATE),
    "sync_all": (SYNC_VIEW, SYNC_OPERATE),
    "daily_archive": (SYNC_VIEW, SYNC_OPERATE),
    "calc_engine": (RESTOCK_OPERATE,),
    "refresh_dashboard_snapshot": (HOME_REFRESH,),
}

TASK_MANAGE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "sync_product_listing": (SYNC_OPERATE,),
    "sync_warehouse": (SYNC_OPERATE,),
    "sync_inventory": (SYNC_OPERATE,),
    "sync_out_records": (SYNC_OPERATE,),
    "sync_order_list": (SYNC_OPERATE,),
    "sync_order_detail": (SYNC_OPERATE,),
    "refetch_order_detail": (SYNC_OPERATE,),
    "sync_shop": (SYNC_OPERATE,),
    "sync_all": (SYNC_OPERATE,),
    "daily_archive": (SYNC_OPERATE,),
    "calc_engine": (RESTOCK_OPERATE,),
    "refresh_dashboard_snapshot": (HOME_REFRESH,),
}

ALL_TASK_JOB_NAMES = frozenset(TASK_VIEW_PERMISSIONS)
MANUAL_ENQUEUE_JOB_NAMES = ALL_TASK_JOB_NAMES


def has_any_task_permission(permissions: frozenset[str], required: tuple[str, ...]) -> bool:
    return any(code in permissions for code in required)


def visible_task_job_names(permissions: frozenset[str]) -> set[str]:
    return {
        job_name
        for job_name, required in TASK_VIEW_PERMISSIONS.items()
        if has_any_task_permission(permissions, required)
    }


def ensure_task_access(
    job_name: str,
    permissions: frozenset[str],
    mapping: dict[str, tuple[str, ...]],
) -> None:
    required = mapping.get(job_name)
    if required is None or not has_any_task_permission(permissions, required):
        raise Forbidden("Permission denied")
