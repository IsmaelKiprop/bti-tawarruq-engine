"""Deploy edition and optional product modules.

``managed`` is the BTI-hosted multi-tenant SaaS (default).
``onprem`` is a customer-server install of the same images.
"""

from __future__ import annotations

KNOWN_PRODUCTS = ("kenya", "malaysia", "sedania", "sacco", "billing", "mobile")
DEFAULT_PRODUCTS = ",".join(KNOWN_PRODUCTS)


def normalize_mode(raw: str | None) -> str:
    mode = (raw or "managed").strip().lower().replace("-", "_")
    return "onprem" if mode in {"onprem", "on_prem"} else "managed"


def parse_products(raw: str | None) -> list[str]:
    if raw is None or not str(raw).strip():
        return list(KNOWN_PRODUCTS)
    found: list[str] = []
    for part in str(raw).split(","):
        name = part.strip().lower()
        if name in KNOWN_PRODUCTS and name not in found:
            found.append(name)
    return found or list(KNOWN_PRODUCTS)


def parse_cors_origins(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]
