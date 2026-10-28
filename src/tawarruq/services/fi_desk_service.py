import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from tawarruq.config import get_settings
from tawarruq.enums import ApiKeyRole, ShariahStepId
from tawarruq.models.fi_desk import FiDeskCase
from tawarruq.models.institution import Institution
from tawarruq.models.ops_user import OpsUser
from tawarruq.schemas.desk import DeskApproverRead, DeskCaseCreate, DeskCaseRead
from tawarruq.services.shariah_audit_service import log_shariah_step

STEP_AUDIT = {
    1: ShariahStepId.FINANCING_REQUEST,
    2: ShariahStepId.ELIGIBILITY_CHECK,
    3: ShariahStepId.MURABAHA_PURCHASE,
    4: ShariahStepId.CUSTOMER_ACCEPTANCE,
    5: ShariahStepId.WAKALA_APPOINTMENT,
    6: ShariahStepId.CASA_CREDIT,
    7: ShariahStepId.MUQASSAH_SET_OFF,
    8: ShariahStepId.WALLET_DISBURSEMENT,
}

OTP_PURPOSES = {"murabaha", "agent", "casa"}
OTP_MINUTES = 10


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def _parse_payload(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _dump_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, default=str)


def _hash_otp(case_id: str, purpose: str, code: str) -> str:
    return hashlib.sha256(f"{case_id}:{purpose}:{code}".encode()).hexdigest()


def _user_name(user: OpsUser | None) -> str | None:
    if not user:
        return None
    return user.full_name or user.email


def seal_completed_case(case: FiDeskCase) -> FiDeskCase:
    payload = _parse_payload(case.payload_json)
    clearing = payload.get("clearing") if isinstance(payload.get("clearing"), dict) else {}
    complete = payload.get("complete") if isinstance(payload.get("complete"), dict) else {}
    stamps = payload.get("timestamps") if isinstance(payload.get("timestamps"), dict) else {}
    finished = (
        case.current_step >= 8
        or clearing.get("final_status") == "Complete"
        or complete.get("final_status") == "Complete"
        or bool(stamps.get("complete"))
        or bool(stamps.get("clearing"))
    )
    if finished and case.status in {"in_progress", "approved"}:
        case.status = "complete"
        case.current_step = 8
    return case


def serialize_case(case: FiDeskCase) -> DeskCaseRead:
    seal_completed_case(case)
    return DeskCaseRead(
        id=case.id,
        institution_id=case.institution_id,
        institution_name=case.institution.name if case.institution else None,
        current_step=case.current_step,
        status=case.status,
        assigned_approver_id=case.assigned_approver_id,
        assigned_approver_name=_user_name(case.assigned_approver),
        requested_by_id=case.requested_by_id,
        requested_by_name=_user_name(case.requested_by),
        approval_comments=case.approval_comments,
        payload=_parse_payload(case.payload_json),
        created_at=case.created_at,
        updated_at=case.updated_at,
    )


def _stamp(payload: dict[str, Any], key: str) -> None:
    stamps = payload.setdefault("timestamps", {})
    if isinstance(stamps, dict):
        stamps[key] = _now().isoformat()


def _audit(db: Session, case: FiDeskCase, step: int, actor: str, details: str, extra: dict[str, Any] | None = None) -> None:
    payload = {"step": step, "status": case.status, "at": _now().isoformat(), **(extra or {})}
    log_shariah_step(
        db,
        step_id=STEP_AUDIT[step],
        entity_type="fi_desk_case",
        entity_id=case.id,
        actor_from=actor,
        actor_to=case.institution_id,
        payload=payload,
        details=details,
        institution_id=case.institution_id,
        application_id=case.id,
    )


def list_approvers(db: Session, institution_id: str) -> list[DeskApproverRead]:
    rows = (
        db.query(OpsUser)
        .filter(
            OpsUser.institution_id == institution_id,
            OpsUser.role == ApiKeyRole.FI_APPROVER.value,
            OpsUser.active.is_(True),
        )
        .order_by(OpsUser.full_name.asc())
        .all()
    )
    return [DeskApproverRead(id=row.id, full_name=row.full_name, email=row.email) for row in rows]


def list_cases(db: Session, *, institution_id: str | None, viewer_id: str | None, role: str | None) -> list[FiDeskCase]:
    query = db.query(FiDeskCase)
    if institution_id:
        query = query.filter(FiDeskCase.institution_id == institution_id)
    if role == ApiKeyRole.FI_APPROVER.value and viewer_id:
        query = query.filter(FiDeskCase.assigned_approver_id == viewer_id)
    return query.order_by(FiDeskCase.updated_at.desc()).all()


def get_case(db: Session, case_id: str) -> FiDeskCase:
    case = db.get(FiDeskCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Desk case not found")
    return case


def create_case(
    db: Session,
    payload: DeskCaseCreate,
    *,
    institution_id: str,
    requester: OpsUser | None,
) -> FiDeskCase:
    institution = db.get(Institution, institution_id)
    if not institution:
        raise HTTPException(status_code=404, detail="Institution not found")
    approver = db.get(OpsUser, payload.assigned_approver_id)
    if (
        not approver
        or not approver.active
        or approver.role != ApiKeyRole.FI_APPROVER.value
        or approver.institution_id != institution_id
    ):
        raise HTTPException(status_code=400, detail="Pick an FI Approver on this institution")
    missing = [
        name
        for name, value in (
            ("customer_id", payload.customer_id),
            ("document_type", payload.document_type),
            ("customer_name", payload.customer_name),
            ("customer_phone", payload.customer_phone),
            ("customer_email", payload.customer_email),
            ("approved_facility_amount", payload.approved_facility_amount),
            ("facility_product_type", payload.facility_product_type),
        )
        if not str(value or "").strip()
    ]
    if missing:
        raise HTTPException(status_code=400, detail=f"Complete origination fields: {', '.join(missing)}")
    product = str(payload.facility_product_type or "").strip()
    if product.lower() != "airtime":
        raise HTTPException(status_code=400, detail="Commodity type must be Airtime")
    try:
        amount = float(str(payload.approved_facility_amount).replace(",", "").strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Approved facility amount must be a number")
    if amount < 0:
        raise HTTPException(status_code=400, detail="Approved facility amount cannot be negative")
    fields = payload.model_dump()
    fields.pop("institution_id", None)
    fields.pop("assigned_approver_id", None)
    body = {
        "origination": fields,
        "initiate": {
            "commodity": "Airtime",
            "commodity_quantity": payload.approved_facility_amount,
            "commodity_seller": "Safaricom",
            "commodity_buyer": institution.name,
            "commodity_agent": "Buruuj Fintech",
            "payment_reference": f"txn-{secrets.token_hex(3)}",
        },
        "timestamps": {},
    }
    _stamp(body, "origination_submitted")
    case = FiDeskCase(
        institution_id=institution_id,
        current_step=2,
        status="pending_approval",
        assigned_approver_id=approver.id,
        requested_by_id=requester.id if requester else None,
        payload_json=_dump_payload(body),
    )
    db.add(case)
    db.flush()
    actor = requester.email if requester else "fi_ops"
    _audit(db, case, 1, actor, f"Origination submitted for {payload.customer_name}")
    return case


def decide_case(db: Session, case: FiDeskCase, *, decision: str, comments: str, actor: OpsUser) -> FiDeskCase:
    if case.status != "pending_approval":
        raise HTTPException(status_code=400, detail="This case is not waiting for approval")
    if case.assigned_approver_id and case.assigned_approver_id != actor.id and actor.role != ApiKeyRole.PLATFORM_ADMIN.value:
        raise HTTPException(status_code=403, detail="Only the assigned FI Approver can decide this request")
    payload = _parse_payload(case.payload_json)
    payload["approval"] = {
        "request_id": case.id,
        "amount": (payload.get("origination") or {}).get("approved_facility_amount"),
        "requester_username": _user_name(case.requested_by),
        "approver_username": actor.full_name or actor.email,
        "status": decision,
        "comments": comments,
    }
    if decision == "approve":
        case.status = "approved"
        case.current_step = 3
        _stamp(payload, "approved")
        details = "FI Approver approved origination"
    elif decision == "return":
        case.status = "returned"
        case.current_step = 1
        _stamp(payload, "returned")
        details = "FI Approver returned origination"
    else:
        raise HTTPException(status_code=400, detail="Decision must be approve or return")
    case.approval_comments = comments
    case.payload_json = _dump_payload(payload)
    _audit(db, case, 2, actor.email, details, {"decision": decision, "comments": comments})
    return case


def complete_step(db: Session, case: FiDeskCase, step: int, fields: dict[str, Any], *, actor: str) -> FiDeskCase:
    if case.status == "pending_approval":
        raise HTTPException(status_code=400, detail="Wait for FI Approver before continuing")
    if case.status == "returned" and step != 1:
        raise HTTPException(status_code=400, detail="Resubmit origination before later steps")
    if step < 3 or step > 8:
        raise HTTPException(status_code=400, detail="Complete this step from the desk form")
    if step > case.current_step:
        raise HTTPException(status_code=400, detail="Complete the earlier step first")
    if step < case.current_step:
        raise HTTPException(status_code=400, detail="This step is already complete and cannot be changed")
    payload = _parse_payload(case.payload_json)
    keys = {3: "initiate", 4: "murabaha", 5: "resale", 6: "proceeds", 7: "clearing", 8: "complete"}
    bucket = keys[step]
    current = payload.get(bucket) if isinstance(payload.get(bucket), dict) else {}
    current.update({key: value for key, value in fields.items() if value is not None})
    if step == 3:
        orig = payload.get("origination") or {}
        current.setdefault("commodity", "Airtime")
        current.setdefault("commodity_quantity", orig.get("approved_facility_amount"))
        current.setdefault("commodity_seller", "Safaricom")
        current.setdefault("commodity_agent", "Buruuj Fintech")
        if not str(current.get("purchase_complete") or "").lower() in {"yes", "true", "1"}:
            raise HTTPException(status_code=400, detail="Mark purchase complete Yes before leaving Initiate Tawarruq")
        _stamp(payload, "purchase")
        current.setdefault("purchase_timestamp", payload["timestamps"].get("purchase"))
    if step == 4:
        initiate = payload.get("initiate") or {}
        orig = payload.get("origination") or {}
        cost = str(current.get("cost_price") or initiate.get("commodity_quantity") or "")
        profit = str(current.get("profit") or "")
        if not profit.strip():
            raise HTTPException(status_code=400, detail="Enter the Murabaha profit")
        if (payload.get("murabaha") or {}).get("sale_status") != "Complete":
            raise HTTPException(status_code=400, detail="Customer OTP must complete the Murabaha sale first")
        facility_account = str(current.get("facility_account") or "").strip()
        installments_raw = str(current.get("repayment_installments") or "").strip()
        first_due = str(current.get("first_installment_due_date") or "").strip()
        last_due = str(current.get("last_installment_due_date") or "").strip()
        if not facility_account or not installments_raw or not first_due or not last_due:
            raise HTTPException(
                status_code=400,
                detail="Enter facility account, repayment installments, and first and last installment due dates",
            )
        try:
            installments = int(installments_raw)
        except ValueError:
            raise HTTPException(status_code=400, detail="Repayment installments must be a whole number")
        if installments < 1:
            raise HTTPException(status_code=400, detail="Repayment installments must be at least 1")
        if last_due < first_due:
            raise HTTPException(status_code=400, detail="Last installment due date cannot be before the first")
        current["buyer_name"] = orig.get("customer_name")
        current["buyer_email"] = orig.get("customer_email")
        current["buyer_phone"] = orig.get("customer_phone")
        current["seller_name"] = (payload.get("initiate") or {}).get("commodity_buyer") or current.get("seller_name")
        current["facility_account"] = facility_account
        current["repayment_installments"] = str(installments)
        current["first_installment_due_date"] = first_due
        current["last_installment_due_date"] = last_due
        current["cost_price"] = cost
        current["profit"] = profit
        try:
            current["deferred_sale_price"] = str(float(cost) + float(profit))
        except ValueError:
            current["deferred_sale_price"] = f"{cost}+{profit}"
    if step == 5:
        if current.get("agent_appointment_status") != "Done":
            raise HTTPException(status_code=400, detail="Customer OTP must appoint the agent first")
        current.setdefault("agent_name", "Soqo Capital")
    if step == 6:
        if current.get("final_status") != "Complete":
            raise HTTPException(status_code=400, detail="Customer OTP must approve the CASA deposit first")
        account = str(current.get("customer_account_number") or "").strip()
        branch = str(current.get("customer_branch") or "").strip()
        if not account or not branch:
            raise HTTPException(status_code=400, detail="Enter customer CASA account and branch")
        current["customer_account_number"] = account
        current["customer_branch"] = branch
        current.setdefault("commodity", "Airtime")
        orig = payload.get("origination") or {}
        current.setdefault("commodity_quantity", orig.get("approved_facility_amount"))
        current.setdefault("resale_cost", orig.get("approved_facility_amount"))
    if step == 7:
        current.setdefault("settlement_ref", f"clr-{case.id[:8]}")
        _stamp(payload, "clearing")
        current.setdefault("settlement_timestamp", payload["timestamps"].get("clearing"))
        current["final_status"] = "Complete"
        _stamp(payload, "complete")
        case.status = "complete"
        case.current_step = 8
    if step == 8:
        current["final_status"] = "Complete"
        _stamp(payload, "complete")
        case.status = "complete"
        case.current_step = 8
    payload[bucket] = current
    case.payload_json = _dump_payload(payload)
    if case.status != "complete":
        case.status = "in_progress"
        case.current_step = min(8, max(case.current_step, step + 1))
    _audit(db, case, step, actor, f"Desk step {step} completed", current)
    return case


def send_otp(db: Session, case: FiDeskCase, purpose: str) -> dict[str, Any]:
    if purpose not in OTP_PURPOSES:
        raise HTTPException(status_code=400, detail="Unknown OTP purpose")
    required = {"murabaha": 4, "agent": 5, "casa": 6}[purpose]
    if case.current_step < required:
        raise HTTPException(status_code=400, detail="This OTP is not available yet")
    code = f"{secrets.randbelow(1_000_000):06d}"
    case.otp_purpose = purpose
    case.otp_hash = _hash_otp(case.id, purpose, code)
    case.otp_expires_at = _now() + timedelta(minutes=OTP_MINUTES)
    payload = _parse_payload(case.payload_json)
    _stamp(payload, f"otp_sent_{purpose}")
    case.payload_json = _dump_payload(payload)
    orig = payload.get("origination") or {}
    email = str(orig.get("customer_email") or "")
    smtp_sent = False
    settings = get_settings()
    if settings.smtp_host and email:
        try:
            from tawarruq.services.customer_notify_service import _send_smtp

            smtp_sent = bool(
                _send_smtp(
                    email,
                    f"BTI Tawarruq OTP ({purpose})",
                    f"Your one-time code is {code}. It expires in {OTP_MINUTES} minutes.",
                )
            )
        except Exception:
            smtp_sent = False
    _audit(db, case, required, "otp", f"OTP sent for {purpose}", {"purpose": purpose, "smtp_sent": smtp_sent})
    return {
        "purpose": purpose,
        "smtp_sent": smtp_sent,
        "dev_code": None if smtp_sent else code,
        "expires_at": case.otp_expires_at,
    }


def verify_otp(db: Session, case: FiDeskCase, purpose: str, code: str, *, actor: str) -> FiDeskCase:
    if purpose not in OTP_PURPOSES:
        raise HTTPException(status_code=400, detail="Unknown OTP purpose")
    if case.otp_purpose != purpose or not case.otp_hash:
        raise HTTPException(status_code=400, detail="Send an OTP first")
    if _aware(case.otp_expires_at) and _aware(case.otp_expires_at) < _now():
        payload = _parse_payload(case.payload_json)
        if purpose == "murabaha":
            murabaha = payload.setdefault("murabaha", {})
            murabaha["sale_status"] = "Expired"
            case.payload_json = _dump_payload(payload)
        raise HTTPException(status_code=400, detail="OTP expired")
    if _hash_otp(case.id, purpose, code.strip()) != case.otp_hash:
        _audit(db, case, {"murabaha": 4, "agent": 5, "casa": 6}[purpose], actor, f"OTP failed for {purpose}")
        raise HTTPException(status_code=400, detail="Incorrect OTP")
    payload = _parse_payload(case.payload_json)
    orig = payload.get("origination") or {}
    now = _now()
    _stamp(payload, f"otp_verified_{purpose}")
    if purpose == "murabaha":
        murabaha = payload.setdefault("murabaha", {})
        murabaha.update(
            {
                "sale_status": "Complete",
                "sale_timestamp": now.isoformat(),
                "proposed_owner_name": orig.get("customer_name"),
                "proposed_owner_id": orig.get("customer_id"),
                "proposed_owner_phone": orig.get("customer_phone"),
                "proposed_owner_email": orig.get("customer_email"),
            }
        )
        _stamp(payload, "murabaha_sale")
    if purpose == "agent":
        start = now + timedelta(seconds=6)
        end = start + timedelta(seconds=30)
        resale = payload.setdefault("resale", {})
        resale.update(
            {
                "current_owner_name": orig.get("customer_name"),
                "current_owner_id": orig.get("customer_id"),
                "current_owner_email": orig.get("customer_email"),
                "current_owner_phone": orig.get("customer_phone"),
                "agent_name": "Soqo Capital",
                "agent_appointment_status": "Done",
                "agent_appointment_timestamp": now.isoformat(),
                "resale_start_timestamp": start.isoformat(),
                "resale_end_timestamp": end.isoformat(),
                "resale_confirmation_status": "",
            }
        )
        _stamp(payload, "agent_appointed")
    if purpose == "casa":
        proceeds = payload.setdefault("proceeds", {})
        proceeds.update(
            {
                "owner_name": orig.get("customer_name"),
                "owner_id": orig.get("customer_id"),
                "owner_email": orig.get("customer_email"),
                "owner_phone": orig.get("customer_phone"),
                "deposit_txn_ref": f"casa-{case.id[:8]}",
                "final_status": "Complete",
            }
        )
        _stamp(payload, "casa_deposit")
    case.otp_purpose = None
    case.otp_hash = None
    case.otp_expires_at = None
    case.payload_json = _dump_payload(payload)
    _audit(db, case, {"murabaha": 4, "agent": 5, "casa": 6}[purpose], actor, f"OTP verified for {purpose}")
    return case


def refresh_resale_status(case: FiDeskCase) -> FiDeskCase:
    payload = _parse_payload(case.payload_json)
    resale = payload.get("resale")
    if not isinstance(resale, dict):
        return case
    end_raw = resale.get("resale_end_timestamp")
    if not end_raw:
        return case
    try:
        end = datetime.fromisoformat(str(end_raw))
    except ValueError:
        return case
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    if _now() >= end and resale.get("resale_confirmation_status") != "Done":
        resale["resale_confirmation_status"] = "Done"
        payload["resale"] = resale
        case.payload_json = _dump_payload(payload)
    return case
