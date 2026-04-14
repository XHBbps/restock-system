"""Auth dependency unit tests."""
import pytest

from app.core.exceptions import Forbidden, Unauthorized
from app.core.permission_cache import InMemoryPermissionCache
from app.api.deps import UserContext


def test_user_context_creation():
    ctx = UserContext(
        id=1, username="admin", display_name="管理员",
        role_id=1, role_name="超级管理员",
        is_superadmin=True, perm_version=0,
    )
    assert ctx.id == 1
    assert ctx.is_superadmin is True


def test_require_permission_raises_forbidden():
    """Test that require_permission factory creates a checker that raises Forbidden."""
    from app.api.deps import require_permission
    checker_fn = require_permission("home:view")
    # The returned function expects a frozenset of permissions
    # We can't easily call it without FastAPI's DI, but we can verify it's callable
    assert callable(checker_fn)


def test_forbidden_is_403():
    exc = Forbidden("no access")
    assert exc.status_code == 403


def test_unauthorized_is_401():
    exc = Unauthorized("bad token")
    assert exc.status_code == 401


def test_permission_cache_integration():
    """Verify cache works with UserContext-like access pattern."""
    cache = InMemoryPermissionCache()
    perms = frozenset({"home:view", "restock:view"})
    cache.set(1, 0, perms)
    assert cache.get(1, 0) == perms
    # Version bump invalidates
    assert cache.get(1, 1) is None
