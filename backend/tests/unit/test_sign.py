"""赛狐签名算法单元测试。

固定 fixture 来自 docs/saihu_api/开发指南/生产sign.md：
    access_token = d20d9d20-5db0-429a-8390-3694265e297c
    client_id = 1111111
    method = post
    nonce = 888
    timestamp = 1668153260508
    url = /openapi/api/commodity/pageList.json
    client_secret = fde212ff-588a-11ef-b1d4-0c42a1eda3d9
预期签名：
    57bcbd213461d47e99e9b781c11f3fb37937127824272a30b95ddb5cbfea881e
"""

from app.saihu.sign import generate_sign


def test_generate_sign_matches_official_fixture() -> None:
    sign = generate_sign(
        access_token="d20d9d20-5db0-429a-8390-3694265e297c",
        client_id="1111111",
        method="post",
        nonce=888,
        timestamp=1668153260508,
        url="/openapi/api/commodity/pageList.json",
        client_secret="fde212ff-588a-11ef-b1d4-0c42a1eda3d9",
    )
    assert sign == "57bcbd213461d47e99e9b781c11f3fb37937127824272a30b95ddb5cbfea881e"


def test_generate_sign_is_deterministic() -> None:
    """同样输入应得同样输出（hex）。"""
    args = dict(
        access_token="aaa",
        client_id="bbb",
        method="post",
        nonce="111",
        timestamp="222",
        url="/x",
        client_secret="secret",
    )
    s1 = generate_sign(**args)  # type: ignore[arg-type]
    s2 = generate_sign(**args)  # type: ignore[arg-type]
    assert s1 == s2
    assert len(s1) == 64  # SHA256 hex


def test_generate_sign_different_nonce_different_output() -> None:
    base = dict(
        access_token="aaa",
        client_id="bbb",
        method="post",
        timestamp="222",
        url="/x",
        client_secret="secret",
    )
    s1 = generate_sign(nonce="111", **base)  # type: ignore[arg-type]
    s2 = generate_sign(nonce="999", **base)  # type: ignore[arg-type]
    assert s1 != s2
