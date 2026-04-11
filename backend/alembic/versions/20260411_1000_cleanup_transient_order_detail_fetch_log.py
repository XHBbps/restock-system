"""Cleanup transient failures from order_detail_fetch_log.

Revision ID: 20260411_1000
Revises: 20260410_1300
Create Date: 2026-04-11

Background
----------
Before 2026-04-11 ``sync_order_detail`` treated every ``SaihuAPIError``
subclass as a permanent failure and wrote it to ``order_detail_fetch_log``,
which prevented future retries for the same order. In reality only
``SaihuBizError`` is permanent — ``SaihuRateLimited`` / ``SaihuAuthExpired``
/ ``SaihuNetworkError`` only surface after the client-level tenacity retry
budget is exhausted and a subsequent run could succeed.

This data-only migration deletes the mis-classified rows so the next
``sync_order_detail`` run can retry them.

Deletion predicate
------------------
- ``http_status IS NULL``: distinguishes failure rows from success rows,
  which are written with ``http_status = 200``.
- ``saihu_code IS NULL OR saihu_code IN (40001, 40019)``:
    - ``40019`` → SaihuRateLimited
    - ``40001`` → SaihuAuthExpired
    - ``NULL``  → SaihuNetworkError / bare SaihuAPIError (no business code)

Rows with any other non-zero ``saihu_code`` represent real business errors
(invalid order id, closed shop, etc.) and are preserved.

Downgrade cannot restore deleted rows; it is a no-op. Re-running
``sync_order_detail`` will re-populate ``order_detail_fetch_log`` with any
orders that still legitimately fail.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260411_1000"
down_revision: str | Sequence[str] | None = "20260410_1300"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM order_detail_fetch_log
         WHERE http_status IS NULL
           AND (saihu_code IS NULL OR saihu_code IN (40001, 40019))
        """
    )


def downgrade() -> None:
    # Data-only migration; deleted rows cannot be restored.
    pass
