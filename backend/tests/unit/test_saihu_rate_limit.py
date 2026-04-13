from app.saihu.rate_limit import get_limiter


def test_order_detail_limiter_is_single_qps() -> None:
    limiter = get_limiter("/api/order/detailByOrderId.json")

    assert limiter.max_rate == 2
    assert limiter.time_period == 1.0
