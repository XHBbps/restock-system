from app.core.permission_cache import InMemoryPermissionCache


def test_cache_miss_returns_none():
    cache = InMemoryPermissionCache()
    assert cache.get(1, 0) is None

def test_cache_hit_returns_perms():
    cache = InMemoryPermissionCache()
    perms = frozenset({"home:view", "restock:view"})
    cache.set(1, 0, perms)
    assert cache.get(1, 0) == perms

def test_version_mismatch_returns_none():
    cache = InMemoryPermissionCache()
    cache.set(1, 0, frozenset({"home:view"}))
    assert cache.get(1, 1) is None

def test_invalidate_removes_entry():
    cache = InMemoryPermissionCache()
    cache.set(1, 0, frozenset({"home:view"}))
    cache.invalidate(1)
    assert cache.get(1, 0) is None

def test_lru_eviction():
    cache = InMemoryPermissionCache(maxsize=2)
    cache.set(1, 0, frozenset())
    cache.set(2, 0, frozenset())
    cache.set(3, 0, frozenset())  # evicts user 1
    assert cache.get(1, 0) is None
    assert cache.get(2, 0) is not None
    assert cache.get(3, 0) is not None
