"""Institution invite + approval for Buruuj Lend hybrid onboarding."""

from __future__ import annotations

import secrets
from datetime import timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session, joinedload

from tawarruq.enums import AmlStatus, KycStatus
from tawarruq.models.customer import Customer
from tawarruq.models.institution import Institution
from tawarruq.models.mobile_account import (
    APPROVAL_APPROVED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
    APPROVAL_SUSPENDED,
    MobileAccount,
    MobileInvite,
)
from tawarruq.services.customer_notify_service import normalize_email
from tawarruq.services.customer_service import create_customer, update_customer
from tawarruq.services.mobile_auth_service import _deliver_email_code, _utcnow, account_public


def _generate_invite_code() -> str:
    # Short human-shareable code e.g. BL-A7K2MQ
    return f"BL-{secrets.token_hex(3).upper()}"


def can_borrow(account: MobileAccount, db: Session | None = None) -> bool:
    if not account.active or not account.email_verified:
        return False
    if account.approval_status != APPROVAL_APPROVED:
        return False
    if not account.customer_id:
        return False
    if db is not None:
        customer = db.get(Customer, account.customer_id)
        if not customer:
            return False
        if customer.kyc_status != KycStatus.VERIFIED:
            return False
        if customer.aml_status != AmlStatus.CLEAR:
            return False
        # Still approved even at full utilization — UI/API will block over-limit amounts
    return True


def customer_utilized_credit(db: Session, customer_id: str) -> Decimal:
    """Outstanding exposure: unpaid installments, or disbursed/in-flight funded apps."""
    from tawarruq.enums import ApplicationStatus, InstallmentStatus, LegStatus
    from tawarruq.models.application import FinancingApplication
    from tawarruq.models.kenya_flow import MurabahaContract, RepaymentInstallment
    from tawarruq.models.transaction import CommodityTransaction, TransactionLeg

    terminal = {
        ApplicationStatus.COMPLETED.value,
        ApplicationStatus.FAILED.value,
        ApplicationStatus.ELIGIBILITY_FAILED.value,
    }
    apps = (
        db.query(FinancingApplication)
        .filter(FinancingApplication.customer_id == customer_id)
        .all()
    )
    utilized = Decimal("0")
    for app in apps:
        if app.status in terminal:
            continue
        contract = (
            db.query(MurabahaContract)
            .filter(MurabahaContract.application_id == app.id)
            .first()
        )
        if contract:
            installments = (
                db.query(RepaymentInstallment)
                .filter(RepaymentInstallment.contract_id == contract.id)
                .all()
            )
            if installments:
                unpaid = sum(
                    (
                        Decimal(str(i.amount))
                        for i in installments
                        if i.status != InstallmentStatus.PAID.value
                    ),
                    Decimal("0"),
                )
                if unpaid <= 0:
                    # Fully paid: close out so limit refreshes cleanly
                    app.status = ApplicationStatus.COMPLETED.value
                    continue
                utilized += unpaid
                continue
        # In-flight only counts after commodity purchase confirmed (failed Apply
        # attempts must not lock the approved limit).
        txn = (
            db.query(CommodityTransaction)
            .filter(CommodityTransaction.application_id == app.id)
            .first()
        )
        if not txn:
            continue
        purchase_ok = (
            db.query(TransactionLeg)
            .filter(
                TransactionLeg.transaction_id == txn.id,
                TransactionLeg.status == LegStatus.CONFIRMED.value,
            )
            .first()
            is not None
        )
        if not purchase_ok:
            continue
        utilized += Decimal(str(app.amount_requested or 0))
    return utilized


def list_customer_facilities(db: Session, customer_id: str, *, limit: int = 8) -> list[dict[str, Any]]:
    """Recent facilities for mobile Home activity (live paid/status)."""
    from tawarruq.enums import ApplicationStatus, InstallmentStatus
    from tawarruq.models.application import FinancingApplication
    from tawarruq.models.institution import Institution
    from tawarruq.models.kenya_flow import (
        AgentDealer,
        AgentDealerFloatTopup,
        AssetBatch,
        MurabahaContract,
        RepaymentInstallment,
    )
    from tawarruq.models.transaction import CommodityTransaction, TransactionLeg

    apps = (
        db.query(FinancingApplication)
        .filter(FinancingApplication.customer_id == customer_id)
        .order_by(FinancingApplication.created_at.desc())
        .limit(limit * 2)
        .all()
    )
    rows: list[dict[str, Any]] = []
    for app in apps:
        if app.status in {
            ApplicationStatus.FAILED.value,
            ApplicationStatus.ELIGIBILITY_FAILED.value,
        }:
            # Hide abandoned Apply attempts from the customer feed
            continue
        if len(rows) >= limit:
            break
        institution = db.get(Institution, app.institution_id)
        institution_name = institution.name if institution else None

        contract = (
            db.query(MurabahaContract)
            .filter(MurabahaContract.application_id == app.id)
            .first()
        )
        installments: list[RepaymentInstallment] = []
        if contract:
            installments = (
                db.query(RepaymentInstallment)
                .filter(RepaymentInstallment.contract_id == contract.id)
                .order_by(RepaymentInstallment.installment_number)
                .all()
            )
        paid = sum(1 for i in installments if i.status == InstallmentStatus.PAID.value)
        total = len(installments)
        if total > 0 and paid >= total and app.status != ApplicationStatus.COMPLETED.value:
            app.status = ApplicationStatus.COMPLETED.value
        settled = app.status == ApplicationStatus.COMPLETED.value or (total > 0 and paid >= total)
        outstanding = sum(
            (Decimal(str(i.amount)) for i in installments if i.status != InstallmentStatus.PAID.value),
            Decimal("0"),
        )
        if settled:
            label = "Paid in full"
        elif total > 0:
            label = f"Repaying {paid} of {total}"
        elif app.status in {
            ApplicationStatus.FAILED.value,
            ApplicationStatus.ELIGIBILITY_FAILED.value,
        }:
            label = "Closed"
        else:
            label = "In progress"

        agent_name = None
        txns = (
            db.query(CommodityTransaction)
            .filter(CommodityTransaction.application_id == app.id)
            .all()
        )
        for txn in txns:
            topup = (
                db.query(AgentDealerFloatTopup)
                .filter(AgentDealerFloatTopup.reference == f"TXN-{txn.id[:8]}")
                .first()
            )
            if topup:
                dealer = db.get(AgentDealer, topup.dealer_id)
                if dealer:
                    agent_name = dealer.business_name
                    break
            legs = db.query(TransactionLeg).filter(TransactionLeg.transaction_id == txn.id).all()
            for leg in legs:
                batch = (
                    db.query(AssetBatch)
                    .filter(AssetBatch.leg_id == leg.id, AssetBatch.source_dealer_code.isnot(None))
                    .first()
                )
                if batch and batch.source_dealer_code:
                    dealer = (
                        db.query(AgentDealer)
                        .filter(AgentDealer.code == batch.source_dealer_code)
                        .first()
                    )
                    if dealer:
                        agent_name = dealer.business_name
                        break
            if agent_name:
                break

        rows.append(
            {
                "application_id": app.id,
                "amount": str(app.amount_requested),
                "status": app.status,
                "label": label,
                "settled": settled,
                "installments_paid": paid,
                "installments_total": total,
                "outstanding": str(outstanding),
                "created_at": app.created_at.isoformat() if app.created_at else None,
                "institution_id": app.institution_id,
                "institution_name": institution_name,
                "agent_dealer_name": agent_name,
            }
        )
    return rows


def account_credit_snapshot(account: MobileAccount, db: Session) -> dict[str, str]:
    limit = Decimal(str(account.credit_limit or 0))
    utilized = (
        customer_utilized_credit(db, account.customer_id) if account.customer_id else Decimal("0")
    )
    available = max(Decimal("0"), limit - utilized)
    return {
        "credit_limit": str(limit),
        "credit_utilized": str(utilized),
        "available_limit": str(available),
    }


def assert_within_available_limit(
    db: Session,
    *,
    customer_id: str,
    amount: Decimal | str | float,
) -> None:
    """Raise ValueError if amount exceeds remaining approved limit for this customer."""
    from tawarruq.models.mobile_account import MobileAccount

    account = (
        db.query(MobileAccount)
        .filter(MobileAccount.customer_id == customer_id, MobileAccount.active.is_(True))
        .first()
    )
    if not account or account.credit_limit is None:
        return
    snap = account_credit_snapshot(account, db)
    available = Decimal(snap["available_limit"])
    requested = Decimal(str(amount))
    if requested > available:
        raise ValueError(
            f"Amount KES {requested} exceeds available limit KES {available} "
            f"(approved KES {snap['credit_limit']}, utilized KES {snap['credit_utilized']})"
        )


def approval_message(account: MobileAccount) -> str:
    if not account.email_verified:
        return "Verify your email to continue."
    if account.approval_status == APPROVAL_PENDING:
        return "Your account is awaiting institution approval. You cannot borrow yet."
    if account.approval_status == APPROVAL_REJECTED:
        reason = account.rejection_reason or "Please contact your institution."
        return f"Your financing access was declined. {reason}"
    if account.approval_status == APPROVAL_SUSPENDED:
        return "Your financing access is suspended. Contact your institution."
    if account.approval_status == APPROVAL_APPROVED:
        return "Approved. You can apply for Halal financing."
    return "Complete onboarding to unlock financing."


def enrich_account_public(account: MobileAccount, db: Session) -> dict[str, Any]:
    data = account_public(account)
    snap = account_credit_snapshot(account, db)
    institution_name = None
    if account.institution_id:
        from tawarruq.models.institution import Institution

        institution = db.get(Institution, account.institution_id)
        institution_name = institution.name if institution else None

    agent_dealer_name = None
    agent_float_available = None
    if account.institution_id:
        from tawarruq.models.kenya_flow import AgentDealer

        dealer = (
            db.query(AgentDealer)
            .filter(AgentDealer.active.is_(True))
            .filter(
                (AgentDealer.institution_id == account.institution_id)
                | (AgentDealer.institution_id.is_(None))
            )
            .order_by(AgentDealer.created_at)
            .first()
        )
        if dealer:
            agent_dealer_name = dealer.business_name
            agent_float_available = str(dealer.float_balance)

    data.update(
        {
            "approval_status": account.approval_status or APPROVAL_PENDING,
            "phone": account.phone,
            "credit_limit": snap["credit_limit"] if account.credit_limit is not None else None,
            "credit_utilized": snap["credit_utilized"],
            "available_limit": snap["available_limit"],
            "can_borrow": can_borrow(account, db),
            "approval_message": approval_message(account),
            "rejection_reason": account.rejection_reason,
            "has_invite": bool(account.invite_id),
            "institution_name": institution_name,
            "agent_dealer_name": agent_dealer_name,
            "agent_float_available": agent_float_available,
            "kyc_status": None,
            "national_id": None,
            "unread_notifications": 0,
        }
    )
    if account.customer_id:
        customer = db.get(Customer, account.customer_id)
        if customer:
            data["kyc_status"] = customer.kyc_status
            data["national_id"] = customer.national_id
    from tawarruq.services import mobile_inbox_service

    data["unread_notifications"] = mobile_inbox_service.unread_count(db, account.id)
    return data


def create_invite(
    db: Session,
    *,
    institution_id: str,
    email: str,
    phone: str | None = None,
    full_name: str | None = None,
    credit_limit: Decimal | str | float = Decimal("100000"),
    activate_on_claim: bool = False,
    expires_days: int = 14,
    created_by_ops_user_id: str | None = None,
) -> tuple[MobileInvite, dict[str, Any]]:
    institution = db.get(Institution, institution_id)
    if not institution:
        raise ValueError("Institution not found")
    normalized = normalize_email(email)
    if not normalized:
        raise ValueError("Valid invite email is required")

    invite = MobileInvite(
        institution_id=institution_id,
        email=normalized,
        phone=(phone or "").strip() or None,
        full_name=(full_name or "").strip() or None,
        code=_generate_invite_code(),
        credit_limit=Decimal(str(credit_limit)),
        activate_on_claim=activate_on_claim,
        status="pending",
        expires_at=_utcnow() + timedelta(days=expires_days),
        created_by_ops_user_id=created_by_ops_user_id,
    )
    db.add(invite)
    db.flush()

    delivery = _deliver_email_code(
        email=normalized,
        subject="You are invited to Buruuj Lend",
        body=(
            f"Assalamu alaikum{(' ' + invite.full_name) if invite.full_name else ''},\n\n"
            f"{institution.name} invited you to Buruuj Lend (Shariah financing).\n\n"
            f"1. Install Buruuj Lend and register with this email: {normalized}\n"
            f"2. Verify your email, then enter invite code: {invite.code}\n"
            f"3. Wait for activation (or you may be activated automatically).\n\n"
            f"Credit limit offered: KES {invite.credit_limit}\n"
            f"Code expires in {expires_days} days.\n"
        ),
        code=invite.code,
    )
    return invite, delivery


def list_invites(
    db: Session,
    *,
    institution_id: str | None = None,
    status: str | None = None,
) -> list[MobileInvite]:
    query = db.query(MobileInvite).options(joinedload(MobileInvite.institution)).order_by(
        MobileInvite.created_at.desc()
    )
    if institution_id:
        query = query.filter(MobileInvite.institution_id == institution_id)
    if status:
        query = query.filter(MobileInvite.status == status)
    return query.limit(200).all()


def list_mobile_accounts(
    db: Session,
    *,
    institution_id: str | None = None,
    approval_status: str | None = None,
) -> list[MobileAccount]:
    query = (
        db.query(MobileAccount)
        .options(joinedload(MobileAccount.institution), joinedload(MobileAccount.customer))
        .order_by(MobileAccount.created_at.desc())
    )
    if institution_id:
        query = query.filter(MobileAccount.institution_id == institution_id)
    if approval_status:
        query = query.filter(MobileAccount.approval_status == approval_status)
    return query.limit(200).all()


def claim_invite(db: Session, account: MobileAccount, invite_code: str) -> MobileAccount:
    code = (invite_code or "").strip().upper()
    if not code:
        raise ValueError("Invite code is required")
    if not account.email_verified:
        raise ValueError("Verify your email before claiming an invite")

    invite = db.query(MobileInvite).filter(MobileInvite.code == code).first()
    if not invite or invite.status != "pending":
        raise ValueError("Invalid or already used invite code")
    if invite.expires_at:
        expires = invite.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires < _utcnow():
            raise ValueError("Invite code has expired")
    if normalize_email(invite.email) != normalize_email(account.email):
        raise ValueError("This invite was issued for a different email address")

    account.institution_id = invite.institution_id
    account.invite_id = invite.id
    account.credit_limit = invite.credit_limit
    if invite.phone and not account.phone:
        account.phone = invite.phone
    if invite.full_name and account.full_name == "Kenya Customer":
        account.full_name = invite.full_name

    invite.status = "claimed"
    invite.claimed_account_id = account.id

    if invite.activate_on_claim:
        _activate_account(
            db,
            account,
            credit_limit=invite.credit_limit,
            phone=account.phone or invite.phone,
            ops_user_id=invite.created_by_ops_user_id,
        )
    else:
        account.approval_status = APPROVAL_PENDING

    db.flush()
    return account


def approve_account(
    db: Session,
    account_id: str,
    *,
    institution_id: str | None,
    credit_limit: Decimal | str | float,
    phone: str | None = None,
    credit_score: int = 680,
    ops_user_id: str | None = None,
) -> MobileAccount:
    account = db.get(MobileAccount, account_id)
    if not account:
        raise ValueError("Mobile account not found")
    if not account.email_verified:
        raise ValueError("Customer must verify email before approval")
    if institution_id:
        institution = db.get(Institution, institution_id)
        if not institution:
            raise ValueError("Institution not found")
        account.institution_id = institution_id
    if not account.institution_id:
        from tawarruq.services import application_service

        institution = application_service.get_or_create_default_institution(db)
        account.institution_id = institution.id

    resolved_phone = (phone or account.phone or "").strip()
    if not resolved_phone.startswith("254") or len(resolved_phone) < 12:
        raise ValueError("A valid 254… phone is required to activate financing")

    account.phone = resolved_phone
    _activate_account(
        db,
        account,
        credit_limit=Decimal(str(credit_limit)),
        phone=resolved_phone,
        credit_score=credit_score,
        ops_user_id=ops_user_id,
    )
    db.flush()
    return account


def _activate_account(
    db: Session,
    account: MobileAccount,
    *,
    credit_limit: Decimal,
    phone: str | None,
    credit_score: int = 680,
    ops_user_id: str | None = None,
) -> None:
    from tawarruq.services import application_service

    if not account.institution_id:
        institution = application_service.get_or_create_default_institution(db)
        account.institution_id = institution.id

    phone_value = (phone or account.phone or "").strip()
    if not phone_value.startswith("254"):
        raise ValueError("Phone 254… required for activation")

    if account.customer_id:
        customer = db.get(Customer, account.customer_id)
        if not customer:
            raise ValueError("Linked customer missing")
        customer.phone = phone_value
        update_customer(
            db,
            customer.id,
            email=account.email,
            full_name=account.full_name,
            wallet_number=phone_value,
            kyc_status=KycStatus.VERIFIED,
            aml_status=AmlStatus.CLEAR,
            credit_score=credit_score,
        )
    else:
        existing = (
            db.query(Customer)
            .filter(Customer.institution_id == account.institution_id, Customer.phone == phone_value)
            .first()
        )
        if existing:
            existing.phone = phone_value
            update_customer(
                db,
                existing.id,
                email=account.email,
                full_name=account.full_name,
                wallet_number=phone_value,
                kyc_status=KycStatus.VERIFIED,
                aml_status=AmlStatus.CLEAR,
                credit_score=credit_score,
            )
            customer = existing
        else:
            customer = create_customer(
                db,
                institution_id=account.institution_id,
                phone=phone_value,
                email=account.email,
                full_name=account.full_name,
                wallet_number=phone_value,
                kyc_status=KycStatus.VERIFIED,
                aml_status=AmlStatus.CLEAR,
                credit_score=credit_score,
            )
        account.customer_id = customer.id

    account.credit_limit = credit_limit
    account.approval_status = APPROVAL_APPROVED
    account.approved_at = _utcnow()
    account.approved_by_ops_user_id = ops_user_id
    account.rejection_reason = None
    account.phone = phone_value
    account.active = True

    from tawarruq.services import mobile_inbox_service
    from tawarruq.models.institution import Institution as InstModel

    inst = db.get(InstModel, account.institution_id) if account.institution_id else None
    inst_name = inst.name if inst else "your institution"
    mobile_inbox_service.push_notification(
        db,
        account,
        kind="approval",
        title="Financing approved",
        body=f"{inst_name} approved your Buruuj Lend account. Limit KES {credit_limit}.",
    )


def reject_account(
    db: Session,
    account_id: str,
    *,
    reason: str,
    ops_user_id: str | None = None,
) -> MobileAccount:
    account = db.get(MobileAccount, account_id)
    if not account:
        raise ValueError("Mobile account not found")
    account.approval_status = APPROVAL_REJECTED
    account.rejection_reason = (reason or "").strip() or "Declined by institution"
    account.approved_by_ops_user_id = ops_user_id
    account.approved_at = _utcnow()
    db.flush()
    return account


def revoke_invite(db: Session, invite_id: str) -> MobileInvite:
    invite = db.get(MobileInvite, invite_id)
    if not invite:
        raise ValueError("Invite not found")
    if invite.status == "claimed":
        raise ValueError("Invite already claimed")
    invite.status = "revoked"
    db.flush()
    return invite


def invite_public(invite: MobileInvite) -> dict[str, Any]:
    return {
        "id": invite.id,
        "institution_id": invite.institution_id,
        "institution_name": invite.institution.name if invite.institution else None,
        "email": invite.email,
        "phone": invite.phone,
        "full_name": invite.full_name,
        "code": invite.code,
        "credit_limit": str(invite.credit_limit),
        "activate_on_claim": invite.activate_on_claim,
        "status": invite.status,
        "expires_at": invite.expires_at.isoformat() if invite.expires_at else None,
        "claimed_account_id": invite.claimed_account_id,
        "created_at": invite.created_at.isoformat() if invite.created_at else None,
    }


def account_ops_public(account: MobileAccount, db: Session) -> dict[str, Any]:
    data = enrich_account_public(account, db)
    data["created_at"] = account.created_at.isoformat() if account.created_at else None
    data["approved_at"] = account.approved_at.isoformat() if account.approved_at else None
    data["institution_name"] = account.institution.name if account.institution else None
    return data
