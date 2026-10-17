from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from tawarruq.database import get_db
from tawarruq.enums import AuditActor, LegStatus
from tawarruq.models.application import FinancingApplication, FinancingOffer
from tawarruq.models.business import CustomerAgency, CustomerSale, TawarruqFinancingCertificate
from tawarruq.models.certificate import Certificate
from tawarruq.models.customer import Customer
from tawarruq.models.disbursement import Disbursement
from tawarruq.models.kenya_flow import AssetBatch, MurabahaContract
from tawarruq.models.transaction import CommodityTransaction, TransactionLeg
from tawarruq.services.trade_evidence_service import (
    TRADE_DOC_KINDS,
    build_trade_document,
    render_trade_document_html,
    trade_documents_payload,
)

router = APIRouter(tags=["Customer Journey"])


def _resolve_application(
    db: Session,
    application_ref: str,
    phone: str | None = None,
) -> FinancingApplication:
    application = (
        db.query(FinancingApplication)
        .options(
            joinedload(FinancingApplication.customer),
            joinedload(FinancingApplication.offer),
            joinedload(FinancingApplication.customer_agency),
            joinedload(FinancingApplication.customer_sale),
            joinedload(FinancingApplication.murabaha_contract).joinedload(MurabahaContract.installments),
            joinedload(FinancingApplication.disbursements).joinedload(Disbursement.wallet_disbursement),
            joinedload(FinancingApplication.disbursements).joinedload(Disbursement.tawarruq_certificate),
            joinedload(FinancingApplication.institution),
        )
        .filter(
            (FinancingApplication.id == application_ref)
            | (FinancingApplication.customer_ref == application_ref)
        )
        .first()
    )

    if not application:
        cert = db.query(TawarruqFinancingCertificate).filter(TawarruqFinancingCertificate.certificate_number == application_ref).first()
        if cert:
            application = db.get(FinancingApplication, cert.application_id)

    if not application:
        leg = (
            db.query(TransactionLeg)
            .filter((TransactionLeg.external_ref == application_ref) | (TransactionLeg.certificate_number == application_ref))
            .first()
        )
        if leg and leg.transaction_id:
            txn = db.get(CommodityTransaction, leg.transaction_id)
            if txn and txn.application_id:
                application = db.get(FinancingApplication, txn.application_id)

    if not application:
        batch = (
            db.query(AssetBatch)
            .filter((AssetBatch.batch_id == application_ref) | (AssetBatch.mno_receipt_id == application_ref))
            .first()
        )
        if batch and batch.leg_id:
            leg = db.get(TransactionLeg, batch.leg_id)
            if leg and leg.transaction_id:
                txn = db.get(CommodityTransaction, leg.transaction_id)
                if txn and txn.application_id:
                    application = db.get(FinancingApplication, txn.application_id)

    if not application:
        txn = db.get(CommodityTransaction, application_ref)
        if txn and txn.application_id:
            application = db.get(FinancingApplication, txn.application_id)

    if not application:
        customer = (
            db.query(Customer)
            .filter((Customer.national_id == application_ref) | (Customer.phone == application_ref))
            .first()
        )
        if customer and customer.applications:
            application = sorted(customer.applications, key=lambda a: a.created_at, reverse=True)[0]

    if not application:
        raise HTTPException(status_code=404, detail=f"Application '{application_ref}' not found")

    if phone and application.customer and application.customer.phone:
        norm_cust = application.customer.phone.replace("+", "").strip()
        norm_in = phone.replace("+", "").strip()
        if norm_cust != norm_in:
            raise HTTPException(status_code=403, detail="Phone number does not match this application")

    return application


def _latest_disbursement(application: FinancingApplication) -> Disbursement | None:
    rows = list(getattr(application, "disbursements", None) or [])
    if not rows:
        return None
    return sorted(rows, key=lambda row: row.disbursed_at or row.id, reverse=True)[0]


def _wakala_ref(agency: CustomerAgency | None) -> str | None:
    if not agency or not agency.notes:
        return None
    notes = agency.notes
    marker = "ref="
    if marker in notes:
        parts = notes.split(marker, 1)
        return parts[1].strip() or None
    return notes.strip() or None


def _latest_transaction(db: Session, application_id: str) -> CommodityTransaction | None:
    return (
        db.query(CommodityTransaction)
        .options(
            joinedload(CommodityTransaction.legs).joinedload(TransactionLeg.certificate),
            joinedload(CommodityTransaction.legs).joinedload(TransactionLeg.asset_batch),
        )
        .filter(CommodityTransaction.application_id == application_id)
        .order_by(CommodityTransaction.created_at.desc())
        .first()
    )


def _build_journey(application: FinancingApplication, transaction: CommodityTransaction | None) -> dict:
    offer = getattr(application, "offer", None)
    contract = getattr(application, "murabaha_contract", None)
    customer_sale = getattr(application, "customer_sale", None)
    customer_agency = getattr(application, "customer_agency", None)
    disbursement = _latest_disbursement(application)
    wallet = getattr(disbursement, "wallet_disbursement", None) if disbursement else None
    tawarruq_cert = getattr(disbursement, "tawarruq_certificate", None) if disbursement else None

    legs = transaction.legs if transaction else []
    leg_map = {str(leg.leg_number): leg for leg in legs}
    leg1 = leg_map.get("1")
    leg2 = leg_map.get("2")
    leg3 = leg_map.get("3")

    track = "kenya" if (application.customer_id or (transaction and transaction.mode in ("mno", "agent_dealer"))) else "malaysia"
    installments = contract.installments if contract else []
    paid = sum(1 for i in installments if i.status == "paid")
    total = len(installments)

    def _leg_cert(leg: TransactionLeg | None):
        if not leg:
            return None
        if getattr(leg, "certificate", None):
            c = leg.certificate
            return {
                "certificate_number": c.certificate_number,
                "issuer": c.issuer,
                "downloadable": bool(c.pdf_path or c.pdf_filename),
                "type": "bsas_cert",
            }
        return None

    def _status(done: bool, active: bool = False) -> str:
        if done:
            return "done"
        if active:
            return "active"
        return "pending"

    leg1_batch = getattr(leg1, "asset_batch", None) if leg1 else None
    documents = trade_documents_payload(leg1_batch) if leg1_batch else {}

    steps = [
        {
            "number": 1,
            "label": "Facility Application & Wakalah Agreement",
            "description": "Customer applies for financing and executes a Wa'd (promise to purchase) and Wakalah (agency) agreement.",
            "actor": "Customer + Institution",
            "status": "done",
            "timestamp": application.created_at.isoformat() if application.created_at else None,
            "wad_accepted": bool(application.wad_accepted_at),
            "wad_text": "Customer applies for financing and executes a Wa'd (promise to purchase) and Wakalah (agency) agreement.",
        },
        {
            "number": 2,
            "label": "Spot Purchase (Leg 1)",
            "description": "Institution purchases the commodity on spot via Buruuj Fintech. Constructive possession is confirmed.",
            "actor": "Buruuj Fintech / Institution",
            "status": _status(leg1 and leg1.status == LegStatus.CONFIRMED.value, leg1 and leg1.status != LegStatus.CONFIRMED.value),
            "timestamp": leg1.executed_at.isoformat() if (leg1 and leg1.executed_at) else None,
            "certificate": _leg_cert(leg1),
            "documents": documents,
        },
        {
            "number": 3,
            "label": "Constructive Possession Confirmed",
            "description": "Ownership and title of the commodity is confirmed in the name of the institution.",
            "actor": "Buruuj Fintech",
            "status": _status(bool(leg1_batch and leg1_batch.possession_status == "confirmed"), bool(leg1 and leg1.status == LegStatus.AWAITING_POSSESSION.value)),
            "timestamp": leg1_batch.verified_at.isoformat() if (leg1_batch and leg1_batch.verified_at) else None,
            "documents": documents,
        },
        {
            "number": 4,
            "label": "Murabaha Sale to You (Leg 2)",
            "description": "Institution sells the commodity to you at cost plus disclosed profit on deferred payment terms.",
            "actor": "Institution → Customer",
            "status": _status(leg2 and leg2.status == LegStatus.CONFIRMED.value, bool(offer and not (contract and contract.signed_at))),
            "timestamp": contract.signed_at.isoformat() if (contract and contract.signed_at) else None,
            "certificate": _leg_cert(leg2),
        },
        {
            "number": 5,
            "label": "Wakala Agency Activation",
            "description": "Buruuj Fintech is activated as your agent to sell the commodity on your behalf on the open market.",
            "actor": "Buruuj Fintech (acting for Customer)",
            "status": _status(customer_agency is not None, bool(contract and contract.signed_at and not customer_agency)),
            "timestamp": customer_agency.appointed_at.isoformat() if customer_agency else None,
            "wakala_ref": _wakala_ref(customer_agency),
            "wakala_notes": customer_agency.notes if customer_agency else None,
        },
        {
            "number": 6,
            "label": "Independent Spot Liquidation (Leg 3)",
            "description": "Buruuj sells the commodity to an independent third-party buyer. Bai' al-Inah guardrail verified.",
            "actor": "Buruuj Fintech → Open Market",
            "status": _status(leg3 and leg3.status == LegStatus.CONFIRMED.value, bool(customer_agency and not (leg3 and leg3.status == LegStatus.CONFIRMED.value))),
            "timestamp": leg3.executed_at.isoformat() if (leg3 and leg3.executed_at) else None,
            "certificate": _leg_cert(leg3),
        },
        {
            "number": 7,
            "label": "Cash Disbursement to Your Account",
            "description": "The spot proceeds are disbursed directly to your wallet or bank account.",
            "actor": "Buruuj Fintech → Customer Wallet",
            "status": _status(bool(wallet and wallet.status == "credited"), bool(disbursement and not (wallet and wallet.status == "credited"))),
            "timestamp": wallet.credited_at.isoformat() if (wallet and wallet.credited_at) else None,
            "certificate": {
                "certificate_number": tawarruq_cert.certificate_number,
                "issuer": "Buruuj Fintech Ltd",
                "downloadable": True,
                "type": "bti_tawarruq_cert",
            } if tawarruq_cert else None,
        },
        {
            "number": 8,
            "label": "Repayment Schedule",
            "description": f"You repay the Murabaha balance in {total} instalment(s) as per the agreed schedule.",
            "actor": "Customer → Institution",
            "status": _status(total > 0 and paid == total, total > 0 and paid < total),
            "timestamp": None,
            "installments_total": total,
            "installments_paid": paid,
            "next_due": next((i.due_date.isoformat() for i in installments if i.status != "paid" and i.due_date), None),
            "wallet_txn_id": wallet.external_txn_id if wallet else None,
            "wallet_provider": wallet.provider if wallet else None,
            "wallet_credited": bool(wallet and wallet.status == "credited"),
            "payments": [
                {
                    "installment_number": item.installment_number,
                    "amount": str(item.amount),
                    "status": item.status,
                    "payment_ref": item.payment_ref,
                }
                for item in installments
            ],
        },
    ]

    certs = []
    if documents:
        for kind in TRADE_DOC_KINDS:
            meta = documents.get(kind)
            if meta:
                certs.append({
                    "step": 2,
                    "label": meta.get("title", kind),
                    "certificate_number": meta.get("reference", ""),
                    "issuer": "Buruuj Fintech Ltd",
                    "downloadable": True,
                    "type": f"trade_{kind}",
                })
    for step in steps:
        if step.get("certificate"):
            certs.append({
                "step": step["number"],
                "label": step.get("label", "Certificate"),
                **step["certificate"],
            })

    customer_action = None
    if offer and not offer.accepted_at:
        customer_action = "accept"
    elif contract and not contract.signed_at:
        customer_action = "sign"

    done_steps = sum(1 for s in steps if s["status"] == "done")

    return {
        "application_id": application.id,
        "customer_ref": application.customer_ref,
        "customer_name": application.customer.full_name if application.customer else application.customer_ref,
        "customer_phone": application.customer.phone if application.customer else None,
        "track": track,
        "status": application.status,
        "amount": str(application.amount_requested),
        "term_months": application.term_months,
        "currency": application.currency or "KES",
        "murabaha_total": str(offer.total_payable) if offer else None,
        "profit": str(offer.profit_amount) if offer else None,
        "offer_accepted": bool(offer and offer.accepted_at),
        "contract_signed": bool(contract and contract.signed_at),
        "customer_action": customer_action,
        "commodity": transaction.commodity_code if transaction else "PALM_OIL",
        "wad_accepted": bool(application.wad_accepted_at),
        "wad_text": "Customer applies for financing and executes a Wa'd (promise to purchase) and Wakalah (agency) agreement.",
        "trade_documents": documents,
        "institution_name": application.institution.name if application.institution else "Institution",
        "created_at": application.created_at.isoformat() if application.created_at else None,
        "steps": steps,
        "certificates": certs,
        "overall_progress": round(done_steps / len(steps) * 100),
        "total_steps": len(steps),
    }


@router.get("/customer/applications/{application_ref}/journey")
def customer_journey(
    application_ref: str,
    phone: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    application = _resolve_application(db, application_ref, phone)
    return _build_journey(application, _latest_transaction(db, application.id))


@router.post("/customer/applications/{application_ref}/accept")
def customer_accept_offer(
    application_ref: str,
    phone: str | None = Query(None),
    db: Session = Depends(get_db),
):
    application = _resolve_application(db, application_ref, phone)
    from tawarruq.services.application_service import accept_offer

    try:
        accept_offer(db, application.id, actor=AuditActor.CUSTOMER)
        db.commit()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return customer_journey(application_ref, phone=phone, db=db)


@router.post("/customer/applications/{application_ref}/sign")
def customer_sign_contract(
    application_ref: str,
    phone: str | None = Query(None),
    db: Session = Depends(get_db),
):
    application = _resolve_application(db, application_ref, phone)
    from tawarruq.services.repayment_service import sign_murabaha_contract

    try:
        sign_murabaha_contract(db, application.id, actor=AuditActor.CUSTOMER)
        db.commit()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return customer_journey(application_ref, phone=phone, db=db)


@router.get("/customer/applications/{application_ref}/trade-documents/{kind}")
def download_trade_document(
    application_ref: str,
    kind: str,
    phone: str | None = Query(None),
    db: Session = Depends(get_db),
):
    application = _resolve_application(db, application_ref, phone)
    transaction = _latest_transaction(db, application.id)
    if not transaction:
        raise HTTPException(status_code=404, detail="No transaction found for this application")
    leg1 = next((leg for leg in transaction.legs if str(leg.leg_number) == "1"), None)
    batch = getattr(leg1, "asset_batch", None) if leg1 else None
    if not batch:
        raise HTTPException(status_code=404, detail="Trade documents not available yet (Leg 1 not confirmed)")
    try:
        doc = build_trade_document(batch, kind=kind, commodity_code=transaction.commodity_code)
        html = render_trade_document_html(doc)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return Response(content=html, media_type="text/html")


@router.get("/customer/applications/{application_ref}/certificates")
def customer_certificates(
    application_ref: str,
    db: Session = Depends(get_db),
) -> list:
    journey = customer_journey(application_ref, phone=None, db=db)
    return journey.get("certificates", [])


@router.get("/customer/applications/{application_ref}/certificate")
def customer_certificate(
    application_ref: str,
    db: Session = Depends(get_db),
):
    journey = customer_journey(application_ref, phone=None, db=db)
    certs = journey.get("certificates", [])
    bti = next((c for c in certs if c.get("type") == "bti_tawarruq_cert"), None)
    if not bti:
        bti = next((c for c in certs if c.get("downloadable")), None)
    if not bti:
        raise HTTPException(status_code=404, detail="No certificate is available for this application yet")
    return {
        "application_ref": journey.get("customer_ref"),
        "customer_name": journey.get("customer_name"),
        "track": journey.get("track"),
        "certificate": bti,
        "downloadable": True,
        "print_hint": "Open the customer journey tracker and use Print / Download PDF.",
    }


@router.get("/customer/applications/{application_ref}")
def customer_application_summary(
    application_ref: str,
    phone: str | None = Query(None),
    db: Session = Depends(get_db),
):
    journey = customer_journey(application_ref, phone=phone, db=db)
    return {
        "application_id": journey.get("application_id"),
        "application_ref": journey.get("customer_ref"),
        "customer_name": journey.get("customer_name"),
        "customer_phone": journey.get("customer_phone"),
        "track": journey.get("track"),
        "status": journey.get("status"),
        "amount": journey.get("amount"),
        "currency": journey.get("currency"),
        "murabaha_total": journey.get("murabaha_total"),
        "profit": journey.get("profit"),
        "commodity": journey.get("commodity"),
        "institution_name": journey.get("institution_name"),
        "created_at": journey.get("created_at"),
        "overall_progress": journey.get("overall_progress"),
        "total_steps": journey.get("total_steps"),
    }


@router.get("/customer/applications")
def customer_applications_by_phone(
    phone: str = Query(..., description="Customer phone number"),
    db: Session = Depends(get_db),
):
    customers = db.query(Customer).filter(Customer.phone == phone).all()
    if not customers:
        raise HTTPException(status_code=404, detail="No applications found for this phone number")
    results = []
    for customer in customers:
        for app in customer.applications:
            results.append({
                "application_id": app.id,
                "customer_ref": app.customer_ref,
                "amount": str(app.amount_requested),
                "currency": app.currency or "KES",
                "status": app.status,
                "institution": app.institution.name if app.institution else None,
                "created_at": app.created_at.isoformat() if app.created_at else None,
            })
    return results
