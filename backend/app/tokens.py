"""Signed, expiring download tokens.

A token carries everything needed to produce a file (media URLs, the
conversion to run and a filename), so the server stores nothing between the
extract call and the download.
"""
import base64
import hashlib
import hmac
import json
import time

from . import config


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def sign(payload: dict, ttl: int | None = None, now: float | None = None) -> str:
    body = dict(payload)
    body["exp"] = int((now or time.time()) + (ttl or config.TOKEN_TTL))
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    sig = hmac.new(config.SECRET_KEY.encode(), raw, hashlib.sha256).digest()
    return f"{_b64(raw)}.{_b64(sig)}"


def verify(token: str, now: float | None = None) -> dict | None:
    try:
        raw_b64, sig_b64 = token.split(".", 1)
        raw = _unb64(raw_b64)
        sig = _unb64(sig_b64)
    except (ValueError, TypeError):
        return None
    expected = hmac.new(config.SECRET_KEY.encode(), raw, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        body = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(body, dict) or body.get("exp", 0) < (now or time.time()):
        return None
    return body
