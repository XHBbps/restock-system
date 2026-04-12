from app.core.query import escape_like


def test_escape_percent():
    assert escape_like("100%") == r"100\%"


def test_escape_underscore():
    assert escape_like("a_b") == r"a\_b"


def test_escape_backslash():
    assert escape_like(r"a\b") == r"a\\b"


def test_no_special_chars():
    assert escape_like("hello") == "hello"


def test_all_special_chars():
    assert escape_like("%_\\") == "\\%\\_\\\\"
