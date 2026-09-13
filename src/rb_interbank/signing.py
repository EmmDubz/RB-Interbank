from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any


def sign(secret: str, body: bytes, timestamp: str | None = None) -> str:
    ts = timestamp or str(int(time.time()))
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256)
    return f"t={ts},v1={mac.hexdigest()}"


def verify(secret: str, body: bytes, header: str, max_age_seconds: int = 300) -> bool:
    parts = dict(piece.split("=", 1) for piece in header.split(",") if "=" in piece)
    ts = parts.get("t")
    digest = parts.get("v1")
    if not ts or not digest:
        return False
    try:
        age = abs(time.time() - int(ts))
    except ValueError:
        return False
    if age > max_age_seconds:
        return False
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256)
    return hmac.compare_digest(expected.hexdigest(), digest)


def dumps(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
