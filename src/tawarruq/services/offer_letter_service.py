"""Letter of Offer / Murabaha pack — narrative aligned to KCS SACCO Commodity Murabaha (Tawarruq).

Template reference: docs/Contract Faraj Rashid.pdf (Letter of Offer + Agency Agreement).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

Attachment = tuple[str, bytes, str]


def _money(value: object) -> str:
    try:
        amount = Decimal(str(value).replace(",", "").strip() or "0")
    except Exception:
        return str(value or "0")
    return f"{amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"


def _int(value: object, default: int = 1) -> int:
    try:
        n = int(str(value).strip())
        return n if n > 0 else default
    except Exception:
        return default


def _text(value: object) -> str:
    if value is None or value == "":
        return "-"
    return str(value).encode("latin-1", "replace").decode("latin-1")


def compute_offer_figures(
    *,
    cost_price: object,
    profit: object,
    term_months: object = 1,
) -> dict[str, Any]:
    cost = Decimal(str(cost_price or "0").replace(",", "") or "0")
    margin = Decimal(str(profit or "0").replace(",", "") or "0")
    months = _int(term_months, 1)
    contract = cost + margin
    installment = (contract / Decimal(months)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        "cost_price": cost,
        "profit_margin": margin,
        "contract_price": contract,
        "term_months": months,
        "monthly_installment": installment,
    }


def offer_pack_from_application(application) -> dict[str, Any]:
    offer = getattr(application, "offer", None)
    customer = getattr(application, "customer", None)
    institution = getattr(application, "institution", None)
    cost = getattr(offer, "cost_price", None) or getattr(application, "amount_requested", 0)
    profit = getattr(offer, "profit_amount", None) or 0
    figures = compute_offer_figures(
        cost_price=cost,
        profit=profit,
        term_months=getattr(application, "term_months", 1) or 1,
    )
    commodity = "fast moving goods e.g. palm oil / airtime"
    purpose = str(getattr(application, "purpose", "") or "")
    if "Palm Oil" in purpose:
        commodity = "fast moving goods e.g. palm oil"
    elif "Airtime" in purpose.lower() or "airtime" in purpose.lower():
        commodity = "fast moving goods e.g. airtime float"
    return {
        "institution_name": institution.name if institution else "Financial Institution",
        "institution_code": getattr(institution, "code", None) or "FI",
        "customer_name": getattr(customer, "full_name", None) or getattr(application, "customer_name", None) or "Member",
        "customer_email": getattr(customer, "email", None),
        "customer_phone": getattr(customer, "phone", None),
        "customer_ref": getattr(application, "customer_ref", None) or application.id[:8],
        "currency": (getattr(application, "currency", None) or "KES").upper(),
        "commodity": commodity,
        "offer_date": date.today().isoformat(),
        "valid_until": (date.today() + timedelta(days=30)).isoformat(),
        **{k: str(v) for k, v in figures.items() if k != "term_months"},
        "term_months": figures["term_months"],
        "cost_price": _money(figures["cost_price"]),
        "profit_margin": _money(figures["profit_margin"]),
        "contract_price": _money(figures["contract_price"]),
        "monthly_installment": _money(figures["monthly_installment"]),
    }


def offer_pack_from_desk(case, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    body = payload or {}
    orig = body.get("origination") if isinstance(body.get("origination"), dict) else {}
    journey = body.get("journey") if isinstance(body.get("journey"), dict) else {}
    institution = getattr(case, "institution", None)
    figures = compute_offer_figures(
        cost_price=orig.get("approved_facility_amount"),
        profit=orig.get("profit"),
        term_months=orig.get("term_months") or orig.get("repayment_period_months") or 1,
    )
    product = str(orig.get("facility_product_type") or "Airtime")
    commodity = {
        "Airtime": "fast moving goods e.g. airtime float",
        "Palm Oil": "fast moving goods e.g. palm oil",
        "Other": "fast moving goods as specified in the purchase requisition",
    }.get(product, "fast moving goods e.g. palm oil")
    ref = journey.get("customer_ref") or getattr(case, "id", "case")[:8]
    return {
        "institution_name": institution.name if institution else "Financial Institution",
        "institution_code": getattr(institution, "code", None) or "FI",
        "customer_name": orig.get("customer_name") or "Member",
        "customer_email": orig.get("customer_email"),
        "customer_phone": orig.get("customer_phone"),
        "customer_ref": ref,
        "currency": "KES",
        "commodity": commodity,
        "offer_date": date.today().isoformat(),
        "valid_until": (date.today() + timedelta(days=30)).isoformat(),
        "term_months": figures["term_months"],
        "cost_price": _money(figures["cost_price"]),
        "profit_margin": _money(figures["profit_margin"]),
        "contract_price": _money(figures["contract_price"]),
        "monthly_installment": _money(figures["monthly_installment"]),
    }


def render_letter_of_offer_pdf(pack: dict[str, Any]) -> bytes:
    """Page 1 narrative: Letter of Offer Commodity Murabaha/Monetization (Tawarruq)."""
    from tawarruq.services.certificate_mail_service import render_certificate_pdf

    currency = pack.get("currency") or "KES"
    return render_certificate_pdf(
        title="Letter of Offer — Commodity Murabaha / Monetization (Tawarruq)",
        subtitle=(
            f"{_text(pack.get('institution_name'))}. "
            "Shariah-compliant facility for the purchase of fast-moving consumer goods."
        ),
        doc_ref=str(pack.get("customer_ref") or "OFFER"),
        sections=[
            (
                "Parties",
                [
                    ("Institution", pack.get("institution_name")),
                    ("Member", pack.get("customer_name")),
                    ("Email", pack.get("customer_email")),
                    ("Phone", pack.get("customer_phone")),
                    ("Offer date", pack.get("offer_date")),
                    ("Valid until (30 days)", pack.get("valid_until")),
                ],
            ),
            (
                "1. Financing contract",
                [
                    ("Commodity", pack.get("commodity")),
                    ("Cost price", f"{currency} {pack.get('cost_price')}"),
                    ("Profit margin", f"{currency} {pack.get('profit_margin')}"),
                    ("Contract price (total payable)", f"{currency} {pack.get('contract_price')}"),
                    ("Monthly installments", f"{currency} {pack.get('monthly_installment')}"),
                    ("Repayment period", f"{pack.get('term_months')} months"),
                ],
            ),
            (
                "2. Conditions",
                [
                    ("Security", "Guarantors and/or other security as agreed with the institution"),
                    ("Proof of need", "Member confirms a genuine financing need"),
                    ("Vendor payment", "Purchase price is paid to the vendor/supplier as agent"),
                    ("Acceptance", "Member must accept this offer before the Tawarruq trade runs"),
                    ("Price lock", "Once the sale is effected the contract price does not change (Shariah)"),
                    ("Default charity", "Late payment charity at 10% p.a. to the Shariah charity fund (not riba)"),
                ],
            ),
            (
                "3. Member acceptance",
                [
                    ("Name", pack.get("customer_name")),
                    ("Signature", "_________________________"),
                    ("Date", "_________________________"),
                    ("Witness", "_________________________"),
                ],
            ),
        ],
        note=(
            "This letter follows the Commodity Murabaha/Monetization (Tawarruq) narrative used by "
            "Kenyan SACCO practice (Letter of Offer, Asset Finance Murabaha Agreement, and Agency Appointment). "
            "Accept via the customer journey link or return a signed physical copy to the institution."
        ),
    )


def render_agency_appointment_pdf(pack: dict[str, Any]) -> bytes:
    """Page 5 narrative: Agency Agreement — FI as agent to buy/sell commodities."""
    from tawarruq.services.certificate_mail_service import render_certificate_pdf

    return render_certificate_pdf(
        title="Agency Agreement — Commodity Murabaha / Tawarruq",
        subtitle="Appointment of the institution as Agent to acquire and monetize commodities.",
        doc_ref=f"AGENCY-{pack.get('customer_ref') or 'OFFER'}",
        sections=[
            (
                "Appointment",
                [
                    ("To (Agent)", pack.get("institution_name")),
                    ("From (Member)", pack.get("customer_name")),
                    ("Facility ref", pack.get("customer_ref")),
                    ("Commodity", pack.get("commodity")),
                ],
            ),
            (
                "Scope",
                [
                    (
                        "1",
                        "Agent receives goods from suppliers on purchase requisitions endorsed for this member.",
                    ),
                    (
                        "2",
                        "Agent may sell the commodities on a Shariah-compliant platform and deposit proceeds "
                        "to the member account / CASA as arranged.",
                    ),
                    (
                        "3",
                        "Acquisition may be physical or constructive possession, as allowed in the Murabaha agreement.",
                    ),
                ],
            ),
            (
                "Annex 1 — Repayment schedule (summary)",
                [
                    ("Contract price", f"{pack.get('currency') or 'KES'} {pack.get('contract_price')}"),
                    ("Installments", f"{pack.get('term_months')} x {pack.get('currency') or 'KES'} {pack.get('monthly_installment')}"),
                    ("First due", "As recorded after Murabaha sale on the desk"),
                ],
            ),
            (
                "Execution",
                [
                    ("Signature of Agent (Institution)", "_________________________"),
                    ("Signature of Member", "_________________________"),
                    ("Date", datetime.now(timezone.utc).date().isoformat()),
                ],
            ),
        ],
        note=(
            "Governing law: laws of Kenya (including Co-operative Societies Act Cap 490 where applicable). "
            "Disputes may be referred to the Shariah/Technical Committee before court appeal."
        ),
    )


def offer_letter_attachments(pack: dict[str, Any]) -> list[Attachment]:
    from tawarruq.services.certificate_mail_service import pdf_bytes_attachment

    ref = str(pack.get("customer_ref") or "offer")[:16]
    return [
        pdf_bytes_attachment(f"{ref}-letter-of-offer.pdf", render_letter_of_offer_pdf(pack)),
        pdf_bytes_attachment(f"{ref}-agency-agreement.pdf", render_agency_appointment_pdf(pack)),
    ]


def desk_offer_letter_attachment(case, kind: str = "offer") -> Attachment | None:
    import json

    try:
        payload = json.loads(case.payload_json or "{}")
    except Exception:
        payload = {}
    pack = offer_pack_from_desk(case, payload)
    items = offer_letter_attachments(pack)
    key = str(kind or "offer").strip().lower()
    if key in {"agency", "agency-agreement", "agency_agreement"}:
        return items[1] if len(items) > 1 else None
    return items[0] if items else None
