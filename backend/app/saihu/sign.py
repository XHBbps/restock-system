"""赛狐 API 签名算法(HmacSHA256)。

来源:docs/saihu_api/开发指南/生产sign.md

签名字段(按键名排序):
    access_token, client_id, method, nonce, timestamp, url
拼接为 `key=value&key=value...` 后用 client_secret 做 HmacSHA256,
结果以 hex 形式作为 sign 参数。
"""

import hashlib
import hmac
import secrets
import time

# 参与签名的固定字段顺序(已排序)
_SIGN_KEYS = ("access_token", "client_id", "method", "nonce", "timestamp", "url")


def generate_sign(
    *,
    access_token: str,
    client_id: str,
    method: str,
    nonce: str | int,
    timestamp: str | int,
    url: str,
    client_secret: str,
) -> str:
    """生成签名 hex 字符串。"""
    params: dict[str, str] = {
        "access_token": access_token,
        "client_id": client_id,
        "method": method,
        "nonce": str(nonce),
        "timestamp": str(timestamp),
        "url": url,
    }
    payload = "&".join(f"{key}={params[key]}" for key in _SIGN_KEYS)
    digest = hmac.new(
        client_secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest


def make_nonce() -> str:
    """每次请求生成的随机 nonce。"""
    return secrets.token_hex(8)


def make_timestamp_ms() -> str:
    """13 位毫秒时间戳字符串。"""
    return str(int(time.time() * 1000))
