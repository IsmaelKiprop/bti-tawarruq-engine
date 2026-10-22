"""Electronic Wa'd, CMP, and SASC agency stamps.

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
from tawarruq.enums import SedaniaAgencyRole

SASC_LEGAL_NAME = "SEDANIA As Salam Capital"
SASC_PARTY_CODE = "SEDANIA_AS_SALAM_CAPITAL"
AS_SIDQ_PLATFORM = "AS SIDQ Digital Commodity Trading Platform"
COMMODITY_LABEL = "Telecommunication Airtime"

WAD_TEMPLATE = (
    "Wa'd (promise to purchase). The customer {customer_name} ({customer_id}) undertakes to "
    "purchase from {institution_name} the {commodity} allocated under this facility, "
    "at the deferred Murabahah price of {deferred_price} {currency} over {tenor_months} months. "
    "This stamp is issued under the board-approved Tawarruq template."
)

CMP_TEMPLATE = (
    "Commodity Murabahah Program. The customer {customer_name} ({customer_id}) applies to "
    "{institution_name} for {amount} {currency} financing, signs the financing contract, and "
    "enters the Commodity Murabahah Program. Under the Terms and Conditions the customer may "
    "appoint {sasc} independently as {agency_role} to sell the commodity to potential purchasers "
    "at the end of the program via {platform}."
)

WAKALAH_TEMPLATE = (
    "Wakalah (liquidation agency mandate). The customer {customer_name} ({customer_id}) appoints "
    "{sasc} independently as wakeel (agent) to sell the allocated {commodity} on a spot and random "
    "basis to random commodity purchasers via {platform}. {institution_name} remains the financier. "
    "Buruuj Fintech operates the technology rail only and does not act as wakeel."
)

RASUL_TEMPLATE = (
    "Rasul (messenger mandate). The customer {customer_name} ({customer_id}) appoints {sasc} "
    "independently as Rasul (messenger) to convey the sale of the allocated {commodity} on a spot "
    "and random basis to random commodity purchasers via {platform}. {sasc} does not act as wakeel. "
    "{institution_name} remains the financier. Buruuj Fintech operates the technology rail only."
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
        commodity=COMMODITY_LABEL,
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


def stamp_cmp(
    *,
    execution_id: str,
    customer_id: str,
    customer_name: str,
    institution_name: str,
    amount: Decimal,
    currency: str,
    agency_role: str,
) -> LegalToken:
    signed_at = datetime.now(UTC)
    token_id = f"CMP-{execution_id[:8].upper()}"
    role = "wakeel (agent)" if agency_role == SedaniaAgencyRole.WAKEEL else "Rasul (messenger)"
    text = CMP_TEMPLATE.format(
        customer_name=customer_name,
        customer_id=customer_id,
        institution_name=institution_name,
        amount=f"{amount:.2f}",
        currency=currency,
        sasc=SASC_LEGAL_NAME,
        agency_role=role,
        platform=AS_SIDQ_PLATFORM,
    )
    payload = {
        "token_id": token_id,
        "kind": "cmp",
        "execution_id": execution_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "institution_name": institution_name,
        "amount": str(amount),
        "currency": currency,
        "agency_role": agency_role,
        "agency_party": SASC_PARTY_CODE,
        "text": text,
        "signed_at": signed_at.isoformat(),
    }
    return LegalToken(
        token_id=token_id,
        kind="cmp",
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
    agency_role: str = SedaniaAgencyRole.WAKEEL,
) -> LegalToken:
    """Appoint SASC independently. `agency_role` is wakeel (approved) or rasul (AAOIFI)."""
    signed_at = datetime.now(UTC)
    role = agency_role if agency_role in {SedaniaAgencyRole.WAKEEL, SedaniaAgencyRole.RASUL} else SedaniaAgencyRole.WAKEEL
    if role == SedaniaAgencyRole.RASUL:
        token_id = f"RASUL-{execution_id[:8].upper()}"
        kind = "rasul"
        text = RASUL_TEMPLATE.format(
            customer_name=customer_name,
            customer_id=customer_id,
            sasc=SASC_LEGAL_NAME,
            commodity=COMMODITY_LABEL,
            platform=AS_SIDQ_PLATFORM,
            institution_name=institution_name,
        )
    else:
        token_id = f"WAKALAH-{execution_id[:8].upper()}"
        kind = "wakalah"
        text = WAKALAH_TEMPLATE.format(
            customer_name=customer_name,
            customer_id=customer_id,
            sasc=SASC_LEGAL_NAME,
            commodity=COMMODITY_LABEL,
            platform=AS_SIDQ_PLATFORM,
            institution_name=institution_name,
        )
    payload = {
        "token_id": token_id,
        "kind": kind,
        "execution_id": execution_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "institution_name": institution_name,
        "agency_role": role,
        "agency_party": SASC_PARTY_CODE,
        "text": text,
        "signed_at": signed_at.isoformat(),
    }
    return LegalToken(
        token_id=token_id,
        kind=kind,
        text=text,
        payload=payload,
        signature=_sign(payload),
        signed_at=signed_at,
    )
