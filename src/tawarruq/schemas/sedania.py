from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from tawarruq.enums import SedaniaAgencyRole, SedaniaDeliveryMode, SedaniaFlowVariant
from tawarruq.schemas.sacco import LegalStampRead, SaccoExecuteRead


class SedaniaFinancingRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "customer_id": "uuid-or-phone",
                    "amount": "10000.00",
                    "tenor": 12,
                    "currency": "MYR",
                    "flow_variant": "approved_wakeel",
                    "delivery_mode": "constructive",
                    "casa_account": "CASA-DIB-0001",
                    "appoint_sasc": True,
                }
            ]
        }
    )

    customer_id: str = Field(..., description="Onboarded borrower UUID, phone, or national ID")
    amount: Decimal = Field(..., gt=0, description="Facility amount / spot purchase cost")
    tenor: int = Field(..., ge=1, le=120, description="Tenor in months")
    currency: str = Field("MYR", min_length=3, max_length=8)
    profit_rate: Decimal | None = Field(
        None,
        ge=0,
        le=1,
        description="Optional Murabahah profit rate. Defaults to SEDANIA_DEFAULT_PROFIT_RATE.",
    )
    flow_variant: SedaniaFlowVariant = Field(
        SedaniaFlowVariant.APPROVED_WAKEEL,
        description="approved_wakeel is the BTI Advisory flow. aaoifi_rasul is the proposed AAOIFI messenger flow.",
    )
    delivery_mode: SedaniaDeliveryMode = Field(
        SedaniaDeliveryMode.CONSTRUCTIVE,
        description="constructive sells independently after qabd hukmi. physical keeps the commodity (qabd hakiki).",
    )
    appoint_sasc: bool = Field(
        True,
        description="Appoint SEDANIA As Salam Capital independently as wakeel or Rasul under the CMP T&C.",
    )
    casa_account: str | None = Field(
        None,
        description="Customer CASA to credit after muqassah (approved) or after the independent sale (AAOIFI).",
    )
    callback_url: str | None = None
    client_request_id: str | None = Field(None, description="Optional idempotency key")
    institution_id: str | None = None
    institution_code: str | None = Field(None, examples=["DIB"])


class SedaniaStepRead(BaseModel):
    n: int
    id: str
    title: str
    status: str
    detail: str
    documents: list[str] = Field(default_factory=list)


class SedaniaFinancingRead(SaccoExecuteRead):
    path: str = "bank_financing"
    flow_variant: str = SedaniaFlowVariant.APPROVED_WAKEEL
    delivery_mode: str = SedaniaDeliveryMode.CONSTRUCTIVE
    agency_role: str = SedaniaAgencyRole.WAKEEL
    agency_party: str = "SEDANIA_AS_SALAM_CAPITAL"
    appoint_sasc: bool = True
    purchase_order_ref: str | None = None
    commodity_invoice_ref: str | None = None
    delivery_order_ref: str | None = None
    trading_ecert_ref: str | None = None
    supplier_ref: str | None = None
    purchaser_ref: str | None = None
    muqassah_ref: str | None = None
    muqassah_at: datetime | None = None
    casa_account: str | None = None
    casa_ref: str | None = None
    casa_credited_at: datetime | None = None
    physical_delivery_requested: bool = False
    physical_delivery_status: str | None = None
    physical_delivery_notified_at: datetime | None = None
    repayment_settled_at: datetime | None = None
    cmp: LegalStampRead | None = None
    steps: list[SedaniaStepRead] = Field(default_factory=list)


class SedaniaDocumentIndex(BaseModel):
    kind: str
    label: str
    available: bool
    ref: str | None = None
    url: str | None = None


class SedaniaPhysicalDeliveryRequest(BaseModel):
    mark_settled: bool = Field(
        True,
        description="Physical delivery is arranged only after the deferred Murabahah price is fully settled.",
    )
