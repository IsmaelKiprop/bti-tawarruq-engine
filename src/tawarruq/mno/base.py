from dataclasses import dataclass
from enum import StrEnum


class MnoPurchaseResult(StrEnum):
    CONFIRMED = "confirmed"
    AWAITING_POSSESSION = "awaiting_possession"
    FAILED = "failed"


@dataclass
class MnoPurchaseRequest:
    transaction_id: str
    leg_id: str
    mno_code: str
    amount: float
    institution_code: str
    customer_phone: str


@dataclass
class MnoPurchaseResponse:
    result: MnoPurchaseResult
    batch_id: str | None = None
    mno_receipt_id: str | None = None
    asset_ref_hash: str | None = None
    error_message: str | None = None


@dataclass
class PossessionVerifyRequest:
    batch_id: str
    mno_receipt_id: str
    mno_code: str = "AIRTIME_SAFARICOM"


@dataclass
class PossessionVerifyResponse:
    verified: bool
    asset_ref_hash: str | None = None
    error_message: str | None = None
