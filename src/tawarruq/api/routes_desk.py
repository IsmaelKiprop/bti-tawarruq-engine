from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload

from tawarruq.api.deps import require_approve_txn, require_tenant_access, require_write_ops, tenant_filter_institution_id
from tawarruq.database import get_db
from tawarruq.enums import ApiKeyRole
from tawarruq.models.fi_desk import FiDeskCase
from tawarruq.models.kenya_flow import ShariahAuditLog
from tawarruq.models.ops_user import OpsUser
from tawarruq.schemas.desk import (
    DeskApproverRead,
    DeskAuditRead,
    DeskCaseCreate,
    DeskCaseDecide,
    DeskCaseRead,
    DeskOtpSend,
    DeskOtpSendRead,
    DeskOtpVerify,
    DeskStepWrite,
)
from tawarruq.services import fi_desk_service
from tawarruq.services.rbac import get_request_role, has_permission

router = APIRouter(prefix="/desk", tags=["FI Desk"])


def _viewer(db: Session, request: Request) -> OpsUser | None:
    user_id = getattr(request.state, "ops_user_id", None)
    return db.get(OpsUser, user_id) if user_id else None


def _load_case(db: Session, case_id: str, request: Request) -> FiDeskCase:
    case = (
        db.query(FiDeskCase)
        .options(
            joinedload(FiDeskCase.institution),
            joinedload(FiDeskCase.assigned_approver),
            joinedload(FiDeskCase.requested_by),
        )
        .filter(FiDeskCase.id == case_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Desk case not found")
    require_tenant_access(request, case.institution_id)
    role = get_request_role(request)
    user_id = getattr(request.state, "ops_user_id", None)
    if role == ApiKeyRole.FI_APPROVER and case.assigned_approver_id != user_id:
        raise HTTPException(status_code=403, detail="This case is assigned to another approver")
    fi_desk_service.refresh_resale_status(case)
    fi_desk_service.seal_completed_case(case)
    return case


@router.get("/approvers", response_model=list[DeskApproverRead])
def list_desk_approvers(
    request: Request, db: Session = Depends(get_db), institution_id: str | None = Query(default=None)
) -> list[DeskApproverRead]:
    scoped = tenant_filter_institution_id(request, institution_id)
    if not scoped:
        raise HTTPException(status_code=400, detail="Institution is required")
    require_tenant_access(request, scoped)
    return fi_desk_service.list_approvers(db, scoped)


@router.get("/cases", response_model=list[DeskCaseRead])
def list_desk_cases(
    request: Request, db: Session = Depends(get_db), institution_id: str | None = Query(default=None)
) -> list[DeskCaseRead]:
    if not (has_permission(request, "write_ops") or has_permission(request, "approve_txn") or has_permission(request, "view_shariah")):
        raise HTTPException(status_code=403, detail="Desk access denied")
    scoped = tenant_filter_institution_id(request, institution_id)
    role = get_request_role(request)
    user_id = getattr(request.state, "ops_user_id", None)
    rows = fi_desk_service.list_cases(
        db,
        institution_id=scoped,
        viewer_id=user_id,
        role=role.value if role else None,
    )
    if not rows:
        return []
    for row in rows:
        fi_desk_service.refresh_resale_status(row)
        fi_desk_service.seal_completed_case(row)
    db.commit()
    loaded = (
        db.query(FiDeskCase)
        .options(
            joinedload(FiDeskCase.institution),
            joinedload(FiDeskCase.assigned_approver),
            joinedload(FiDeskCase.requested_by),
        )
        .filter(FiDeskCase.id.in_([row.id for row in rows]))
        .all()
    )
    by_id = {row.id: row for row in loaded}
    return [fi_desk_service.serialize_case(by_id[row.id]) for row in rows if row.id in by_id]


@router.post("/cases", response_model=DeskCaseRead, status_code=201)
def create_desk_case(payload: DeskCaseCreate, request: Request, db: Session = Depends(get_db)) -> DeskCaseRead:
    require_write_ops(request)
    institution_id = tenant_filter_institution_id(request, payload.institution_id)
    if not institution_id:
        raise HTTPException(status_code=400, detail="This login is not bound to an institution")
    require_tenant_access(request, institution_id)
    case = fi_desk_service.create_case(
        db, payload, institution_id=institution_id, requester=_viewer(db, request)
    )
    db.commit()
    return fi_desk_service.serialize_case(_load_case(db, case.id, request))


@router.get("/cases/{case_id}", response_model=DeskCaseRead)
def get_desk_case(case_id: str, request: Request, db: Session = Depends(get_db)) -> DeskCaseRead:
    case = _load_case(db, case_id, request)
    db.commit()
    return fi_desk_service.serialize_case(case)


@router.post("/cases/{case_id}/decide", response_model=DeskCaseRead)
def decide_desk_case(
    case_id: str, payload: DeskCaseDecide, request: Request, db: Session = Depends(get_db)
) -> DeskCaseRead:
    require_approve_txn(request)
    case = _load_case(db, case_id, request)
    actor = _viewer(db, request)
    if not actor:
        raise HTTPException(status_code=401, detail="Login required")
    fi_desk_service.decide_case(db, case, decision=payload.decision, comments=payload.comments, actor=actor)
    db.commit()
    return fi_desk_service.serialize_case(_load_case(db, case_id, request))


@router.post("/cases/{case_id}/steps/{step}", response_model=DeskCaseRead)
def complete_desk_step(
    case_id: str, step: int, payload: DeskStepWrite, request: Request, db: Session = Depends(get_db)
) -> DeskCaseRead:
    require_write_ops(request)
    case = _load_case(db, case_id, request)
    actor = getattr(_viewer(db, request), "email", None) or "fi_ops"
    fi_desk_service.complete_step(db, case, step, payload.fields, actor=actor)
    db.commit()
    return fi_desk_service.serialize_case(_load_case(db, case_id, request))


@router.post("/cases/{case_id}/otp/send", response_model=DeskOtpSendRead)
def send_desk_otp(
    case_id: str, payload: DeskOtpSend, request: Request, db: Session = Depends(get_db)
) -> DeskOtpSendRead:
    require_write_ops(request)
    case = _load_case(db, case_id, request)
    result = fi_desk_service.send_otp(db, case, payload.purpose)
    db.commit()
    return DeskOtpSendRead(**result)


@router.post("/cases/{case_id}/otp/verify", response_model=DeskCaseRead)
def verify_desk_otp(
    case_id: str, payload: DeskOtpVerify, request: Request, db: Session = Depends(get_db)
) -> DeskCaseRead:
    require_write_ops(request)
    case = _load_case(db, case_id, request)
    actor = getattr(_viewer(db, request), "email", None) or "fi_ops"
    fi_desk_service.verify_otp(db, case, payload.purpose, payload.code, actor=actor)
    db.commit()
    return fi_desk_service.serialize_case(_load_case(db, case_id, request))


@router.get("/audit", response_model=list[DeskAuditRead])
def list_desk_audit(
    request: Request,
    db: Session = Depends(get_db),
    institution_id: str | None = Query(default=None),
    case_id: str | None = Query(default=None),
) -> list[DeskAuditRead]:
    if not has_permission(request, "view_shariah"):
        raise HTTPException(status_code=403, detail="Shariah access denied")
    scoped = tenant_filter_institution_id(request, institution_id)
    query = db.query(ShariahAuditLog).filter(ShariahAuditLog.entity_type == "fi_desk_case")
    if scoped:
        query = query.filter(ShariahAuditLog.institution_id == scoped)
    if case_id:
        query = query.filter(ShariahAuditLog.entity_id == case_id)
    rows = query.order_by(ShariahAuditLog.timestamp.desc()).limit(500).all()
    return [
        DeskAuditRead(
            id=row.id,
            timestamp=row.timestamp,
            step_id=row.step_id,
            entity_id=row.entity_id,
            actor_from=row.actor_from,
            actor_to=row.actor_to,
            details=row.details,
            institution_id=row.institution_id,
        )
        for row in rows
    ]
