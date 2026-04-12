from app.api.config import init_sku_configs_from_listings
from app.models.product_listing import ProductListing
from app.models.sku import SkuConfig


class _ScalarResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


class _FakeDb:
    def __init__(self, listing_skus, existing_skus) -> None:
        self.listing_skus = listing_skus
        self.existing_skus = existing_skus
        self.inserted = []
        self.commits = 0

    async def execute(self, stmt):
        if hasattr(stmt, "column_descriptions") and stmt.column_descriptions:
            entity = stmt.column_descriptions[0].get("entity")
            if entity is ProductListing:
                return _ScalarResult(self.listing_skus)
            if entity is SkuConfig:
                return _ScalarResult(self.existing_skus)

        if getattr(stmt, "table", None) is not None and stmt.table.name == "sku_config":
            params = stmt.compile().params
            indexes = sorted(
                int(key.removeprefix("commodity_sku_m"))
                for key in params
                if key.startswith("commodity_sku_m")
            )
            self.inserted = [params[f"commodity_sku_m{index}"] for index in indexes]
        return _ScalarResult([])

    async def commit(self) -> None:
        self.commits += 1


async def test_init_sku_configs_from_listings_only_inserts_missing() -> None:
    db = _FakeDb(
        listing_skus=["SKU-001", "SKU-002", "SKU-003"],
        existing_skus=["SKU-002"],
    )

    created = await init_sku_configs_from_listings(db)  # type: ignore[arg-type]

    assert created == 2
    assert db.inserted == ["SKU-001", "SKU-003"]
    assert db.commits == 1


async def test_init_sku_configs_from_listings_returns_zero_when_no_source_data() -> None:
    db = _FakeDb(listing_skus=[], existing_skus=[])

    created = await init_sku_configs_from_listings(db)  # type: ignore[arg-type]

    assert created == 0
    assert db.inserted == []
    assert db.commits == 0
