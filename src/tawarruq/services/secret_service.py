from dataclasses import dataclass, field
import hashlib
import os

from tawarruq.config import get_settings

_PREFIX = "enc:v1:"


def _fernet():
    try:
        from cryptography.fernet import Fernet
    except ImportError as exc:
        raise RuntimeError("Install cryptography package for secret encryption") from exc

    key = get_settings().integration_encryption_key
    if not key:
        return None
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if value.startswith(_PREFIX):
        return value
    fernet = _fernet()
    if fernet is None:
        return value
    token = fernet.encrypt(value.encode()).decode()
    return f"{_PREFIX}{token}"


def decrypt_secret(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    if not value.startswith(_PREFIX):
        return value
    fernet = _fernet()
    if fernet is None:
        raise RuntimeError("INTEGRATION_ENCRYPTION_KEY required to decrypt institution secrets")
    token = value[len(_PREFIX) :]
    return fernet.decrypt(token.encode()).decode()


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    digest = hashlib.sha256(value.encode()).hexdigest()[:8]
    return f"****{digest}"
