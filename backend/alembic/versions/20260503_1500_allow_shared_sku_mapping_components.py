"""allow shared inventory SKU mapping components.

Revision ID: 20260503_1500
Revises: 20260503_1000
Create Date: 2026-05-03 15:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260503_1500"
down_revision: str | None = "20260503_1000"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_sku_mapping_component_inventory_sku",
        "sku_mapping_component",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_sku_mapping_component_rule_inventory",
        "sku_mapping_component",
        ["rule_id", "inventory_sku"],
    )


def downgrade() -> None:
    raise NotImplementedError("downgrade not supported per AGENTS.md section 11")
