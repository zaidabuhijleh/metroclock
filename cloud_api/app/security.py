from __future__ import annotations

import hashlib
import secrets


def generate_device_token() -> str:
    return f"mclk_{secrets.token_urlsafe(48)}"


def hash_device_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
