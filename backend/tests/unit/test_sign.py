"""赛狐签名算法单元测试。

固定 fixture 使用非敏感示例值，避免在仓库中保留真实形态凭据:
    access_token = example-access-token
    client_id = 1111111
    method = post
    nonce = 888
    timestamp = 1668153260508
    url = /openapi/api/commodity/pageList.json
    client_secret = example-client-secret
预期签名:
    3e655bb2eb0ab93cbc5fd387cd1771fa3b79cb57fb3ccdd8f18c3d2a218710de
"""

from app.saihu.sign import generate_sign, make_nonce


def test_generate_sign_matches_official_fixture() -> None:
    sign = generate_sign(
        access_token="example-access-token",
        client_id="1111111",
        method="post",
        nonce=888,
        timestamp=1668153260508,
        url="/openapi/api/commodity/pageList.json",
        client_secret="example-client-secret",
    )
    assert sign == "3e655bb2eb0ab93cbc5fd387cd1771fa3b79cb57fb3ccdd8f18c3d2a218710de"


def test_generate_sign_is_deterministic() -> None:
    """同样输入应得同样输出(hex)。"""
    args = {
        "access_token": "aaa",
        "client_id": "bbb",
        "method": "post",
        "nonce": "111",
        "timestamp": "222",
        "url": "/x",
        "client_secret": "secret",
    }
    s1 = generate_sign(**args)  # type: ignore[arg-type]
    s2 = generate_sign(**args)  # type: ignore[arg-type]
    assert s1 == s2
    assert len(s1) == 64  # SHA256 hex


def test_generate_sign_different_nonce_different_output() -> None:
    base = {
        "access_token": "aaa",
        "client_id": "bbb",
        "method": "post",
        "timestamp": "222",
        "url": "/x",
        "client_secret": "secret",
    }
    s1 = generate_sign(nonce="111", **base)  # type: ignore[arg-type]
    s2 = generate_sign(nonce="999", **base)  # type: ignore[arg-type]
    assert s1 != s2


def test_make_nonce_is_numeric_and_fixed_width() -> None:
    nonce = make_nonce()
    assert len(nonce) == 16
    assert nonce.isdigit()


def test_make_nonce_changes_between_calls() -> None:
    assert make_nonce() != make_nonce()
