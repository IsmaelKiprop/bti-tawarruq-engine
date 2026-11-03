import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

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


def _offer_acceptance_method(payload: dict[str, Any]) -> str:
    mode = str((payload.get("journey") or {}).get("offer_letter_mode") or (payload.get("origination") or {}).get("offer_letter_mode") or "automated").lower()
    if mode == "physical":
        return "physical"
    if mode == "both":
        # Prefer email if the journey offer was accepted on the application; physical otherwise.
        return "email" if (payload.get("journey") or {}).get("offer_accepted") else "physical"
    return "email"


def _record_offer_letter_accepted(payload: dict[str, Any], *, method: str | None = None) -> None:
    """Branch keeps the paper letter — portal only records acceptance + how it was accepted."""
    rows = payload.get("workflow") if isinstance(payload.get("workflow"), list) else []
    if any(isinstance(row, dict) and row.get("title") == "Offer Letter accepted" for row in rows):
        return
    how = method or _offer_acceptance_method(payload)
    detail = (
        "Accepted via physical signed offer letter at the branch."
        if how == "physical"
        else "Accepted via customer email / journey link."
    )
    _stamp(payload, "offer_letter_accepted")
    _append_workflow(payload, "Offer Letter accepted", detail)
    journey = payload.setdefault("journey", {})
    if isinstance(journey, dict):
        journey["offer_accepted"] = True
        journey["acceptance_method"] = how
        journey.setdefault("accepted_at", payload.get("timestamps", {}).get("offer_letter_accepted"))


def refresh_journey_status(db: Session, case: FiDeskCase) -> FiDeskCase:
    payload = _parse_payload(case.payload_json)
    journey = payload.get("journey")
    if not isinstance(journey, dict) or not journey.get("application_id"):
        return case
    accepted = _journey_offer_accepted(db, payload)
    accepted_at = journey.get("accepted_at")
    if accepted and not accepted_at:
        from tawarruq.models.application import FinancingApplication

        application = db.get(FinancingApplication, journey["application_id"])
        if application and application.offer and application.offer.accepted_at:
            accepted_at = application.offer.accepted_at.isoformat()
    if journey.get("offer_accepted") != accepted or journey.get("accepted_at") != accepted_at:
        journey["offer_accepted"] = accepted
        if accepted_at:
            journey["accepted_at"] = accepted_at
        payload["journey"] = journey
        if accepted:
            _record_offer_letter_accepted(payload, method="email")
        case.payload_json = _dump_payload(payload)
    elif accepted:
        _record_offer_letter_accepted(payload, method=str(journey.get("acceptance_method") or "email"))
        case.payload_json = _dump_payload(payload)
    return auto_progress_case(db, case)


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


def _append_workflow(
    payload: dict[str, Any],
    title: str,
    detail: str,
    *,
    cert_kinds: list[str] | None = None,
) -> None:
    rows = payload.setdefault("workflow", [])
    if not isinstance(rows, list):
        rows = []
        payload["workflow"] = rows
    rows.append(
        {
            "at": _now().isoformat(),
            "title": title,
            "detail": detail,
            "certificates": list(cert_kinds or []),
        }
    )


def _notify_approver(db: Session, case: FiDeskCase, approver: OpsUser, institution: Institution) -> None:
    from tawarruq.config import get_settings
    from tawarruq.services.customer_notify_service import _send_smtp, normalize_email

    to_email = normalize_email(approver.email)
    if not to_email:
        return
    payload = _parse_payload(case.payload_json)
    orig = payload.get("origination") or {}
    portal = (get_settings().portal_public_url or "https://ops.buruujfintech.com").rstrip("/")
    subject = f"Approval needed · {orig.get('customer_name') or case.id[:8]}"
    body = (
        f"Assalamu alaikum {approver.full_name or 'Approver'},\n\n"
        f"{institution.name} has a facility waiting for your decision.\n\n"
        f"Customer: {orig.get('customer_name')}\n"
        f"Email: {orig.get('customer_email')}\n"
        f"Phone: {orig.get('customer_phone')}\n"
        f"Amount: {orig.get('approved_facility_amount')}\n"
        f"Profit: {orig.get('profit')}\n"
        f"Commodity: {orig.get('facility_product_type')}\n"
        f"Offer letter: {orig.get('offer_letter_mode')}\n\n"
        f"Open: {portal}/origination?case={case.id}\n\n"
        "Buruuj Fintech — BTI Tawarruq Engine\n"
    )
    try:
        mail_dir = get_settings().customer_mail_path / "desk_approvals"
        mail_dir.mkdir(parents=True, exist_ok=True)
        (mail_dir / f"{case.id}-approval.txt").write_text(
            f"To: {to_email}\nSubject: {subject}\n\n{body}",
            encoding="utf-8",
        )
    except Exception:
        pass
    try:
        _send_smtp(to_email, subject, body)
    except Exception:
        pass


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
    name = str(payload.customer_name or "").strip()
    email = str(payload.customer_email or "").strip()
    phone = str(payload.customer_phone or "").strip()
    missing = [
        field
        for field, value in (
            ("customer_name", name),
            ("customer_email", email),
            ("customer_phone", phone),
            ("approved_facility_amount", payload.approved_facility_amount),
            ("profit", payload.profit),
        )
        if not str(value or "").strip()
    ]
    if missing:
        raise HTTPException(status_code=400, detail=f"Complete origination fields: {', '.join(missing)}")
    product = str(payload.facility_product_type or "Airtime").strip() or "Airtime"
    allowed = {"airtime", "palm oil", "other"}
    if product.lower() not in allowed:
        raise HTTPException(status_code=400, detail="Commodity type must be Airtime, Palm Oil, or Other")
    # Canonical labels
    product = {"airtime": "Airtime", "palm oil": "Palm Oil", "other": "Other"}[product.lower()]
    offer_mode = str(payload.offer_letter_mode or "automated").strip().lower() or "automated"
    if offer_mode not in {"physical", "automated", "both"}:
        raise HTTPException(status_code=400, detail="Offer letter must be physical, automated, or both")
    try:
        amount = float(str(payload.approved_facility_amount).replace(",", "").strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Approved facility amount must be a number")
    if amount < 0:
        raise HTTPException(status_code=400, detail="Approved facility amount cannot be negative")
    try:
        profit_amount = float(str(payload.profit or "").replace(",", "").strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Profit must be a number")
    if profit_amount < 0:
        raise HTTPException(status_code=400, detail="Profit cannot be negative")
    try:
        term_months = int(str(payload.term_months or "12").strip())
    except ValueError:
        raise HTTPException(status_code=400, detail="Repayment period must be a whole number of months")
    if term_months < 1:
        raise HTTPException(status_code=400, detail="Repayment period must be at least 1 month")
    from tawarruq.services.offer_letter_service import compute_offer_figures

    figures = compute_offer_figures(cost_price=amount, profit=profit_amount, term_months=term_months)
    fields = payload.model_dump()
    fields.pop("institution_id", None)
    fields.pop("assigned_approver_id", None)
    fields["customer_name"] = name
    fields["customer_email"] = email
    fields["customer_phone"] = phone
    fields["facility_product_type"] = product
    fields["offer_letter_mode"] = offer_mode
    fields["term_months"] = str(term_months)
    fields["cost_price"] = str(figures["cost_price"])
    fields["profit_margin"] = str(figures["profit_margin"])
    fields["contract_price"] = str(figures["contract_price"])
    fields["monthly_installment"] = str(figures["monthly_installment"])
    fields["document_type"] = str(payload.document_type or "").strip() or "Not provided"
    fields["customer_id"] = str(payload.customer_id or "").strip() or email
    seller = {
        "Airtime": "Safaricom",
        "Palm Oil": "Bursa Malaysia Islamic Services",
        "Other": "Commodity supplier",
    }[product]
    body = {
        "origination": fields,
        "initiate": {
            "commodity": product,
            "commodity_quantity": payload.approved_facility_amount,
            "commodity_seller": seller,
            "commodity_buyer": institution.name,
            "commodity_agent": "Buruuj Fintech",
            "payment_reference": f"txn-{secrets.token_hex(3)}",
        },
        "timestamps": {},
        "workflow": [],
    }
    _stamp(body, "origination_submitted")
    _append_workflow(
        body,
        "Origination submitted",
        f"{name} · {product} · amount {payload.approved_facility_amount} · profit {payload.profit}",
    )
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
    _notify_approver(db, case, approver, institution)
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
        _append_workflow(
            payload,
            "FI Approver approved",
            comments.strip() or "Approved. Customer journey and trade steps follow the offer letter mode.",
        )
        case.payload_json = _dump_payload(payload)
        _attach_customer_journey(db, case)
        payload = _parse_payload(case.payload_json)
        details = "FI Approver approved origination"
    elif decision == "return":
        case.status = "returned"
        case.current_step = 1
        _stamp(payload, "returned")
        note = comments.strip() or "Returned for changes."
        _append_workflow(payload, "FI Approver returned", note)
        details = "FI Approver returned origination"
    else:
        raise HTTPException(status_code=400, detail="Decision must be approve or return")
    case.approval_comments = comments
    case.payload_json = _dump_payload(payload)
    _audit(db, case, 2, actor.email, details, {"decision": decision, "comments": comments})
    if decision == "approve":
        auto_progress_case(db, case)
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
        product = str(orig.get("facility_product_type") or current.get("commodity") or "Airtime")
        seller = {
            "Airtime": "Safaricom",
            "Palm Oil": "Bursa Malaysia Islamic Services",
            "Other": "Commodity supplier",
        }.get(product, "Commodity supplier")
        current.setdefault("commodity", product)
        current.setdefault("commodity_quantity", orig.get("approved_facility_amount"))
        current.setdefault("commodity_seller", seller)
        current.setdefault("commodity_agent", "Buruuj Fintech")
        if not str(current.get("purchase_complete") or "").lower() in {"yes", "true", "1"}:
            raise HTTPException(status_code=400, detail="Mark purchase complete Yes before leaving Initiate Tawarruq")
        _stamp(payload, "purchase")
        current.setdefault("purchase_timestamp", payload["timestamps"].get("purchase"))
        _append_workflow(
            payload,
            "Commodity purchase",
            f"{product} purchased via {current.get('commodity_seller')}.",
            cert_kinds=["purchase"],
        )
    if step == 4:
        initiate = payload.get("initiate") or {}
        orig = payload.get("origination") or {}
        if not _journey_offer_accepted(db, payload):
            raise HTTPException(status_code=400, detail="Offer Letter must be accepted first (physical branch sign or customer email)")
        _record_offer_letter_accepted(payload)
        institution_name = case.institution.name if case.institution else "Institution"
        commodity = str(initiate.get("commodity") or orig.get("facility_product_type") or "Airtime")
        units = str(
            current.get("units")
            or current.get("commodity_units")
            or initiate.get("commodity_quantity")
            or orig.get("approved_facility_amount")
            or "1"
        )
        loan = str(orig.get("approved_facility_amount") or initiate.get("commodity_quantity") or "0")
        profit = str(current.get("profit") or orig.get("profit") or "0")
        try:
            total_price = f"{float(str(loan).replace(',', '')) + float(str(profit).replace(',', '')):.2f}"
        except ValueError:
            total_price = str(orig.get("contract_price") or loan)
        # Bank sells the commodity to the customer (no cost-breakdown in the narrative).
        seller = institution_name
        buyer = str(orig.get("customer_name") or "Customer")
        current["sale_status"] = "Complete"
        current["seller_name"] = seller
        current["buyer_name"] = buyer
        current["buyer_email"] = orig.get("customer_email")
        current["buyer_phone"] = orig.get("customer_phone")
        current["commodity"] = commodity
        current["units"] = units
        current["total_price"] = total_price
        current["deferred_sale_price"] = total_price
        current["cost_price"] = loan
        current["profit"] = profit
        facility_account = str(current.get("facility_account") or "").strip() or f"FAC-{case.id.replace('-', '')[:8]}"
        installments_raw = str(current.get("repayment_installments") or orig.get("term_months") or "12").strip()
        try:
            installments = max(1, int(installments_raw))
        except ValueError:
            installments = 12
        today = datetime.now(UTC).date()
        first_due = str(current.get("first_installment_due_date") or "").strip() or (today + timedelta(days=30)).isoformat()
        last_due = str(current.get("last_installment_due_date") or "").strip() or (today + timedelta(days=30 * installments)).isoformat()
        current["facility_account"] = facility_account
        current["repayment_installments"] = str(installments)
        current["first_installment_due_date"] = first_due
        current["last_installment_due_date"] = last_due
        _stamp(payload, "sale")
        current.setdefault("sale_timestamp", payload["timestamps"].get("sale"))
        _append_workflow(
            payload,
            "Murabaha sale",
            (
                f"Bank sold {commodity} ({units} units) to the customer. "
                f"Total price of the commodity: KES {total_price}. "
                f"Seller: {seller}. Buyer: {buyer}."
            ),
            cert_kinds=["murabahah"],
        )
        # Drop resale appointment, resale proceeds, and clearing — facility completes here.
        complete_bucket = payload.get("complete") if isinstance(payload.get("complete"), dict) else {}
        complete_bucket["final_status"] = "Complete"
        payload["complete"] = complete_bucket
        _stamp(payload, "complete")
        _append_workflow(
            payload,
            "Facility complete",
            "Trade certificates are ready for the customer.",
            cert_kinds=["purchase", "murabahah", "complete"],
        )
        case.status = "complete"
        case.current_step = 8
    if step in {5, 6, 7}:
        # Legacy steps removed from the live desk flow.
        raise HTTPException(
            status_code=400,
            detail="Resale appointment, resale proceeds, and clearing are no longer part of this desk",
        )
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
    _notify_desk_step(db, case, step)
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
    if email:
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


def _journey_offer_accepted(db: Session, payload: dict[str, Any]) -> bool:
    from tawarruq.models.application import FinancingApplication

    application_id = (payload.get("journey") or {}).get("application_id")
    if not application_id:
        return False
    application = db.get(FinancingApplication, application_id)
    return bool(application and application.offer and application.offer.accepted_at)


def _desk_contact_phone(email: str, case_id: str) -> str:
    compact = "".join(ch for ch in f"{case_id}{email}" if ch.isalnum())[-9:].ljust(9, "0")
    return f"+254{compact}"


def _hidden_step_fields(case: FiDeskCase, step: int, payload: dict[str, Any]) -> dict[str, Any]:
    orig = payload.get("origination") or {}
    today = datetime.now(UTC).date()
    short = case.id.replace("-", "")[:8]
    if step == 3:
        return {"purchase_complete": "Yes"}
    if step == 4:
        return {
            "profit": str(orig.get("profit") or ""),
            "offer_reference": f"OFF-{short}",
            "contract_reference": f"CON-{short}",
            "facility_account": f"FAC-{short}",
            "repayment_installments": "12",
            "first_installment_due_date": (today + timedelta(days=30)).isoformat(),
            "last_installment_due_date": (today + timedelta(days=365)).isoformat(),
        }
    if step == 6:
        return {
            "customer_account_number": f"CASA-{short}",
            "customer_branch": "Head office",
        }
    if step == 7:
        return {"settlement_ref": f"CLR-{short}"}
    return {}


def auto_progress_case(db: Session, case: FiDeskCase) -> FiDeskCase:
    if case.status in {"pending_approval", "returned", "complete"}:
        return case
    if case.current_step == 3:
        complete_step(db, case, 3, _hidden_step_fields(case, 3, _parse_payload(case.payload_json)), actor="system")
    payload = _parse_payload(case.payload_json)
    if not _journey_offer_accepted(db, payload):
        return case
    _record_offer_letter_accepted(payload)
    case.payload_json = _dump_payload(payload)
    # After offer accept: Murabaha sale only (steps 5–7 dropped).
    if case.status != "complete" and case.current_step == 4:
        complete_step(db, case, 4, _hidden_step_fields(case, 4, _parse_payload(case.payload_json)), actor="system")
    return case


def progress_cases_for_application(db: Session, application_id: str) -> None:
    rows = db.query(FiDeskCase).filter(FiDeskCase.status.in_(["approved", "in_progress"])).all()
    for case in rows:
        journey_id = (_parse_payload(case.payload_json).get("journey") or {}).get("application_id")
        if journey_id == application_id:
            refresh_journey_status(db, case)


def _attach_customer_journey(db: Session, case: FiDeskCase) -> None:
    from decimal import Decimal

    from tawarruq.enums import ApplicationStatus, AuditActor
    from tawarruq.models.application import FinancingOffer
    from tawarruq.models.customer import Customer
    from tawarruq.services.application_service import create_application, generate_customer_ref
    from tawarruq.services.customer_notify_service import notify_offer_ready
    from tawarruq.services.customer_service import link_customer_to_application

    payload = _parse_payload(case.payload_json)
    if (payload.get("journey") or {}).get("application_id"):
        return
    orig = payload.get("origination") or {}
    phone = str(orig.get("customer_phone") or "").strip()
    email = str(orig.get("customer_email") or "").strip()
    name = str(orig.get("customer_name") or "").strip()
    national_id = str(orig.get("customer_id") or "").strip()
    amount = Decimal(str(orig.get("approved_facility_amount") or "0"))
    profit = Decimal(str(orig.get("profit") or "0"))
    customer = None
    if email:
        customer = (
            db.query(Customer)
            .filter(Customer.institution_id == case.institution_id, Customer.email == email)
            .first()
        )
    if not customer and phone:
        customer = (
            db.query(Customer)
            .filter(Customer.institution_id == case.institution_id, Customer.phone == phone)
            .first()
        )
    if not customer:
        phone = phone or _desk_contact_phone(email, case.id)
        customer = Customer(
            institution_id=case.institution_id,
            phone=phone,
            email=email or None,
            full_name=name or email or "Customer",
            national_id=national_id or None,
            wallet_number=phone,
        )
        db.add(customer)
        db.flush()
    elif email and not customer.email:
        customer.email = email
    institution = case.institution or db.get(Institution, case.institution_id)
    commodity = str(orig.get("facility_product_type") or "Airtime")
    offer_mode = str(orig.get("offer_letter_mode") or "automated").lower()
    try:
        term_months = int(str(orig.get("term_months") or "12").strip())
    except ValueError:
        term_months = 12
    if term_months < 1:
        term_months = 12
    application = create_application(
        db,
        customer_ref=generate_customer_ref(db, institution) if institution else None,
        customer_name=name,
        currency="KES",
        amount_requested=amount,
        term_months=term_months,
        purpose=f"Origination desk {commodity} tawarruq",
        institution_id=case.institution_id,
        actor=AuditActor.HUMAN,
    )
    link_customer_to_application(db, application.id, customer.id)
    offer = FinancingOffer(
        application_id=application.id,
        cost_price=amount,
        profit_amount=profit,
        total_payable=amount + profit,
    )
    application.status = ApplicationStatus.OFFER_PENDING
    db.add(offer)
    db.flush()
    db.refresh(application, attribute_names=["customer", "institution", "offer"])
    # Physical offer letter stays at the branch — record acceptance only (no portal document access).
    if offer_mode == "physical":
        offer.accepted_at = _now()
        application.status = ApplicationStatus.OFFER_ACCEPTED
        payload["journey"] = {
            "application_id": application.id,
            "customer_ref": application.customer_ref,
            "customer_id": customer.id,
            "offer_accepted": True,
            "accepted_at": offer.accepted_at.isoformat(),
            "offer_letter_mode": offer_mode,
            "acceptance_method": "physical",
        }
        _record_offer_letter_accepted(payload, method="physical")
    else:
        notify_offer_ready(db, application)
        _append_workflow(
            payload,
            "Customer offer emailed",
            "Customer journey link sent. Waiting for Offer Letter acceptance via email."
            if offer_mode == "automated"
            else "Customer journey link sent; a physical branch signature may also be used.",
        )
        payload["journey"] = {
            "application_id": application.id,
            "customer_ref": application.customer_ref,
            "customer_id": customer.id,
            "offer_accepted": False,
            "accepted_at": None,
            "offer_letter_mode": offer_mode,
        }
    case.payload_json = _dump_payload(payload)


def resend_certificates(db: Session, case: FiDeskCase, kind: str | None = None) -> dict[str, Any]:
    """Re-email one step PDF (kind) or all trade certificates."""
    from tawarruq.services.certificate_mail_service import desk_certificate_attachment, desk_step_attachments
    from tawarruq.services.customer_notify_service import notify_step_ready

    payload = _parse_payload(case.payload_json)
    orig = payload.get("origination") or {}
    journey = payload.get("journey") or {}
    email = str(orig.get("customer_email") or "").strip()
    if not email:
        raise HTTPException(status_code=400, detail="This case has no customer email")
    key = str(kind or "").strip().lower() or None
    if key:
        one = desk_certificate_attachment(case, key)
        if not one:
            raise HTTPException(status_code=404, detail=f"No certificate for kind {key}")
        attachments = [one]
        title = f"Your {key} certificate"
        body_line = f"The {key} certificate for this facility is attached again."
        label = key
    else:
        attachments = desk_step_attachments(case, 8)
        if not attachments:
            attachments = desk_step_attachments(case, 4) or desk_step_attachments(case, 3)
        title = "Your Tawarruq certificates"
        body_line = "All trade certificates for this facility are attached again."
        label = "all"
    notify_step_ready(
        db,
        email=email,
        customer_name=orig.get("customer_name"),
        customer_ref=str(journey.get("customer_ref") or orig.get("customer_id") or case.id[:8]),
        title=title,
        body_line=body_line,
        institution_name=case.institution.name if case.institution else None,
        attachments=attachments,
    )
    _append_workflow(payload, "Certificates resent", f"Emailed ({label}) again to {email}.")
    case.payload_json = _dump_payload(payload)
    return {"emailed": True, "to": email, "attachments": len(attachments), "kind": label}


def _notify_desk_step(db: Session, case: FiDeskCase, step: int) -> None:
    from tawarruq.services.certificate_mail_service import desk_step_attachments
    from tawarruq.services.customer_notify_service import notify_step_ready

    payload = _parse_payload(case.payload_json)
    orig = payload.get("origination") or {}
    journey = payload.get("journey") or {}
    titles = {
        3: ("Tawarruq purchase", "The commodity purchase is complete."),
        4: ("Murabaha sale", "The bank has sold the commodity to you. Certificates are attached."),
    }
    if step not in titles:
        return
    title, line = titles[step]
    # After Murabaha the facility is complete — send all certs with the sale mail.
    attach_step = 8 if step == 4 else step
    notify_step_ready(
        db,
        email=orig.get("customer_email"),
        customer_name=orig.get("customer_name"),
        customer_ref=str(journey.get("customer_ref") or orig.get("customer_id") or case.id[:8]),
        title=title,
        body_line=line,
        institution_name=case.institution.name if case.institution else None,
        attachments=desk_step_attachments(case, attach_step),
    )
