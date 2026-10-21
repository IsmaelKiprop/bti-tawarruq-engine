import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session, joinedload

from tawarruq.api.approval_http import queued_or_none
from tawarruq.api.deps import resolve_write_institution_id, tenant_filter_institution_id
from tawarruq.api.kenya_access import (
    bound_dealer_id,
    guarded_application,
    guarded_customer,
    guarded_dealer,
    guarded_installment,
    guarded_transaction,
    is_dealer_desk,
    kenya_write_guard,
    require_dealer_topup,
)
from tawarruq.config import get_settings
from tawarruq.database import get_db
from tawarruq.enums import AuditActor, LegStatus
from tawarruq.models.application import FinancingApplication
from tawarruq.models.customer import Customer
from tawarruq.models.institution import Institution
from tawarruq.models.disbursement import Disbursement
from tawarruq.models.kenya_flow import MurabahaContract, RepaymentInstallment, WalletDisbursement
from tawarruq.models.transaction import CommodityTransaction
from tawarruq.schemas import ApplicationRead, ErrorResponse, OfferCreate, OfferRead, TransactionRead
from tawarruq.schemas.kenya import (
    CustomerCreate,
    CustomerRead,
    CustomerUpdate,
    EligibilityDecisionRequest,
    EligibilityResultRead,
    KenyaApplicationCreate,
    KenyaDisbursementRead,
    KenyaFlowStatusRead,
    MnoTransactionCreate,
    MurabahaContractRead,
    MurabahaSignRequest,
    OfferEmailRead,
    PossessionVerifyRequest,
    WakalaConsentRequest,
    WakalaConsentRead,
    OfferSummaryRead,
    RepaymentInstallmentRead,
    ShariahAuditRead,
    ShariahIntegrityRead,
)
from tawarruq.services import application_service
from tawarruq.services.customer_service import (
    create_customer,
    delete_customer,
    link_customer_to_application,
    to_customer_read,
    update_customer,
)
from tawarruq.services.eligibility_service import record_institution_eligibility_decision, run_eligibility_check
from tawarruq.services.kenya_flow_service import (
    complete_kenya_disbursement,
    create_mno_transaction,
    execute_liquidation_leg,
    execute_mno_purchase_leg,
    execute_transfer_leg,
    prepare_murabaha_for_application,
    get_mno_transaction,
    require_possession_before_murabaha_offer,
    run_ordered_kenya_flow,
    verify_possession,
)
from tawarruq.services.business_flow_service import appoint_wakala_with_customer_consent
from tawarruq.services.callback_service import initiate_stk_repayment
from tawarruq.services.repayment_service import create_murabaha_contract, sign_murabaha_contract
from tawarruq.services.shariah_audit_service import (
    export_shariah_ledger,
    query_shariah_audit,
    query_shariah_audit_for_application,
    verify_application_shariah_integrity,
)
from tawarruq.services.shariah_ledger_service import verify_ledger_chain
from tawarruq.services.shariah_state_machine import ShariahStateViolation
from tawarruq.services.transaction_service import get_transaction_detail
from tawarruq.models.kenya_flow import AgentDealer, AgentDealerFloatTopup
from tawarruq.services.kenya_flow_service import execute_agent_dealer_purchase_leg

router = APIRouter(dependencies=[Depends(kenya_write_guard)])


def _queue(db, request, application, action: str, transaction_id: str | None = None, extra: dict | None = None):
    return queued_or_none(
        db,
        request,
        action=action,
        institution_id=application.institution_id,
        amount=application.amount_requested,
        application_id=application.id,
        transaction_id=transaction_id,
        payload=extra,
        currency=application.currency or "KES",
    )

COMMON_ERRORS = {
    400: {"model": ErrorResponse, "description": "Invalid request"},
    404: {"model": ErrorResponse, "description": "Not found"},
}


@router.get(
    "/kenya/ops/cases",
    tags=["Kenya Ops"],
    summary="Kenya ops case queue (possession, Wakala, settlement, repay)",
)
def kenya_ops_cases(
    request: Request,
    institution_id: str | None = None,
    queue: str | None = Query(None, description="active|possession|wakala|settlement|repay"),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
) -> list[dict]:
    from tawarruq.services.kenya_ops_service import list_kenya_ops_cases

    scoped = tenant_filter_institution_id(request, institution_id)
    return list_kenya_ops_cases(db, institution_id=scoped, queue=queue, limit=limit)


@router.get(
    "/kenya/ops/cases/{application_id}",
    tags=["Kenya Ops"],
    summary="Kenya ops case detail for workbench",
)
def kenya_ops_case(application_id: str, request: Request, db: Session = Depends(get_db)) -> dict:
    from tawarruq.services.kenya_ops_service import get_kenya_ops_case

    guarded_application(db, request, application_id)
    case = get_kenya_ops_case(db, application_id)
    if not case:
        raise HTTPException(status_code=404, detail="Kenya application not found")
    return case


@router.get(
    "/kenya/ops/repayments",
    tags=["Kenya Ops"],
    summary="Repayment board across Kenya Murabaha contracts",
)
def kenya_ops_repayments(
    request: Request,
    institution_id: str | None = None,
    limit: int = Query(200, le=1000),
    db: Session = Depends(get_db),
) -> list[dict]:
    from tawarruq.services.kenya_ops_service import list_repayment_board

    scoped = tenant_filter_institution_id(request, institution_id)
    return list_repayment_board(db, institution_id=scoped, limit=limit)


@router.get(
    "/kenya/ops/brokers",
    tags=["Kenya Ops"],
    summary="Third-party brokers and No-Inah eligibility",
)
def kenya_ops_brokers(db: Session = Depends(get_db)) -> list[dict]:
    from tawarruq.services.kenya_ops_service import list_brokers

    return list_brokers(db)


@router.post(
    "/kenya/customers",
    response_model=CustomerRead,
    status_code=201,
    tags=["Kenya MNO Flow"],
    summary="Kenya step 1: Register customer",
)
def register_customer(payload: CustomerCreate, request: Request, db: Session = Depends(get_db)) -> CustomerRead:
    institution_id = resolve_write_institution_id(request, payload.institution_id)
    if not institution_id:
        institution = application_service.get_or_create_default_institution(db)
        institution_id = institution.id
    try:
        customer = create_customer(
            db,
            institution_id=institution_id,
            phone=payload.phone,
            email=payload.email,
            full_name=payload.full_name,
            wallet_number=payload.wallet_number,
            national_id=payload.national_id,
            kyc_status=payload.kyc_status,
            aml_status=payload.aml_status,
            credit_score=payload.credit_score,
            wallet_provider=payload.wallet_provider,
        )
        db.commit()
        db.refresh(customer)
        return to_customer_read(customer)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/kenya/customers", response_model=list[CustomerRead], tags=["Kenya MNO Flow"])
def list_customers(
    request: Request,
    institution_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[CustomerRead]:
    scoped = tenant_filter_institution_id(request, institution_id)
    query = db.query(Customer).options(joinedload(Customer.institution)).order_by(Customer.created_at.desc())
    if scoped:
        query = query.filter(Customer.institution_id == scoped)
    return [to_customer_read(customer) for customer in query.limit(100).all()]


@router.get("/kenya/customers/{customer_id}", response_model=CustomerRead, tags=["Kenya MNO Flow"])
def get_customer(customer_id: str, request: Request, db: Session = Depends(get_db)) -> CustomerRead:
    return to_customer_read(guarded_customer(db, request, customer_id))


@router.patch("/kenya/customers/{customer_id}", response_model=CustomerRead, tags=["Kenya MNO Flow"], summary="Update customer KYC, AML, and score")
def patch_customer(
    customer_id: str,
    payload: CustomerUpdate,
    request: Request,
    db: Session = Depends(get_db),
) -> CustomerRead:
    guarded_customer(db, request, customer_id)
    try:
        customer = update_customer(db, customer_id, **payload.model_dump(exclude_unset=True))
        db.commit()
        db.refresh(customer)
        return to_customer_read(customer)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/kenya/customers/{customer_id}",
    status_code=204,
    tags=["Kenya MNO Flow"],
    summary="Delete a customer and their financing journeys",
)
def remove_customer(customer_id: str, request: Request, db: Session = Depends(get_db)) -> None:
    customer = guarded_customer(db, request, customer_id)
    try:
        delete_customer(db, customer)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/kenya/applications",
    response_model=ApplicationRead,
    status_code=201,
    tags=["Kenya MNO Flow"],
    summary="Kenya step 1: Financing request with linked customer",
)
def create_kenya_application(
    payload: KenyaApplicationCreate, request: Request, db: Session = Depends(get_db)
) -> ApplicationRead:
    customer = guarded_customer(db, request, payload.customer_id)
    try:
        from tawarruq.services.mobile_onboarding_service import assert_within_available_limit

        assert_within_available_limit(
            db, customer_id=customer.id, amount=payload.amount_requested
        )
        application = application_service.create_application(
            db,
            amount_requested=payload.amount_requested,
            term_months=payload.term_months,
            purpose=payload.purpose,
            institution_id=customer.institution_id,
            customer_name=customer.full_name,
        )
        link_customer_to_application(db, application.id, customer.id)
        db.commit()
        db.refresh(application)
        return application_service.to_application_read(application)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/kenya/applications/{application_id}/eligibility",
    response_model=EligibilityResultRead,
    tags=["Kenya MNO Flow"],
    summary="Kenya step 1: Eligibility (KYC, AML, credit, pool)",
)
def check_eligibility(application_id: str, request: Request, db: Session = Depends(get_db)) -> EligibilityResultRead:
    guarded_application(db, request, application_id)
    try:
        application = run_eligibility_check(db, application_id)
        db.commit()
        return EligibilityResultRead(
            application_id=application.id,
            status=application.status,
            eligibility_passed=application.eligibility_passed,
            message="Eligibility passed" if application.eligibility_passed else "Eligibility failed",
            source="engine",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/kenya/applications/{application_id}/eligibility/decision",
    response_model=EligibilityResultRead,
    tags=["Kenya MNO Flow"],
    summary="Kenya step 1: Record bank or SACCO eligibility decision",
)
def record_eligibility_decision(
    application_id: str,
    payload: EligibilityDecisionRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> EligibilityResultRead:
    guarded_application(db, request, application_id)
    try:
        application = record_institution_eligibility_decision(
            db,
            application_id,
            passed=payload.passed,
            kyc_status=payload.kyc_status,
            aml_status=payload.aml_status,
            credit_score=payload.credit_score,
            decision_ref=payload.decision_ref,
            notes=payload.notes,
        )
        db.commit()
        return EligibilityResultRead(
            application_id=application.id,
            status=application.status,
            eligibility_passed=application.eligibility_passed,
            message="Eligibility passed" if application.eligibility_passed else "Eligibility failed",
            source="institution",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/kenya/applications/{application_id}/offer",
    response_model=OfferRead,
    status_code=201,
    tags=["Kenya MNO Flow"],
    summary="Kenya step 4: Generate Murabaha offer (after step 3 possession)",
    description=(
        "Blocked until Leg 1 is confirmed and constructive possession is sealed. "
        "Step 4 cannot start before step 3."
    ),
)
def kenya_generate_offer(
    application_id: str,
    request: Request,
    payload: OfferCreate | None = None,
    db: Session = Depends(get_db),
) -> OfferRead:
    application = guarded_application(db, request, application_id)
    if application.eligibility_passed is not True:
        raise HTTPException(status_code=400, detail="Eligibility must pass before offer")
    try:
        require_possession_before_murabaha_offer(db, application_id)
        offer_kwargs = {}
        if payload:
            if payload.cost_price is not None:
                offer_kwargs["cost_price"] = payload.cost_price
            offer_kwargs["profit_rate_pct"] = payload.profit_rate_pct
        offer = application_service.create_offer(db, application_id, **offer_kwargs)
        db.commit()
        db.refresh(offer)
        return offer
    except ShariahStateViolation as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/kenya/applications/{application_id}/offer-email",
    response_model=OfferEmailRead,
    tags=["Kenya MNO Flow"],
    summary="Resend the Murabaha accept email to the customer",
)
def kenya_resend_offer_email(
    application_id: str,
    request: Request,
    db: Session = Depends(get_db),
) -> OfferEmailRead:
    application = guarded_application(db, request, application_id)
    if not application.offer:
        raise HTTPException(status_code=400, detail="Lock the Murabaha offer first.")
    from tawarruq.services.customer_notify_service import notify_offer_ready

    result = notify_offer_ready(db, application)
    db.commit()
    return OfferEmailRead(
        status=result.status,
        email=result.email,
        journey_url=result.journey_url,
        smtp_sent=result.smtp_sent,
        mail_path=result.mail_path,
        reason=result.reason,
    )


@router.post("/kenya/applications/{application_id}/accept", response_model=OfferRead, tags=["Kenya MNO Flow"], summary="Kenya step 4: Accept Murabaha offer")
def kenya_accept_offer(application_id: str, request: Request, db: Session = Depends(get_db)) -> OfferRead:
    application = guarded_application(db, request, application_id)
    queued = _queue(db, request, application, "kenya.accept_offer")
    if queued:
        return queued  # type: ignore[return-value]
    try:
        offer = application_service.accept_offer(db, application_id)
        db.commit()
        db.refresh(offer)
        return offer
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/kenya/transactions",
    response_model=TransactionRead,
    status_code=201,
    tags=["Kenya MNO Flow"],
    summary="Kenya step 2: Start float commodity transaction (MNO or Agent Dealer)",
)
def start_mno_transaction(payload: MnoTransactionCreate, request: Request, db: Session = Depends(get_db)) -> TransactionRead:
    guarded_application(db, request, payload.application_id)
    try:
        transaction = create_mno_transaction(
            db,
            application_id=payload.application_id,
            commodity_code=payload.commodity_code,
            mode=payload.mode,
        )
        db.commit()
        detail = get_transaction_detail(db, transaction.id)
        return detail  # type: ignore[return-value]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/kenya/transactions/{transaction_id}/purchase",
    response_model=TransactionRead,
    tags=["Kenya MNO Flow"],
    summary="Kenya step 2: Execute Leg 1 float purchase (MNO path)",
)
def mno_purchase(transaction_id: str, request: Request, db: Session = Depends(get_db)) -> TransactionRead:
    guarded_transaction(db, request, transaction_id)
    try:
        execute_mno_purchase_leg(db, transaction_id)
        db.commit()
        detail = get_transaction_detail(db, transaction_id)
        return detail  # type: ignore[return-value]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/kenya/transactions/{transaction_id}/possession",
    response_model=TransactionRead,
    tags=["Kenya MNO Flow"],
    summary="Kenya step 3: Verify constructive possession",
)
def mno_possession(
    transaction_id: str,
    payload: PossessionVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TransactionRead:
    guarded_transaction(db, request, transaction_id)
    try:
        verify_possession(db, transaction_id, batch_id=payload.batch_id, mno_receipt_id=payload.mno_receipt_id)
        db.commit()
        detail = get_transaction_detail(db, transaction_id)
        return detail  # type: ignore[return-value]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/kenya/applications/{application_id}/offer",
    response_model=OfferSummaryRead,
    tags=["Kenya MNO Flow"],
    summary="Kenya step 4: Murabaha offer summary (customer review)",
)
def get_kenya_offer(application_id: str, request: Request, db: Session = Depends(get_db)) -> OfferSummaryRead:
    """Returns cost price, profit, total payable, and installment count after offer is generated."""
    application = guarded_application(db, request, application_id)
    if not application.offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    offer = application.offer
    return OfferSummaryRead(
        application_id=application.id,
        cost_price=offer.cost_price,
        profit_amount=offer.profit_amount,
        total_payable=offer.total_payable,
        installment_count=application.term_months,
        accepted=bool(offer.accepted_at),
    )


@router.post(
    "/kenya/applications/{application_id}/wakala",
    response_model=WakalaConsentRead,
    status_code=201,
    tags=["Kenya MNO Flow"],
    summary="Kenya step 5: Customer Wakala consent (required before step 6)",
    description=(
        "Customer appoints the platform as agent (Wakala) to sell float to an independent third-party broker. "
        "Requires step 4 complete (Murabaha signed and Leg 2 transferred). Logs `WAKALA_APPOINTMENT`."
    ),
)
def appoint_wakala(
    application_id: str,
    payload: WakalaConsentRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> WakalaConsentRead:
    guarded_application(db, request, application_id)
    try:
        agency = appoint_wakala_with_customer_consent(
            db,
            application_id,
            consent_ref=payload.consent_ref,
            notes=payload.notes,
            actor=AuditActor.HUMAN,
        )
        db.commit()
        db.refresh(agency)
        return agency
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/kenya/applications/{application_id}/complete-settlement",
    response_model=KenyaDisbursementRead,
    tags=["Kenya MNO Flow"],
    summary="Kenya steps 6 to 8: Liquidate, clear, disburse, and schedule repayments",
    description=(
        "After step 5 Wakala: executes No-Inah liquidation (step 6), clearing (step 7), "
        "wallet credit and installment schedule (step 8). Requires prior `POST .../wakala`."
    ),
)
def complete_settlement(application_id: str, request: Request, db: Session = Depends(get_db)) -> KenyaDisbursementRead:
    application = guarded_application(db, request, application_id)
    queued = _queue(db, request, application, "kenya.complete_settlement")
    if queued:
        return queued  # type: ignore[return-value]
    """After Wakala consent: liquidate, wallet credit, and schedule repayments."""
    txn = get_mno_transaction(db, application_id)
    if not txn:
        raise HTTPException(status_code=404, detail="MNO transaction not found")
    try:
        transfer = next((leg for leg in txn.legs if leg.leg_number == "2"), None)
        if transfer and transfer.status == "pending":
            execute_transfer_leg(db, txn.id)
        execute_liquidation_leg(db, txn.id)
        result = complete_kenya_disbursement(db, application_id=application_id, transaction_id=txn.id)
        db.commit()
        return KenyaDisbursementRead(**result)
    except (ShariahStateViolation, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/kenya/applications/{application_id}/murabaha",
    response_model=MurabahaContractRead,
    status_code=201,
    tags=["Kenya MNO Flow"],
    summary="Kenya step 4: Create Murabaha contract",
    description="Generates cost-plus Murabaha contract from accepted offer. Logs `MURABAHA_OFFER` to Shariah audit.",
)
def create_murabaha(application_id: str, request: Request, db: Session = Depends(get_db)) -> MurabahaContractRead:
    application = guarded_application(db, request, application_id)
    queued = _queue(db, request, application, "kenya.create_murabaha")
    if queued:
        return queued  # type: ignore[return-value]
    try:
        contract = create_murabaha_contract(db, application_id)
        db.commit()
        db.refresh(contract)
        return contract
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/kenya/applications/{application_id}/murabaha/sign",
    response_model=MurabahaContractRead,
    tags=["Kenya MNO Flow"],
    summary="Kenya step 4: Customer digital signature",
    description="Customer accepts the Murabaha contract. Required before Leg 2 ownership transfer.",
)
def sign_murabaha(
    application_id: str,
    payload: MurabahaSignRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> MurabahaContractRead:
    guarded_application(db, request, application_id)
    try:
        contract = sign_murabaha_contract(db, application_id, signature_ref=payload.signature_ref)
        db.commit()
        db.refresh(contract)
        return contract
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/kenya/transactions/{transaction_id}/transfer",
    response_model=TransactionRead,
    tags=["Kenya MNO Flow"],
    summary="Kenya step 4: Ownership transfer, Leg 2 (financier to customer)",
    description="Transfers title of airtime/float batch to customer. Logs `OWNERSHIP_TRANSFER` to Shariah audit.",
)
def mno_transfer(transaction_id: str, request: Request, db: Session = Depends(get_db)) -> TransactionRead:
    guarded_transaction(db, request, transaction_id)
    try:
        execute_transfer_leg(db, transaction_id)
        db.commit()
        detail = get_transaction_detail(db, transaction_id)
        return detail  # type: ignore[return-value]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/kenya/transactions/{transaction_id}/liquidate",
    response_model=TransactionRead,
    tags=["Kenya MNO Flow"],
    summary="Kenya step 6: Third-party liquidation, Leg 3 (No-Inah enforced)",
    description=(
        "Routes sale through independent OTC broker. Blocked if broker is financier or originating MNO pool. "
        "Requires Wakala consent (`POST .../wakala`). Logs `THIRD_PARTY_LIQUIDATION`."
    ),
)
def mno_liquidate(transaction_id: str, request: Request, db: Session = Depends(get_db)) -> TransactionRead:
    txn = guarded_transaction(db, request, transaction_id)
    application = db.get(FinancingApplication, txn.application_id) if txn.application_id else None
    if application:
        queued = _queue(db, request, application, "kenya.liquidate", transaction_id=txn.id, extra={"transaction_id": txn.id})
        if queued:
            return queued  # type: ignore[return-value]
    try:
        execute_liquidation_leg(db, transaction_id)
        db.commit()
        detail = get_transaction_detail(db, transaction_id)
        return detail  # type: ignore[return-value]
    except ShariahStateViolation as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/kenya/disbursements",
    response_model=KenyaDisbursementRead,
    status_code=201,
    tags=["Kenya MNO Flow"],
    summary="Kenya step 8: Wallet disbursement and repayment schedule",
    description="Credits M-Pesa or Airtel Money wallet and creates Murabaha installment schedule.",
)
def kenya_disburse(
    request: Request,
    application_id: str = Query(...),
    transaction_id: str = Query(...),
    db: Session = Depends(get_db),
) -> KenyaDisbursementRead:
    application = guarded_application(db, request, application_id)
    guarded_transaction(db, request, transaction_id)
    queued = _queue(
        db,
        request,
        application,
        "kenya.disburse",
        transaction_id=transaction_id,
        extra={"application_id": application_id, "transaction_id": transaction_id},
    )
    if queued:
        return queued  # type: ignore[return-value]
    try:
        result = complete_kenya_disbursement(db, application_id=application_id, transaction_id=transaction_id)
        db.commit()
        return KenyaDisbursementRead(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/kenya/applications/{application_id}/repayments",
    response_model=list[RepaymentInstallmentRead],
    tags=["Kenya MNO Flow"],
    summary="Kenya step 8: Repayment schedule",
)
def list_repayments(application_id: str, request: Request, db: Session = Depends(get_db)) -> list[RepaymentInstallmentRead]:
    guarded_application(db, request, application_id)
    application = (
        db.query(FinancingApplication)
        .options(joinedload(FinancingApplication.murabaha_contract).joinedload(MurabahaContract.installments))
        .filter(FinancingApplication.id == application_id)
        .first()
    )
    if not application or not application.murabaha_contract:
        raise HTTPException(status_code=404, detail="Repayment schedule not found")
    return sorted(application.murabaha_contract.installments, key=lambda i: i.installment_number)


@router.post(
    "/kenya/repayments/{installment_id}/collect",
    response_model=RepaymentInstallmentRead,
    tags=["Kenya MNO Flow"],
    summary="Kenya step 8: Collect repayment installment",
)
def collect_installment(installment_id: str, request: Request, db: Session = Depends(get_db)) -> RepaymentInstallmentRead:
    guarded_installment(db, request, installment_id)
    try:
        installment = initiate_stk_repayment(db, installment_id)
        db.commit()
        db.refresh(installment)
        return installment
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/kenya/applications/{application_id}/status",
    response_model=KenyaFlowStatusRead,
    tags=["Kenya MNO Flow"],
    summary="Full Kenya flow status",
)
def kenya_flow_status(application_id: str, request: Request, db: Session = Depends(get_db)) -> KenyaFlowStatusRead:
    guarded_application(db, request, application_id)
    application = (
        db.query(FinancingApplication)
        .options(
            joinedload(FinancingApplication.murabaha_contract).joinedload(MurabahaContract.installments),
            joinedload(FinancingApplication.transactions),
            joinedload(FinancingApplication.customer_agency),
            joinedload(FinancingApplication.disbursements).joinedload(Disbursement.wallet_disbursement),
        )
        .filter(FinancingApplication.id == application_id)
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    txn = application.transactions[-1] if application.transactions else None
    installments = application.murabaha_contract.installments if application.murabaha_contract else []
    paid = sum(1 for i in installments if i.status == "paid")
    wallet_credited = any(
        disb.wallet_disbursement and disb.wallet_disbursement.status == "credited"
        for disb in application.disbursements
    )

    return KenyaFlowStatusRead(
        application_id=application.id,
        current_phase=application.current_phase,
        eligibility_passed=application.eligibility_passed,
        wad_accepted=bool(application.wad_accepted_at),
        offer_accepted=bool(application.offer and application.offer.accepted_at),
        murabaha_signed=bool(application.murabaha_contract and application.murabaha_contract.signed_at),
        wakala_appointed=application.customer_agency is not None,
        wallet_credited=wallet_credited,
        transaction_id=txn.id if txn else None,
        transaction_status=txn.status if txn else None,
        transaction_phase=txn.phase if txn else None,
        installments_total=len(installments),
        installments_paid=paid,
    )


@router.get(
    "/kenya/applications/{application_id}/shariah-audit",
    response_model=list[ShariahAuditRead],
    tags=["Kenya MNO Flow"],
    summary="Shariah audit trail for entire application",
)
def get_application_shariah_audit(application_id: str, request: Request, db: Session = Depends(get_db)) -> list[ShariahAuditRead]:
    guarded_application(db, request, application_id)
    return query_shariah_audit_for_application(db, application_id)


@router.get(
    "/kenya/applications/{application_id}/shariah-audit/verify",
    response_model=ShariahIntegrityRead,
    tags=["Kenya MNO Flow"],
    summary="Verify Shariah ledger integrity (hash chain + possession seal)",
)
def verify_application_shariah(application_id: str, request: Request, db: Session = Depends(get_db)) -> ShariahIntegrityRead:
    guarded_application(db, request, application_id)
    result = verify_application_shariah_integrity(db, application_id)
    if result.get("reason") == "application not found":
        raise HTTPException(status_code=404, detail="Application not found")
    return ShariahIntegrityRead(**result)


@router.get(
    "/kenya/shariah-audit/verify-chain",
    tags=["Kenya MNO Flow"],
    summary="Verify append-only hash chain for institution ledger",
)
def verify_shariah_chain(
    request: Request,
    institution_id: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    scoped = tenant_filter_institution_id(request, institution_id)
    return verify_ledger_chain(db, institution_id=scoped)


@router.get(
    "/kenya/shariah-audit/export",
    tags=["Kenya MNO Flow"],
    summary="Regulatory export — append-only Shariah ledger (JSON or CSV)",
    description="Export hash-chained audit entries for CMA/CBK review. Filter by institution_id or application_id.",
)
def export_shariah_audit(
    request: Request,
    format: str = Query("json", pattern="^(json|csv)$"),
    institution_id: str | None = None,
    application_id: str | None = None,
    limit: int = Query(10_000, le=100_000),
    db: Session = Depends(get_db),
):
    from tawarruq.api.deps import require_export_data, require_permission

    require_permission(request, "view_shariah")
    require_export_data(request)
    if application_id:
        guarded_application(db, request, application_id)
    scoped = tenant_filter_institution_id(request, institution_id)
    rows = export_shariah_ledger(
        db,
        institution_id=scoped,
        application_id=application_id,
        limit=limit,
    )
    if format == "csv":
        buffer = io.StringIO()
        if rows:
            writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return Response(
            content=buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=shariah_audit_export.csv"},
        )
    return rows


@router.get(
    "/kenya/shariah-audit",
    response_model=list[ShariahAuditRead],
    tags=["Kenya MNO Flow"],
    summary="Shariah audit trail with payload hashes",
)
def get_shariah_audit(
    entity_id: str | None = None,
    step_id: str | None = None,
    limit: int = Query(200, le=1000),
    db: Session = Depends(get_db),
) -> list[ShariahAuditRead]:
    if not entity_id and not step_id:
        raise HTTPException(status_code=400, detail="Provide entity_id or step_id")
    return query_shariah_audit(db, entity_id=entity_id, step_id=step_id, limit=limit)


@router.post(
    "/kenya/applications/{application_id}/run-full-flow",
    response_model=KenyaFlowStatusRead,
    tags=["Kenya MNO Flow"],
    summary="Demo: run complete 8-step Kenya flow (requires KENYA_INTEGRATION_MODE=mock)",
)
def run_full_kenya_flow(application_id: str, request: Request, db: Session = Depends(get_db)) -> KenyaFlowStatusRead:
    """Automates all steps synchronously — only available when KENYA_INTEGRATION_MODE=mock."""
    application = guarded_application(db, request, application_id)
    settings = get_settings()
    if settings.kenya_integration_mode != "mock":
        raise HTTPException(
            status_code=400,
            detail=(
                "run-full-flow is only for mock/integration testing. "
                "In live mode, execute each step via the Kenya MNO endpoints and configure Daraja/MNO callbacks."
            ),
        )
    queued = _queue(db, request, application, "kenya.run_full_flow")
    if queued:
        return queued  # type: ignore[return-value]
    try:
        run_ordered_kenya_flow(db, application_id)
        db.commit()
    except (ShariahStateViolation, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return kenya_flow_status(application_id, request, db)


# ─────────────────────────────────────────────────────────────
# Agent Dealer endpoints
# ─────────────────────────────────────────────────────────────


@router.get("/kenya/agent-dealers", tags=["Kenya Agent Dealers"], summary="List all M-Pesa Agent Dealers")
def list_agent_dealers(
    request: Request,
    institution_id: str | None = None,
    active_only: bool = True,
    db: Session = Depends(get_db),
) -> list[dict]:
    scoped = tenant_filter_institution_id(request, institution_id)
    q = db.query(AgentDealer)
    if scoped:
        q = q.filter((AgentDealer.institution_id == scoped) | (AgentDealer.institution_id.is_(None)))
    if is_dealer_desk(request) and bound_dealer_id(request):
        q = q.filter(AgentDealer.id == bound_dealer_id(request))
    elif active_only:
        q = q.filter(AgentDealer.active.is_(True))
    dealers = q.order_by(AgentDealer.created_at).all()
    return [
        {
            "id": d.id,
            "code": d.code,
            "business_name": d.business_name,
            "mpesa_number": d.mpesa_number,
            "mpesa_till_number": d.mpesa_till_number,
            "float_balance": float(d.float_balance),
            "institution_id": d.institution_id,
            "contact_name": d.contact_name,
            "contact_phone": d.contact_phone,
            "active": d.active,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in dealers
    ]


@router.get("/kenya/agent-dealers/summary", tags=["Kenya Agent Dealers"], summary="Get overall Agent Dealer float pool summary")
def get_agent_dealer_summary(
    request: Request,
    institution_id: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    scoped = tenant_filter_institution_id(request, institution_id)
    q = db.query(AgentDealer).filter(AgentDealer.active.is_(True))
    if scoped:
        q = q.filter((AgentDealer.institution_id == scoped) | (AgentDealer.institution_id.is_(None)))
    if is_dealer_desk(request) and bound_dealer_id(request):
        q = q.filter(AgentDealer.id == bound_dealer_id(request))
    dealers = q.all()
    total_float = sum(float(d.float_balance) for d in dealers)
    return {
        "total_active_dealers": len(dealers),
        "total_float_balance": total_float,
        "health": "green" if total_float >= 100000 else ("amber" if total_float >= 20000 else "red"),
        "primary_dealer": {
            "id": dealers[0].id,
            "code": dealers[0].code,
            "business_name": dealers[0].business_name,
            "float_balance": float(dealers[0].float_balance),
            "mpesa_till_number": dealers[0].mpesa_till_number,
        } if dealers else None,
    }


@router.post("/kenya/agent-dealers", tags=["Kenya Agent Dealers"], summary="Register a new M-Pesa Agent Dealer", status_code=201)
def create_agent_dealer(
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    import uuid
    code = body.get("code") or f"DEALER-{uuid.uuid4().hex[:6].upper()}"
    existing = db.query(AgentDealer).filter(AgentDealer.code == code).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Dealer with code '{code}' already exists")
    dealer = AgentDealer(
        code=code,
        business_name=body["business_name"],
        mpesa_number=body["mpesa_number"],
        mpesa_till_number=body.get("mpesa_till_number"),
        float_balance=0,
        institution_id=None,
        contact_name=body.get("contact_name"),
        contact_phone=body.get("contact_phone"),
    )
    db.add(dealer)
    db.flush()
    db.commit()
    db.refresh(dealer)
    return {"id": dealer.id, "code": dealer.code, "business_name": dealer.business_name, "float_balance": float(dealer.float_balance)}


def _float_history_rows(topups: list, *, dealer_view: bool) -> list[dict]:
    rows = []
    for t in topups:
        amount = float(t.amount)
        rows.append(
            {
                "id": t.id,
                "amount": amount,
                "kind": "draw" if amount < 0 else "topup",
                "reference": t.reference,
                "note": None if dealer_view else t.note,
                "added_by": None if dealer_view else t.added_by,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
        )
    return rows


@router.get("/kenya/agent-dealers/me", tags=["Kenya Agent Dealers"], summary="Current dealer desk")
def get_my_agent_dealer(request: Request, db: Session = Depends(get_db)) -> dict:
    dealer_id = bound_dealer_id(request)
    if not dealer_id:
        raise HTTPException(status_code=403, detail="This login is not bound to an Agent Dealer")
    return get_agent_dealer(dealer_id, request, db)


@router.get("/kenya/agent-dealers/{dealer_id}", tags=["Kenya Agent Dealers"], summary="Get dealer detail + float history")
def get_agent_dealer(dealer_id: str, request: Request, db: Session = Depends(get_db)) -> dict:
    dealer = guarded_dealer(db, request, dealer_id)
    topups = db.query(AgentDealerFloatTopup).filter(AgentDealerFloatTopup.dealer_id == dealer_id).order_by(AgentDealerFloatTopup.created_at.desc()).limit(50).all()
    return {
        "id": dealer.id,
        "code": dealer.code,
        "business_name": dealer.business_name,
        "mpesa_number": dealer.mpesa_number,
        "mpesa_till_number": dealer.mpesa_till_number,
        "float_balance": float(dealer.float_balance),
        "institution_id": dealer.institution_id,
        "contact_name": dealer.contact_name,
        "contact_phone": dealer.contact_phone,
        "active": dealer.active,
        "created_at": dealer.created_at.isoformat() if dealer.created_at else None,
        "float_history": _float_history_rows(topups, dealer_view=is_dealer_desk(request)),
    }


@router.post("/kenya/agent-dealers/{dealer_id}/topup", tags=["Kenya Agent Dealers"], summary="Add float to a dealer's pool")
def topup_agent_dealer(
    dealer_id: str,
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    dealer = guarded_dealer(db, request, dealer_id)
    require_dealer_topup(request, dealer.id)
    amount = float(body.get("amount", 0))
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Top-up amount must be positive")
    dealer.float_balance = float(dealer.float_balance) + amount
    added_by = getattr(request.state, "ops_user_id", None) or body.get("added_by") or "dealer"
    db.add(AgentDealerFloatTopup(
        dealer_id=dealer.id,
        amount=amount,
        reference=body.get("reference"),
        note=body.get("note"),
        added_by=added_by,
    ))
    db.commit()
    db.refresh(dealer)
    return {"id": dealer.id, "float_balance": float(dealer.float_balance), "message": f"KES {amount:,.2f} added successfully"}


def _optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    return raw or None


@router.patch("/kenya/agent-dealers/{dealer_id}", tags=["Kenya Agent Dealers"], summary="Update dealer details")
def update_agent_dealer(dealer_id: str, body: dict, request: Request, db: Session = Depends(get_db)) -> dict:
    dealer = guarded_dealer(db, request, dealer_id)
    dealer_view = is_dealer_desk(request)
    if "active" in body:
        if dealer_view:
            raise HTTPException(status_code=403, detail="The dealer cannot activate or deactivate this desk.")
        dealer.active = bool(body["active"])
    if "business_name" in body:
        name = _optional_text(body["business_name"])
        if not name:
            raise HTTPException(status_code=400, detail="Business name is required.")
        dealer.business_name = name
    if "mpesa_number" in body:
        number = _optional_text(body["mpesa_number"])
        if not number:
            raise HTTPException(status_code=400, detail="M-Pesa number is required.")
        dealer.mpesa_number = number
    if "mpesa_till_number" in body:
        dealer.mpesa_till_number = _optional_text(body["mpesa_till_number"])
    if "contact_name" in body:
        dealer.contact_name = _optional_text(body["contact_name"])
    if "contact_phone" in body:
        dealer.contact_phone = _optional_text(body["contact_phone"])
    db.commit()
    db.refresh(dealer)
    return {
        "id": dealer.id,
        "code": dealer.code,
        "business_name": dealer.business_name,
        "mpesa_number": dealer.mpesa_number,
        "mpesa_till_number": dealer.mpesa_till_number,
        "contact_name": dealer.contact_name,
        "contact_phone": dealer.contact_phone,
        "active": dealer.active,
        "message": "Dealer updated",
    }


@router.post(
    "/kenya/transactions/{transaction_id}/agent-dealer-purchase",
    tags=["Kenya Agent Dealers"],
    summary="Kenya step 2: Execute Leg 1 via Agent Dealer float pool",
)
def agent_dealer_purchase(transaction_id: str, request: Request, db: Session = Depends(get_db)) -> dict:
    guarded_transaction(db, request, transaction_id)
    """Deducts the purchase amount from the dealer's float balance and confirms possession."""
    try:
        txn = execute_agent_dealer_purchase_leg(db, transaction_id)
        db.commit()
        return {"transaction_id": txn.id, "status": txn.status, "message": "Agent Dealer purchase executed and possession confirmed"}
    except (ValueError, ShariahStateViolation) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
