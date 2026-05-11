from datetime import UTC, datetime

from app.schemas.data import DataProductListing


def test_data_product_listing_allows_unmatched_null_sku_and_id() -> None:
    listing = DataProductListing(
        id=1,
        commodity_sku=None,
        commodity_id=None,
        commodity_name=None,
        main_image=None,
        shop_id="SHOP-1",
        marketplace_id="US",
        seller_sku="SELLER-1",
        parent_sku=None,
        day7_sale_num=None,
        day14_sale_num=None,
        day30_sale_num=None,
        is_matched=False,
        online_status="active",
        last_sync_at=datetime(2026, 5, 11, tzinfo=UTC),
    )

    payload = listing.model_dump(by_alias=True)

    assert payload["commoditySku"] is None
    assert payload["commodityId"] is None
