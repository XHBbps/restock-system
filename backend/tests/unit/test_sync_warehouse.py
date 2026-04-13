from app.sync.warehouse import _normalize_replenish_site


def test_normalize_replenish_site_truncates_long_values() -> None:
    raw = "ATVPDKIKX0DER,A2EUQ1WTGCTBG2,A1AM78C64UM0Y8,A1F83G8C2ARO7P"
    value = _normalize_replenish_site(raw)

    assert value is not None
    assert len(value) == 50
    assert value.endswith("…")


def test_normalize_replenish_site_keeps_short_values() -> None:
    assert _normalize_replenish_site("ATVPDKIKX0DER") == "ATVPDKIKX0DER"
    assert _normalize_replenish_site("") is None
