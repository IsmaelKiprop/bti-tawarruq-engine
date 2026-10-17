"""Electronic Wa'd and Wakalah stamps.

Legal wording is owned by the Buruuj Legal / Shariah board. This module only
fills approved templates and signs them. It does not draft new contract text.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from tawarruq.config import get_settings

WAD_TEMPLATE = (
    "Wa'd (promise to purchase). The customer {customer_name} ({customer_id}) undertakes to "
    "purchase from {institution_name} the airtime credit units allocated under this facility, "
    "at the deferred Murabahah price of {deferred_price} {currency} over {tenor_months} months. "
    "This stamp is issued under the board-approved Tawarruq template."
)

WAKALAH_TEMPLATE = (
    "Wakalah (liquidation agency mandate). The customer {customer_name} ({customer_id}) appoints "
    "{institution_name} and Buruuj Fintech as wakeel to liquidate the allocated airtime commodity "
    "to an independent purchaser through Sedania As-Sidq, without Buruuj handling principal cash. "
    "This stamp is issued under the board-approved Tawarruq template."
)


@dataclass
class LegalToken:
    token_id: str
    kind: str
    text: str
    payload: dict[str, Any]
    signature: str
    signed_at: datetime


def _signing_key() -> bytes:
    settings = get_settings()
    raw = settings.legal_token_signing_key or settings.ops_session_secret or "bti-legal-token-dev"
    return raw.encode()


def _sign(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hmac.new(_signing_key(), canonical.encode(), hashlib.sha256).hexdigest()


def stamp_wad(
    *,
    execution_id: str,
    customer_id: str,
    customer_name: str,
    institution_name: str,
    deferred_price: Decimal,
    currency: str,
    tenor_months: int,
) -> LegalToken:
    signed_at = datetime.now(UTC)
    token_id = f"WAD-{execution_id[:8].upper()}"
    text = WAD_TEMPLATE.format(
        customer_name=customer_name,
        customer_id=customer_id,
        institution_name=institution_name,
        deferred_price=f"{deferred_price:.2f}",
        currency=currency,
        tenor_months=tenor_months,
    )
    payload = {
        "token_id": token_id,
        "kind": "wad",
        "execution_id": execution_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "institution_name": institution_name,
        "deferred_price": str(deferred_price),
        "currency": currency,
        "tenor_months": tenor_months,
        "text": text,
        "signed_at": signed_at.isoformat(),
    }
    return LegalToken(
        token_id=token_id,
        kind="wad",
        text=text,
        payload=payload,
        signature=_sign(payload),
        signed_at=signed_at,
    )


def stamp_wakalah(
    *,
    execution_id: str,
    customer_id: str,
    customer_name: str,
    institution_name: str,
) -> LegalToken:
    signed_at = datetime.now(UTC)
    token_id = f"WAKALAH-{execution_id[:8].upper()}"
    text = WAKALAH_TEMPLATE.format(
        customer_name=customer_name,
        customer_id=customer_id,
        institution_name=institution_name,
    )
    payload = {
        "token_id": token_id,
        "kind": "wakalah",
        "execution_id": execution_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "institution_name": institution_name,
        "text": text,
        "signed_at": signed_at.isoformat(),
    }
    return LegalToken(
        token_id=token_id,
        kind="wakalah",
        text=text,
        payload=payload,
        signature=_sign(payload),
        signed_at=signed_at,
    )
