from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SaccoExecuteRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "customer_id": "uuid-or-phone",
                    "amount": "50000.00",
                    "tenor": 6,
                    "callback_url": "https://sacco.example/api/tawarruq/callback",
                }
            ]
        }
    )

    customer_id: str = Field(..., description="Onboarded borrower UUID, phone, or national ID")
    amount: Decimal = Field(..., gt=0, description="Facility amount / spot purchase cost")
    tenor: int = Field(..., ge=1, le=120, description="Tenor in months")
    currency: str = Field("KES", min_length=3, max_length=8)
    profit_rate: Decimal | None = Field(
        None,
        ge=0,
        le=1,
        description="Optional Murabahah profit rate as a fraction 0–1. Defaults to Super Admin Sedania % Charge.",
    )
    callback_url: str | None = Field(
        None,
        description="SACCO CBS callback, typically POST /api/tawarruq/callback. Falls back to registered webhooks.",
    )
    client_request_id: str | None = Field(
        None,
        description="Optional idempotency key from the SACCO CBS.",
    )
    institution_id: str | None = None
    institution_code: str | None = Field(None, examples=["MWALIMU"])


class VaultCertificateRead(BaseModel):
    kind: str
    certificate_number: str
    source: str
    url: str
    source_url: str | None = None
    batch_id: str | None = None
    serial_numbers: list[str] = Field(default_factory=list)
    retention_until: datetime


class LegalStampRead(BaseModel):
    token_id: str
    signature: str
    kind: str


class SaccoExecuteRead(BaseModel):
    execution_id: str
    application_id: str | None = None
    customer_id: str
    institution_id: str
    amount: Decimal
    profit_amount: Decimal
    deferred_price: Decimal
    tenor_months: int
    currency: str
    status: str
    sedania_batch_id: str | None = None
    wad: LegalStampRead | None = None
    wakalah: LegalStampRead | None = None
    certificates: dict[str, VaultCertificateRead] = Field(default_factory=dict)
    callback_delivered: bool = False
    cash_disbursement: str = Field(
        "sacco_cbs",
        description="Buruuj never pays principal. The SACCO CBS disburses after receiving the certificates.",
    )
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
