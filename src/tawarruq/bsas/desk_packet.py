"""Format Bursa BSAS dealing-desk request packets (email + JSON)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from tawarruq.bsas.base import LegContext
from tawarruq.bsas.product_codes import PURCHASE_TYPE_LABEL
from tawarruq.enums import LegNumber


def _money(value: float, currency: str) -> str:
    return f"{currency} {value:,.2f}"


def processing_instructions(*, include_follow_on_legs: bool = True) -> list[str]:
    lines = [
        "Leg 1: Execute the purchase as an Agent and provide the e-Certificate number.",
    ]
    if include_follow_on_legs:
        lines.append(
            "Legs 2 & 3: Proceed with the Ownership Transfer (OTC) and Sale to BMIS (STB) "
            "immediately following Leg 1 to complete the cycle."
        )
    return lines


def customer_desk_lines(context: LegContext) -> list[str]:
    currency = context.currency or "KES"
    return [
        f"End Customer Name: {context.resolved_customer_name()}",
        f"Customer Ref: {context.customer_ref}",
        f"Bid Amount (Cost Price): {_money(context.resolved_bid(), currency)}",
        f"Profit Amount: {_money(context.resolved_profit(), currency)}",
        f"Total Murabaha Price (Sale Amount): {_money(context.resolved_murabaha(), currency)}",
        f"Product Code: {context.resolved_product_code()}",
        f"Purchase Type: {PURCHASE_TYPE_LABEL}",
    ]


def build_desk_packet(context: LegContext, *, external_ref: str) -> dict[str, Any]:
    """Structured packet stored on disk and returned to the ops portal."""
    currency = context.currency or "KES"
    bid = context.resolved_bid()
    profit = context.resolved_profit()
    murabaha = context.resolved_murabaha()
    product = context.resolved_product_code()
    follow_on = context.leg_number == LegNumber.PURCHASE
    instructions = processing_instructions(include_follow_on_legs=follow_on)

    packet = {
        "format": "bursa_bsas_desk_v1",
        "external_ref": external_ref,
        "transaction_id": context.transaction_id,
        "application_id": context.application_id,
        "leg_number": str(context.leg_number),
        "leg_label": {
            "1": "Leg 1: Agent Purchase (BSAS)",
            "2": "Leg 2: Ownership Transfer (OTC)",
            "3": "Leg 3: Sale to BMIS (STB)",
        }.get(str(context.leg_number), f"Leg {context.leg_number}"),
        "institution_code": context.institution_code,
        "institution_name": context.institution_name,
        "customer": {
            "end_customer_name": context.resolved_customer_name(),
            "customer_ref": context.customer_ref,
        },
        "amounts": {
            "currency": currency,
            "bid_amount_cost_price": f"{bid:.2f}",
            "profit_amount": f"{profit:.2f}",
            "total_murabaha_price": f"{murabaha:.2f}",
            # legacy field kept for older consumers
            "amount": bid,
        },
        "product_code": product,
        "commodity_code": context.commodity_code,
        "purchase_type": context.purchase_type or "A",
        "purchase_type_label": PURCHASE_TYPE_LABEL,
        "processing_instructions": instructions,
        "submitted_at": datetime.now(UTC).isoformat(),
        "email_body": format_single_request_email(context, external_ref=external_ref),
    }
    return packet


def format_single_request_email(context: LegContext, *, external_ref: str) -> str:
    institution = context.institution_name or context.institution_code or "Institution"
    lines = [
        f"Subject: REQUEST FOR LIVE ACCESS — {institution}",
        "",
        f"Dear BSAS Ops & Dealing,",
        "",
        f"Please process the following Tawarruq facility for members under {institution}.",
        "",
        f"External Ref: {external_ref}",
        f"Transaction ID: {context.transaction_id}",
        f"Leg: {context.leg_number}",
        "",
        *customer_desk_lines(context),
        "",
        "Processing Instructions:",
        *[f"{idx}. {text}" for idx, text in enumerate(processing_instructions(include_follow_on_legs=context.leg_number == LegNumber.PURCHASE), start=1)],
        "",
        "Kindly share the generated e-certificate(s) once complete so we can update our records.",
        "",
        "Regards,",
        "Buruuj Fintech Tawarruq Engine",
    ]
    return "\n".join(lines)


def format_batch_desk_email(
    *,
    institution_name: str,
    institution_code: str,
    customers: list[dict[str, Any]],
) -> str:
    """Match the multi-customer Bursa desk email sample."""
    name = institution_name or institution_code or "Institution"
    lines = [
        f"Subject: REQUEST FOR LIVE ACCESS — {name}",
        "",
        "Dear BSAS Ops & Dealing,",
        "",
        f"Please process the following Tawarruq facilities for members under {name}.",
        "",
    ]
    for idx, item in enumerate(customers, start=1):
        currency = item.get("currency") or "KES"
        lines.extend(
            [
                f"--- Customer {idx} ---",
                f"End Customer Name: {item.get('end_customer_name') or item.get('customer_ref')}",
                f"Customer Ref: {item.get('customer_ref')}",
                f"External Ref: {item.get('external_ref')}",
                f"Bid Amount (Cost Price): {_money(float(item.get('bid_amount') or 0), currency)}",
                f"Profit Amount: {_money(float(item.get('profit_amount') or 0), currency)}",
                f"Total Murabaha Price (Sale Amount): {_money(float(item.get('murabaha_total') or 0), currency)}",
                f"Product Code: {item.get('product_code') or 'ACPO'}",
                f"Purchase Type: {PURCHASE_TYPE_LABEL}",
                "",
            ]
        )
    lines.extend(
        [
            "Processing Instructions:",
            "1. Leg 1: Execute the purchase as an Agent and provide the e-Certificate number.",
            "2. Legs 2 & 3: Proceed with the Ownership Transfer (OTC) and Sale to BMIS (STB) "
            "immediately following Leg 1 to complete the cycle.",
            "",
            "Kindly share the generated e-certificates once complete so we can update our records.",
            "",
            "Regards,",
            "Buruuj Fintech Tawarruq Engine",
        ]
    )
    return "\n".join(lines)
