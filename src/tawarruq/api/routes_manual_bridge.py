"""Malaysia BSAS manual-bridge ops endpoints."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tawarruq.amanah.worker import AmanahWorker
from tawarruq.api.deps import require_tenant_access, tenant_filter_institution_id
from tawarruq.database import get_db
from tawarruq.enums import TransactionMode
from tawarruq.models.transaction import CommodityTransaction
from tawarruq.services import manual_bridge_service
from tawarruq.services.transaction_service import get_transaction_detail

router = APIRouter(tags=["Malaysia Manual Bridge"])


class ManualBridgePendingItem(BaseModel):
    transaction_id: str
    application_id: str
    institution_id: str | None = None
    institution_code: str | None = None
    institution_name: str | None = None
    customer_ref: str | None = None
    customer_name: str | None = None
    currency: str | None = "KES"
    amount_requested: str | None = None
    bid_amount: str | None = None
    profit_amount: str | None = None
    murabaha_total: str | None = None
    commodity_code: str
    product_code: str | None = None
    purchase_type: str | None = "A"
    transaction_status: str
    leg_number: str
    leg_label: str
    leg_status: str
    external_ref: str | None = None
    request: dict | None = None
    email_body: str | None = None
    created_at: str | None = None


class ManualBridgeDetail(ManualBridgePendingItem):
    reply_on_disk: bool = False
    ops_instructions: list[str] = Field(default_factory=list)


class ManualBridgeInboxSummary(BaseModel):
    inbox_dir: str
    request_count: int
    reply_count: int
    unanswered_request_refs: list[str]


class DeskBatchCustomer(BaseModel):
    end_customer_name: str | None = None
    customer_ref: str | None = None
    external_ref: str | None = None
    transaction_id: str | None = None
    application_id: str | None = None
    currency: str = "KES"
    bid_amount: float
    profit_amount: float
    murabaha_total: float
    product_code: str
    purchase_type: str = "A"


class DeskBatchResponse(BaseModel):
    institution_id: str | None = None
    institution_name: str | None = None
    institution_code: str | None = None
    leg_number: str
    customer_count: int
    customers: list[DeskBatchCustomer]
    email_body: str
    batch_email_path: str | None = None
    batch_json_path: str | None = None
    generated_at: str


@router.get(
    "/manual-bridge/pending",
    response_model=list[ManualBridgePendingItem],
    summary="List legs awaiting BSAS e-certificate",
    description=(
        "Ops inbox for Malaysia `manual_bridge` mode. "
        "Each item is a leg where Amanah generated a Bursa desk request packet and is waiting for "
        "ops to paste the e-certificate number after trading on the BSAS portal / bank desk."
    ),
)
def list_pending(
    request: Request,
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
) -> list[ManualBridgePendingItem]:
    items = manual_bridge_service.list_pending_manual_items(db, limit=limit)
    scoped = tenant_filter_institution_id(request, None)
    if scoped:
        items = [item for item in items if item.get("institution_id") == scoped]
    return [ManualBridgePendingItem(**item) for item in items]


@router.get(
    "/manual-bridge/inbox",
    response_model=ManualBridgeInboxSummary,
    summary="Manual-bridge file inbox summary",
    description="Shows request/reply file counts under MANUAL_BRIDGE_INBOX_DIR.",
)
def inbox_summary() -> ManualBridgeInboxSummary:
    return ManualBridgeInboxSummary(**manual_bridge_service.inbox_summary())


@router.get(
    "/manual-bridge/desk-batch",
    response_model=DeskBatchResponse,
    summary="Build Bursa multi-customer desk email",
    description=(
        "Aggregates unanswered Leg-1 manual-bridge requests into one email matching the "
        "BSAS Ops REQUEST FOR LIVE ACCESS format (customer name, bid, profit, murabaha, ACPO, Agent)."
    ),
)
def desk_batch(
    request: Request,
    institution_id: str | None = Query(None),
    leg_number: str = Query("1", pattern="^[123]$"),
    db: Session = Depends(get_db),
) -> DeskBatchResponse:
    scoped = tenant_filter_institution_id(request, institution_id)
    batch = manual_bridge_service.build_desk_batch(
        db,
        institution_id=scoped or institution_id,
        leg_number=leg_number,
    )
    return DeskBatchResponse(**batch)


@router.get(
    "/manual-bridge/desk-batch.txt",
    summary="Bursa desk batch email (plain text)",
    response_class=Response,
)
def desk_batch_text(
    request: Request,
    institution_id: str | None = Query(None),
    leg_number: str = Query("1", pattern="^[123]$"),
    db: Session = Depends(get_db),
) -> Response:
    scoped = tenant_filter_institution_id(request, institution_id)
    batch = manual_bridge_service.build_desk_batch(
        db,
        institution_id=scoped or institution_id,
        leg_number=leg_number,
    )
    return Response(content=batch["email_body"], media_type="text/plain; charset=utf-8")


@router.get(
    "/manual-bridge/transactions/{transaction_id}/legs/{leg_number}",
    response_model=ManualBridgeDetail,
    summary="Get BSAS request packet for a leg",
    description=(
        "Returns the structured Bursa desk packet ops should submit to BSAS, plus paste-certificate instructions."
    ),
)
def get_leg_detail(
    transaction_id: str,
    leg_number: str,
    request: Request,
    db: Session = Depends(get_db),
) -> ManualBridgeDetail:
    if leg_number not in ("1", "2", "3"):
        raise HTTPException(status_code=400, detail="leg_number must be 1, 2, or 3")
    txn = db.get(CommodityTransaction, transaction_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    require_tenant_access(request, txn.institution_id)
    detail = manual_bridge_service.get_leg_bridge_detail(db, transaction_id, leg_number)
    if not detail:
        raise HTTPException(status_code=404, detail="Manual-bridge leg not found")
    return ManualBridgeDetail(**detail)


@router.post(
    "/manual-bridge/transactions/{transaction_id}/advance",
    summary="Advance next pending manual-bridge leg",
    description=(
        "Runs Amanah against the transaction so the next pending leg generates a BSAS request "
        "(purchase → transfer → sale). Use after confirming a certificate, or to start Leg 1."
    ),
)
def advance_transaction(
    transaction_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    txn = db.get(CommodityTransaction, transaction_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    require_tenant_access(request, txn.institution_id)
    if txn.mode != TransactionMode.MANUAL_BRIDGE:
        raise HTTPException(status_code=400, detail="Transaction is not manual_bridge mode")

    worker = AmanahWorker(write_enabled=True)
    worker.process_transaction(db, txn)
    db.commit()
    return get_transaction_detail(db, transaction_id)


@router.post(
    "/manual-bridge/transactions/{transaction_id}/legs/{leg_number}/ecert-pdf",
    summary="Upload Bursa e-cert PDF",
    description="Stores the Islamic Services Receipt PDF under MANUAL_BRIDGE_INBOX_DIR/ecerts/.",
)
async def upload_ecert_pdf(
    transaction_id: str,
    leg_number: str,
    request: Request,
    file: UploadFile = File(...),
    certificate_number: str = Form(...),
    db: Session = Depends(get_db),
):
    if leg_number not in ("1", "2", "3"):
        raise HTTPException(status_code=400, detail="leg_number must be 1, 2, or 3")
    txn = db.get(CommodityTransaction, transaction_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    require_tenant_access(request, txn.institution_id)
    if txn.mode != TransactionMode.MANUAL_BRIDGE:
        raise HTTPException(status_code=400, detail="Transaction is not manual_bridge mode")

    leg = next((item for item in txn.legs if item.leg_number == leg_number), None)
    if not leg:
        raise HTTPException(status_code=404, detail="Leg not found")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty PDF upload")
    if file.content_type and "pdf" not in file.content_type.lower() and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload must be a PDF")

    stored = manual_bridge_service.store_ecert_pdf(
        external_ref=leg.external_ref,
        certificate_number=certificate_number,
        filename=file.filename or "ecert.pdf",
        content=content,
    )
    return {
        "transaction_id": transaction_id,
        "leg_number": leg_number,
        "certificate_number": certificate_number,
        **stored,
    }


@router.post(
    "/manual-bridge/transactions/{transaction_id}/legs/{leg_number}/confirm",
    summary="Confirm leg with Bursa e-cert metadata (+ optional PDF)",
    description=(
        "Multipart confirm matching the Bursa Islamic Services Receipt: certificate number, "
        "seller/buyer, product, volume, prices, and optional PDF attachment."
    ),
)
async def confirm_leg_with_ecert(
    transaction_id: str,
    leg_number: str,
    request: Request,
    db: Session = Depends(get_db),
    certificate_number: str = Form(...),
    issuer: str = Form("Bursa Malaysia Islamic Services Sdn.Bhd."),
    seller: str | None = Form(None),
    buyer: str | None = Form(None),
    bid_no: str | None = Form(None),
    selling_time: str | None = Form(None),
    selling_date: str | None = Form(None),
    value_date: str | None = Form(None),
    product_code: str | None = Form(None),
    product_description: str | None = Form(None),
    unit: str | None = Form(None),
    volume: str | None = Form(None),
    currency: str | None = Form(None),
    price: str | None = Form(None),
    price_myr_equivalent: str | None = Form(None),
    value_amount: str | None = Form(None),
    transaction_type: str | None = Form(None),
    file: UploadFile | None = File(None),
):
    from tawarruq.enums import AuditActor, LegNumber
    from tawarruq.services import transaction_service

    if leg_number not in ("1", "2", "3"):
        raise HTTPException(status_code=400, detail="leg_number must be 1, 2, or 3")
    txn = db.get(CommodityTransaction, transaction_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    require_tenant_access(request, txn.institution_id)

    fields: dict = {
        "seller": seller,
        "buyer": buyer,
        "bid_no": bid_no,
        "selling_time": selling_time,
        "selling_date": selling_date,
        "value_date": value_date,
        "product_code": product_code,
        "product_description": product_description,
        "unit": unit,
        "volume": volume,
        "currency": currency,
        "price": price,
        "price_myr_equivalent": price_myr_equivalent,
        "value_amount": value_amount,
        "transaction_type": transaction_type,
    }
    fields = {k: v for k, v in fields.items() if v is not None and str(v).strip() != ""}

    if file is not None and file.filename:
        content = await file.read()
        if content:
            leg = next((item for item in txn.legs if item.leg_number == leg_number), None)
            stored = manual_bridge_service.store_ecert_pdf(
                external_ref=leg.external_ref if leg else None,
                certificate_number=certificate_number,
                filename=file.filename,
                content=content,
            )
            fields.update(stored)

    try:
        transaction_service.confirm_manual_leg(
            db,
            transaction_id,
            LegNumber(leg_number),
            certificate_number=certificate_number,
            issuer=issuer,
            certificate_fields=fields,
            actor=AuditActor.HUMAN,
        )
        db.commit()
        return get_transaction_detail(db, transaction_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
