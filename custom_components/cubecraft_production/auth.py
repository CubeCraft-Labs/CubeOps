"""HMAC request signing and replay protection helpers."""

from __future__ import annotations

import hashlib
import hmac
import time
from base64 import b64encode


def signature(secret: str, timestamp: str, nonce: str, body: bytes) -> str:
    payload = b".".join((timestamp.encode(), nonce.encode(), body))
    return b64encode(hmac.new(secret.encode(), payload, hashlib.sha256).digest()).decode()


def validate_signature(secret: str, timestamp: str, nonce: str, body: bytes, received: str, *, max_age: int = 300) -> bool:
    try:
        age = abs(time.time() - int(timestamp))
    except (TypeError, ValueError):
        return False
    if age > max_age or not nonce or not received:
        return False
    return hmac.compare_digest(signature(secret, timestamp, nonce, body), received)
