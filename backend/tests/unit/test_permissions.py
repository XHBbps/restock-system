from app.core.permissions import ALL_CODES, REGISTRY, PermDef


def test_registry_not_empty():
    assert len(REGISTRY) >= 16


def test_no_duplicate_codes():
    codes = [p.code for p in REGISTRY]
    assert len(codes) == len(set(codes))


def test_all_codes_match_registry():
    assert ALL_CODES == frozenset(p.code for p in REGISTRY)


def test_permdef_is_frozen():
    p = REGISTRY[0]
    assert isinstance(p, PermDef)
    import pytest

    with pytest.raises(AttributeError):
        p.code = "hack"


def test_forbidden_exception():
    from app.core.exceptions import BusinessError, Forbidden

    exc = Forbidden("no access")
    assert isinstance(exc, BusinessError)
    assert exc.status_code == 403
    assert exc.message == "no access"
