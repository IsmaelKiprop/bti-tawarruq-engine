"""TOTP for privileged ops MFA (RFC 6238, SHA-1, 30s, 6 digits)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

def _issuer() -> str:
    from tawarruq.config import get_settings

    return get_settings().totp_issuer


def generate_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _hotp(secret: str, counter: int) -> str:
    padded = secret.upper() + "=" * ((8 - len(secret.upper()) % 8) % 8)
    key = base64.b32decode(padded, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return f"{code % 1_000_000:06d}"


def totp_now(secret: str, *, for_time: float | None = None) -> str:
    counter = int((for_time if for_time is not None else time.time()) // 30)
    return _hotp(secret, counter)


def verify_totp(secret: str, code: str, *, window: int = 1) -> bool:
    cleaned = (code or "").strip().replace(" ", "")
    if len(cleaned) != 6 or not cleaned.isdigit() or not secret:
        return False
    now = int(time.time() // 30)
    for drift in range(-window, window + 1):
        if hmac.compare_digest(_hotp(secret, now + drift), cleaned):
            return True
    return False


def otpauth_url(secret: str, email: str) -> str:
    name = _issuer()
    label = quote(f"{name}:{email}")
    issuer = quote(name)
    return f"otpauth://totp/{label}?secret={secret}&issuer={issuer}&period=30&digits=6"
