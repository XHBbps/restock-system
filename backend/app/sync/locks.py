"""Business-level advisory locks for Saihu sync jobs."""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text

from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.tasks.jobs import JobContext

logger = get_logger(__name__)

SYNC_BUSINESS_LOCK_JOBS: tuple[str, ...] = (
    "sync_shop",
    "sync_warehouse",
    "sync_product_listing",
    "sync_inventory",
    "sync_out_records",
    "sync_order_list",
)
_HELD_LOCKS_PAYLOAD_KEY = "_held_sync_business_locks"


class SyncBusinessLockConflictError(RuntimeError):
    """Raised when a sync business lock is already held by another task."""


def sync_business_lock_key(job_name: str) -> int:
    digest = hashlib.sha256(f"restock_system:sync:{job_name}".encode()).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)


@asynccontextmanager
async def sync_business_lock(ctx: JobContext, job_name: str) -> AsyncIterator[None]:
    held = set(ctx.payload.get(_HELD_LOCKS_PAYLOAD_KEY) or [])
    if job_name in held:
        yield
        return

    async with sync_business_locks([job_name]) as acquired:
        ctx.payload[_HELD_LOCKS_PAYLOAD_KEY] = sorted(held | set(acquired))
        try:
            yield
        finally:
            if not held:
                ctx.payload.pop(_HELD_LOCKS_PAYLOAD_KEY, None)
            else:
                ctx.payload[_HELD_LOCKS_PAYLOAD_KEY] = sorted(held)


@asynccontextmanager
async def sync_business_locks(job_names: list[str] | tuple[str, ...]) -> AsyncIterator[tuple[str, ...]]:
    unique_names = tuple(sorted(set(job_names), key=sync_business_lock_key))
    if not unique_names:
        yield ()
        return

    async with async_session_factory() as db:
        acquired: list[str] = []
        try:
            for job_name in unique_names:
                lock_key = sync_business_lock_key(job_name)
                ok = (
                    await db.execute(
                        text("SELECT pg_try_advisory_lock(:lock_key)"),
                        {"lock_key": lock_key},
                    )
                ).scalar_one()
                if not ok:
                    logger.warning(
                        "sync_business_lock_conflict",
                        job_name=job_name,
                        lock_key=lock_key,
                        requested=list(unique_names),
                    )
                    raise SyncBusinessLockConflictError(
                        f"sync business lock is already held: {job_name}"
                    )
                acquired.append(job_name)
            yield tuple(acquired)
        finally:
            for job_name in reversed(acquired):
                lock_key = sync_business_lock_key(job_name)
                await db.execute(
                    text("SELECT pg_advisory_unlock(:lock_key)"),
                    {"lock_key": lock_key},
                )
