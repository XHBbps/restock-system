"""SQL query utilities."""


def escape_like(value: str) -> str:
    """Escape SQL LIKE/ILIKE wildcards for safe use in patterns."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
