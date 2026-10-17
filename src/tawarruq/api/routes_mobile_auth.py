"""Buruuj Lend mobile email authentication (high security)."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from tawarruq.database import get_db
from tawarruq.models.mobile_account import MobileAccount
from tawarruq.schemas.mobile_auth import (
    MobileAccountRead,
    MobileAuthDelivery,
    MobileChangePasswordRequest,
    MobileClaimInviteRequest,
    MobileForgotPasswordRequest,
    MobileKycSubmitRequest,
    MobileLoginChallengeResponse,
    MobileLoginRequest,
    MobileMfaVerifyRequest,
    MobileProfileRequest,
    MobilePushTokenRequest,
    MobileRefreshRequest,
    MobileRegisterRequest,
    MobileRegisterResponse,
    MobileResendVerificationRequest,
    MobileResetPasswordRequest,
    MobileTokenResponse,
    MobileVerifyEmailRequest,
)
from tawarruq.services import mobile_auth_service as auth
from tawarruq.services import mobile_inbox_service as inbox
from tawarruq.services import mobile_onboarding_service as onboarding
from tawarruq.services.customer_service import to_customer_read

router = APIRouter(prefix="/mobile/auth", tags=["Mobile Auth"])


def _require_mobile_account(request: Request, db: Session) -> MobileAccount:
    account_id = getattr(request.state, "mobile_account_id", None)
    if not account_id:
        raise HTTPException(status_code=401, detail="Sign in required")
    account = db.get(MobileAccount, account_id)
    if not account or not account.active:
        raise HTTPException(status_code=401, detail="Account inactive or missing")
    return account


def _account_read(db: Session, account: MobileAccount) -> MobileAccountRead:
    return MobileAccountRead(**onboarding.enrich_account_public(account, db))


@router.post("/register", response_model=MobileRegisterResponse, status_code=201)
def register(payload: MobileRegisterRequest, db: Session = Depends(get_db)) -> MobileRegisterResponse:
    try:
        account, delivery = auth.register_account(
            db,
            email=str(payload.email),
            password=payload.password,
            full_name=payload.full_name,
        )
        db.commit()
        return MobileRegisterResponse(
            email=account.email,
            message="Account created. Verify email, then wait for institution approval (or claim an invite).",
            smtp_sent=delivery.get("smtp_sent", False),
            mail_path=delivery.get("mail_path"),
            dev_code=delivery.get("dev_code"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/verify-email", response_model=MobileAccountRead)
def verify_email(payload: MobileVerifyEmailRequest, db: Session = Depends(get_db)) -> MobileAccountRead:
    try:
        account = auth.verify_email(db, email=str(payload.email), code=payload.code)
        db.commit()
        return _account_read(db, account)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/resend-verification", response_model=MobileAuthDelivery)
def resend_verification(
    payload: MobileResendVerificationRequest, db: Session = Depends(get_db)
) -> MobileAuthDelivery:
    delivery = auth.resend_verification(db, str(payload.email))
    db.commit()
    return MobileAuthDelivery(
        smtp_sent=delivery.get("smtp_sent", False),
        mail_path=delivery.get("mail_path"),
        dev_code=delivery.get("dev_code"),
        status=delivery.get("status"),
    )


@router.post("/login", response_model=MobileLoginChallengeResponse)
def login(payload: MobileLoginRequest, db: Session = Depends(get_db)) -> MobileLoginChallengeResponse:
    try:
        result = auth.begin_login(db, email=str(payload.email), password=payload.password)
        db.commit()
        return MobileLoginChallengeResponse(**result)
    except ValueError as exc:
        db.commit()
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/mfa", response_model=MobileTokenResponse)
def verify_mfa(payload: MobileMfaVerifyRequest, db: Session = Depends(get_db)) -> MobileTokenResponse:
    try:
        result = auth.complete_login_mfa(db, mfa_token=payload.mfa_token, code=payload.code)
        account = db.get(MobileAccount, result["account"]["id"])
        db.commit()
        return MobileTokenResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            expires_in=result["expires_in"],
            account=_account_read(db, account) if account else MobileAccountRead(**result["account"]),
        )
    except ValueError as exc:
        db.commit()
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/refresh", response_model=MobileTokenResponse)
def refresh(payload: MobileRefreshRequest, db: Session = Depends(get_db)) -> MobileTokenResponse:
    try:
        result = auth.refresh_session(db, refresh_token=payload.refresh_token)
        account = db.get(MobileAccount, result["account"]["id"])
        db.commit()
        return MobileTokenResponse(
            access_token=result["access_token"],
            refresh_token=result["refresh_token"],
            expires_in=result["expires_in"],
            account=_account_read(db, account) if account else MobileAccountRead(**result["account"]),
        )
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)) -> None:
    account = _require_mobile_account(request, db)
    auth.logout(db, account)
    db.commit()


@router.get("/me", response_model=MobileAccountRead)
def me(request: Request, db: Session = Depends(get_db)) -> MobileAccountRead:
    account = _require_mobile_account(request, db)
    read = _account_read(db, account)
    db.commit()
    return read


@router.get("/facilities")
def list_facilities(request: Request, db: Session = Depends(get_db)):
    """Live facility history for the signed-in mobile customer."""
    account = _require_mobile_account(request, db)
    if not account.customer_id:
        return []
    rows = onboarding.list_customer_facilities(db, account.customer_id)
    db.commit()  # persist any auto-completed statuses from snapshot
    return rows


@router.post("/claim-invite", response_model=MobileAccountRead)
def claim_invite(
    payload: MobileClaimInviteRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> MobileAccountRead:
    account = _require_mobile_account(request, db)
    try:
        account = onboarding.claim_invite(db, account, payload.invite_code)
        db.commit()
        db.refresh(account)
        return _account_read(db, account)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/profile")
def complete_profile(
    payload: MobileProfileRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    account = _require_mobile_account(request, db)
    try:
        customer = auth.ensure_customer_profile(
            db,
            account,
            phone=payload.phone,
            wallet_provider=payload.wallet_provider,
            wallet_number=payload.wallet_number,
        )
        db.commit()
        db.refresh(account)
        return {
            "account": onboarding.enrich_account_public(account, db),
            "customer": to_customer_read(customer) if customer else None,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/forgot-password", response_model=MobileAuthDelivery)
def forgot_password(
    payload: MobileForgotPasswordRequest, db: Session = Depends(get_db)
) -> MobileAuthDelivery:
    delivery = auth.request_password_reset(db, str(payload.email))
    db.commit()
    return MobileAuthDelivery(
        smtp_sent=delivery.get("smtp_sent", False),
        mail_path=delivery.get("mail_path"),
        dev_code=delivery.get("dev_code"),
        status=delivery.get("status") or "accepted",
    )


@router.post("/reset-password", status_code=204)
def reset_password(payload: MobileResetPasswordRequest, db: Session = Depends(get_db)) -> None:
    try:
        auth.reset_password(
            db,
            email=str(payload.email),
            code=payload.code,
            new_password=payload.new_password,
        )
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/change-password", status_code=204)
def change_password(
    payload: MobileChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> None:
    account = _require_mobile_account(request, db)
    try:
        auth.change_password(
            db,
            account,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/notifications")
def list_notifications(request: Request, db: Session = Depends(get_db)):
    account = _require_mobile_account(request, db)
    return inbox.list_notifications(db, account.id)


@router.post("/notifications/read")
def mark_notifications_read(
    request: Request,
    db: Session = Depends(get_db),
    notification_id: str | None = Query(None),
):
    account = _require_mobile_account(request, db)
    count = inbox.mark_read(db, account.id, notification_id)
    db.commit()
    return {"marked": count, "unread": inbox.unread_count(db, account.id)}


@router.post("/push-token", response_model=MobileAccountRead)
def save_push_token(
    payload: MobilePushTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> MobileAccountRead:
    account = _require_mobile_account(request, db)
    account.push_token = payload.push_token.strip()
    db.commit()
    db.refresh(account)
    return _account_read(db, account)


@router.post("/kyc", response_model=MobileAccountRead)
def submit_kyc(
    payload: MobileKycSubmitRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> MobileAccountRead:
    """Capture national ID + optional document/selfie images (base64)."""
    from datetime import UTC, datetime
    from pathlib import Path

    from tawarruq.enums import KycStatus
    from tawarruq.models.customer import Customer

    account = _require_mobile_account(request, db)
    if not account.customer_id:
        raise HTTPException(status_code=400, detail="Complete profile and get institution approval first")
    customer = db.get(Customer, account.customer_id)
    if not customer:
        raise HTTPException(status_code=400, detail="Customer profile missing")

    root = Path("data/kyc") / customer.id
    root.mkdir(parents=True, exist_ok=True)

    def _save(b64: str | None, name: str) -> str | None:
        if not b64:
            return None
        raw = b64.split(",", 1)[-1]
        import base64

        path = root / name
        path.write_bytes(base64.b64decode(raw))
        return str(path)

    customer.national_id = payload.national_id.strip()
    customer.id_document_path = _save(payload.id_document_b64, "id.bin") or customer.id_document_path
    customer.selfie_path = _save(payload.selfie_b64, "selfie.bin") or customer.selfie_path
    customer.kyc_submitted_at = datetime.now(UTC)
    # Demo path: auto-verify after capture (ops can still override via Kenya customer PATCH).
    customer.kyc_status = KycStatus.VERIFIED
    inbox.push_notification(
        db,
        account,
        kind="kyc",
        title="Identity verified",
        body="Your national ID details were received and marked verified.",
    )
    db.commit()
    db.refresh(account)
    return _account_read(db, account)


@router.get("/applications/{application_id}/documents")
def list_facility_documents(application_id: str, request: Request, db: Session = Depends(get_db)):
    from tawarruq.services import mobile_docs_service

    account = _require_mobile_account(request, db)
    application = _assert_owns_application(db, account, application_id)
    docs = mobile_docs_service.list_mobile_documents(db, application)
    return {"application_id": application_id, "documents": docs}


@router.get("/applications/{application_id}/documents/{kind}")
def get_facility_document_html(
    application_id: str,
    kind: str,
    request: Request,
    db: Session = Depends(get_db),
):
    from fastapi.responses import Response

    from tawarruq.services import mobile_docs_service

    account = _require_mobile_account(request, db)
    application = _assert_owns_application(db, account, application_id)
    try:
        html, filename = mobile_docs_service.render_mobile_document_html(db, application, kind)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(
        content=html,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/applications/{application_id}/statement")
def facility_statement(application_id: str, request: Request, db: Session = Depends(get_db)):
    account = _require_mobile_account(request, db)
    application = _assert_owns_application(db, account, application_id)
    from decimal import Decimal

    from tawarruq.enums import InstallmentStatus
    from tawarruq.models.kenya_flow import MurabahaContract, RepaymentInstallment
    from tawarruq.models.institution import Institution

    contract = (
        db.query(MurabahaContract).filter(MurabahaContract.application_id == application_id).first()
    )
    installments = []
    if contract:
        installments = (
            db.query(RepaymentInstallment)
            .filter(RepaymentInstallment.contract_id == contract.id)
            .order_by(RepaymentInstallment.installment_number)
            .all()
        )
    paid = sum(1 for i in installments if i.status == InstallmentStatus.PAID.value)
    outstanding = sum(
        (Decimal(str(i.amount)) for i in installments if i.status != InstallmentStatus.PAID.value),
        Decimal("0"),
    )
    institution = db.get(Institution, application.institution_id)
    return {
        "application_id": application_id,
        "amount": str(application.amount_requested),
        "status": application.status,
        "institution_name": institution.name if institution else None,
        "installments_paid": paid,
        "installments_total": len(installments),
        "outstanding": str(outstanding),
        "installments": [
            {
                "number": i.installment_number,
                "amount": str(i.amount),
                "status": i.status,
                "due_date": i.due_date.isoformat() if i.due_date else None,
                "paid_at": i.paid_at.isoformat() if i.paid_at else None,
                "payment_ref": i.payment_ref,
            }
            for i in installments
        ],
    }


def _assert_owns_application(db: Session, account, application_id: str):
    from tawarruq.models.application import FinancingApplication

    application = db.get(FinancingApplication, application_id)
    if not application or application.customer_id != account.customer_id:
        raise HTTPException(status_code=404, detail="Facility not found")
    return application
