"""Build enriched LegContext for BSAS backends from application + offer data."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from tawarruq.bsas.base import LegContext
from tawarruq.bsas.product_codes import (
    DEFAULT_CURRENCY,
    PURCHASE_TYPE_AGENT,
    bsas_product_code,
)
from tawarruq.enums import LegNumber
from tawarruq.models.application import FinancingApplication
from tawarruq.models.transaction import CommodityTransaction, TransactionLeg


def resolve_customer_name(application: FinancingApplication | None) -> str:
    if not application:
        return ""
    if application.customer_name and application.customer_name.strip():
        return application.customer_name.strip()
    if application.customer is not None and application.customer.full_name:
        return application.customer.full_name.strip()
    return application.customer_ref or ""


def build_leg_context(
    db: Session,
    transaction: CommodityTransaction,
    leg: TransactionLeg,
) -> LegContext:
    application = (
        db.query(FinancingApplication)
        .options(joinedload(FinancingApplication.offer), joinedload(FinancingApplication.customer))
        .filter(FinancingApplication.id == transaction.application_id)
        .first()
    )
    offer = application.offer if application else None
    bid = Decimal(str(offer.cost_price)) if offer else Decimal("0")
    profit = Decimal(str(offer.profit_amount)) if offer else Decimal("0")
    murabaha = Decimal(str(offer.total_payable)) if offer else bid + profit
    currency = (application.currency if application and application.currency else DEFAULT_CURRENCY).upper()
    institution = transaction.institution
    commodity = transaction.commodity_code or "PALM_OIL"

    return LegContext(
        transaction_id=transaction.id,
        leg_number=LegNumber(leg.leg_number),
        commodity_code=commodity,
        amount=float(bid),
        institution_code=institution.code if institution else "",
        institution_name=institution.name if institution else "",
        customer_ref=application.customer_ref if application else "",
        customer_name=resolve_customer_name(application),
        bid_amount=float(bid),
        profit_amount=float(profit),
        murabaha_total=float(murabaha),
        currency=currency,
        product_code=bsas_product_code(commodity),
        purchase_type=PURCHASE_TYPE_AGENT,
        application_id=application.id if application else transaction.application_id,
    )
