"""Map internal commodity codes to Bursa BSAS product codes (e.g. ACPO)."""

from __future__ import annotations

# Internal engine code → BSAS product code used on the dealing desk
COMMODITY_TO_BSAS_PRODUCT: dict[str, str] = {
    "PALM_OIL": "ACPO",
    "ACPO": "ACPO",
    "CRUDE_PALM_OIL": "ACPO",
    "AIRTIME_SAFARICOM": "AIRTIME_SAFARICOM",
    "AIRTIME_AIRTEL": "AIRTIME_AIRTEL",
}

PURCHASE_TYPE_AGENT = "A"
PURCHASE_TYPE_LABEL = "Agent (A)"

DEFAULT_CURRENCY = "KES"


def bsas_product_code(commodity_code: str) -> str:
    code = (commodity_code or "").strip().upper()
    if not code:
        return "ACPO"
    return COMMODITY_TO_BSAS_PRODUCT.get(code, code)
