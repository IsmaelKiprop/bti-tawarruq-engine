"""Tenant and write guards for Kenya routes."""

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from tawarruq.api.deps import require_tenant_access, require_write_ops
from tawarruq.database import SessionLocal
from tawarruq.enums import ApiKeyRole
from tawarruq.models.application import FinancingApplication
from tawarruq.models.customer import Customer
from tawarruq.models.kenya_flow import AgentDealer, RepaymentInstallment
from tawarruq.models.mobile_account import MobileAccount
from tawarruq.models.transaction import CommodityTransaction
from tawarruq.services.mobile_onboarding_service import can_borrow as mobile_can_borrow
from tawarruq.services.rbac import auth_is_enabled, get_request_role, require_permission

READ_METHODS = {"GET", "HEAD", "OPTIONS"}

# Paths mobile borrowers may write (self-service journey). Ops / dealer admin stay blocked.
_MOBILE_KENYA_WRITE_PREFIXES = (
    "/api/v1/kenya/customers",
    "/api/v1/kenya/applications",
    "/api/v1/kenya/transactions",
    "/api/v1/kenya/disbursements",
    "/api/v1/kenya/repayments",
)


def bound_dealer_id(request: Request) -> str | None:
    return getattr(request.state, "agent_dealer_id", None)


def is_dealer_desk(request: Request) -> bool:
    return get_request_role(request) == ApiKeyRole.AGENT_DEALER


def is_mobile_session(request: Request) -> bool:
    return bool(getattr(request.state, "mobile_account_id", None)) or getattr(request.state, "auth_method", None) == "mobile"


def _mobile_kenya_write_allowed(path: str) -> bool:
    if "/kenya/ops" in path:
        return False
    if "/kenya/agent-dealers" in path:
        return False
    return any(path == prefix or path.startswith(prefix + "/") for prefix in _MOBILE_KENYA_WRITE_PREFIXES)


def _require_mobile_can_borrow(request: Request) -> None:
    account_id = getattr(request.state, "mobile_account_id", None)
    if not account_id:
        raise HTTPException(status_code=401, detail="Mobile session required")
    db = SessionLocal()
    try:
        account = db.get(MobileAccount, account_id)
        if not account or not mobile_can_borrow(account, db):
            raise HTTPException(
                status_code=403,
                detail="Institution approval required before financing",
            )
    finally:
        db.close()


def kenya_write_guard(request: Request) -> None:
    if request.method in READ_METHODS:
        return
    path = request.url.path.rstrip("/")
    if "/kenya/agent-dealers/" in path and (
        path.endswith("/topup") or (request.method == "PATCH" and is_dealer_desk(request))
    ):
        return

    if is_mobile_session(request):
        if not _mobile_kenya_write_allowed(path):
            raise HTTPException(status_code=403, detail="Mobile session cannot access this Kenya resource")
        _require_mobile_can_borrow(request)
        return

    require_write_ops(request)


def require_own_dealer(request: Request, dealer_id: str) -> None:
    if not auth_is_enabled(request) or not is_dealer_desk(request):
        return
    bound = bound_dealer_id(request)
    if not bound or bound != dealer_id:
        raise HTTPException(status_code=403, detail="Access denied for this dealer")


def require_dealer_topup(request: Request, dealer_id: str) -> None:
    require_permission(request, "dealer_desk")
    if not auth_is_enabled(request):
        return
    bound = bound_dealer_id(request)
    if not bound or bound != dealer_id:
        raise HTTPException(
            status_code=403,
            detail="Only this dealer's login can add float. Institution and platform ops cannot top up.",
        )


def require_mobile_owns_customer(request: Request, customer_id: str) -> None:
    if not is_mobile_session(request):
        return
    bound = getattr(request.state, "customer_id", None)
    if not bound or bound != customer_id:
        raise HTTPException(status_code=403, detail="Mobile session can only use its own customer profile")


def require_mobile_owns_application(db: Session, request: Request, application: FinancingApplication) -> None:
    if not is_mobile_session(request):
        return
    bound = getattr(request.state, "customer_id", None)
    if not bound or application.customer_id != bound:
        raise HTTPException(status_code=403, detail="Mobile session can only access its own applications")


def guarded_application(db: Session, request: Request, application_id: str) -> FinancingApplication:
    application = db.get(FinancingApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    require_tenant_access(request, application.institution_id)
    require_mobile_owns_application(db, request, application)
    return application


def guarded_customer(db: Session, request: Request, customer_id: str) -> Customer:
    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    require_tenant_access(request, customer.institution_id)
    require_mobile_owns_customer(request, customer_id)
    return customer


def guarded_transaction(db: Session, request: Request, transaction_id: str) -> CommodityTransaction:
    txn = db.get(CommodityTransaction, transaction_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    require_tenant_access(request, txn.institution_id)
    if is_mobile_session(request) and txn.application_id:
        application = db.get(FinancingApplication, txn.application_id)
        if application:
            require_mobile_owns_application(db, request, application)
    return txn


def guarded_dealer(db: Session, request: Request, dealer_id: str) -> AgentDealer:
    dealer = db.query(AgentDealer).filter(AgentDealer.id == dealer_id).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="Dealer not found")
    if dealer.institution_id:
        require_tenant_access(request, dealer.institution_id)
    require_own_dealer(request, dealer.id)
    return dealer


def guarded_installment(db: Session, request: Request, installment_id: str) -> RepaymentInstallment:
    installment = db.get(RepaymentInstallment, installment_id)
    if not installment:
        raise HTTPException(status_code=404, detail="Installment not found")
    contract = installment.contract
    application = contract.application if contract else None
    if application:
        require_tenant_access(request, application.institution_id)
        require_mobile_owns_application(db, request, application)
    return installment
