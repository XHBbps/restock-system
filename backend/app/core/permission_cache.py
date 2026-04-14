"""进程内 LRU 权限缓存，版本号驱动失效。"""

from collections import OrderedDict


class InMemoryPermissionCache:
    def __init__(self, maxsize: int = 100) -> None:
        self._maxsize = maxsize
        self._store: OrderedDict[int, tuple[int, frozenset[str]]] = OrderedDict()

    def get(self, user_id: int, version: int) -> frozenset[str] | None:
        entry = self._store.get(user_id)
        if entry is None:
            return None
        cached_version, perms = entry
        if cached_version != version:
            return None
        self._store.move_to_end(user_id)
        return perms

    def set(self, user_id: int, version: int, perms: frozenset[str]) -> None:
        self._store[user_id] = (version, perms)
        self._store.move_to_end(user_id)
        while len(self._store) > self._maxsize:
            self._store.popitem(last=False)

    def invalidate(self, user_id: int) -> None:
        self._store.pop(user_id, None)

    def clear(self) -> None:
        self._store.clear()


# Singleton instance used by auth dependencies
perm_cache = InMemoryPermissionCache()
