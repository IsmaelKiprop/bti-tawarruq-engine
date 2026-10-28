from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DeskApproverRead(BaseModel):
    id: str
    full_name: str
    email: str


class DeskCaseCreate(BaseModel):
    customer_id: str
    document_type: str
    customer_name: str
    customer_phone: str
    customer_email: str
    approved_facility_amount: str
    facility_product_type: str
    assigned_approver_id: str
    institution_id: str | None = None


class DeskCaseDecide(BaseModel):
    decision: str = Field(..., description="approve | return")
    comments: str = ""


class DeskStepWrite(BaseModel):
    fields: dict[str, Any] = Field(default_factory=dict)


class DeskOtpSend(BaseModel):
    purpose: str


class DeskOtpVerify(BaseModel):
    purpose: str
    code: str


class DeskOtpSendRead(BaseModel):
    purpose: str
    smtp_sent: bool = False
    dev_code: str | None = None
    expires_at: datetime | None = None


class DeskCaseRead(BaseModel):
    id: str
    institution_id: str
    institution_name: str | None = None
    current_step: int
    status: str
    assigned_approver_id: str | None = None
    assigned_approver_name: str | None = None
    requested_by_id: str | None = None
    requested_by_name: str | None = None
    approval_comments: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime | None = None


class DeskAuditRead(BaseModel):
    id: str
    timestamp: datetime
    step_id: str
    entity_id: str
    actor_from: str
    actor_to: str
    details: str | None = None
    institution_id: str | None = None
