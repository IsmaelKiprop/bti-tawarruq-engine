"""Ops: invite and approve Buruuj Lend mobile customers."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from tawarruq.api.deps import require_write_ops, tenant_filter_institution_id
from tawarruq.database import get_db
from tawarruq.schemas.mobile_auth import (
    MobileApproveRequest,
    MobileAuthDelivery,
    MobileInviteCreate,
    MobileRejectRequest,
)
from tawarruq.services import mobile_onboarding_service as onboarding

router = APIRouter(prefix="/ops/mobile", tags=["Mobile Lend Ops"])


@router.get("/accounts")
def list_accounts(
    request: Request,
    approval_status: str | None = Query(None),
    institution_id: str | None = None,
    db: Session = Depends(get_db),
):
    require_write_ops(request)
    scoped = tenant_filter_institution_id(request, institution_id)
    accounts = onboarding.list_mobile_accounts(
        db, institution_id=scoped, approval_status=approval_status
    )
    return [onboarding.account_ops_public(a, db) for a in accounts]


@router.post("/accounts/{account_id}/approve")
def approve_account(
    account_id: str,
    payload: MobileApproveRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    require_write_ops(request)
    try:
        scoped = tenant_filter_institution_id(request, payload.institution_id)
        account = onboarding.approve_account(
            db,
            account_id,
            institution_id=scoped or payload.institution_id,
            credit_limit=payload.credit_limit,
            phone=payload.phone,
            credit_score=payload.credit_score,
            ops_user_id=getattr(request.state, "ops_user_id", None),
        )
        db.commit()
        db.refresh(account)
        return onboarding.account_ops_public(account, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/accounts/{account_id}/reject")
def reject_account(
    account_id: str,
    payload: MobileRejectRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    require_write_ops(request)
    try:
        account = onboarding.reject_account(
            db,
            account_id,
            reason=payload.reason,
            ops_user_id=getattr(request.state, "ops_user_id", None),
        )
        db.commit()
        return onboarding.account_ops_public(account, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/invites")
def list_invites(
    request: Request,
    status: str | None = Query(None),
    institution_id: str | None = None,
    db: Session = Depends(get_db),
):
    require_write_ops(request)
    scoped = tenant_filter_institution_id(request, institution_id)
    invites = onboarding.list_invites(db, institution_id=scoped, status=status)
    return [onboarding.invite_public(i) for i in invites]


@router.post("/invites", status_code=201)
def create_invite(
    payload: MobileInviteCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    require_write_ops(request)
    try:
        scoped = tenant_filter_institution_id(request, payload.institution_id)
        institution_id = scoped or payload.institution_id
        invite, delivery = onboarding.create_invite(
            db,
            institution_id=institution_id,
            email=payload.email,
            phone=payload.phone,
            full_name=payload.full_name,
            credit_limit=payload.credit_limit,
            activate_on_claim=payload.activate_on_claim,
            expires_days=payload.expires_days,
            created_by_ops_user_id=getattr(request.state, "ops_user_id", None),
        )
        db.commit()
        db.refresh(invite)
        return {
            **onboarding.invite_public(invite),
            "delivery": MobileAuthDelivery(
                smtp_sent=delivery.get("smtp_sent", False),
                mail_path=delivery.get("mail_path"),
                dev_code=delivery.get("dev_code"),
                status="sent",
            ).model_dump(),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/invites/{invite_id}/revoke")
def revoke_invite(invite_id: str, request: Request, db: Session = Depends(get_db)):
    require_write_ops(request)
    try:
        invite = onboarding.revoke_invite(db, invite_id)
        db.commit()
        return onboarding.invite_public(invite)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
