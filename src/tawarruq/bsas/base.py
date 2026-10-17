from dataclasses import dataclass
from abc import ABC, abstractmethod
from enum import StrEnum

from tawarruq.enums import LegNumber


class LegExecutionResult(StrEnum):
    CONFIRMED = "confirmed"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    FAILED = "failed"


@dataclass
class LegExecutionResponse:
    result: LegExecutionResult
    external_ref: str | None = None
    certificate_number: str | None = None
    issuer: str = "BSAS"
    error_message: str | None = None
    manual_request_path: str | None = None
    bsas_fee: float | None = None


@dataclass
class LegContext:
    transaction_id: str
    leg_number: LegNumber
    commodity_code: str
    amount: float
    institution_code: str
    customer_ref: str
    # Bursa desk / BSAS packet fields (optional defaults for older call sites)
    institution_name: str = ""
    customer_name: str = ""
    bid_amount: float | None = None
    profit_amount: float | None = None
    murabaha_total: float | None = None
    currency: str = "KES"
    product_code: str = ""
    purchase_type: str = "A"
    application_id: str = ""

    def resolved_bid(self) -> float:
        return float(self.bid_amount if self.bid_amount is not None else self.amount)

    def resolved_profit(self) -> float:
        return float(self.profit_amount or 0.0)

    def resolved_murabaha(self) -> float:
        if self.murabaha_total is not None:
            return float(self.murabaha_total)
        return self.resolved_bid() + self.resolved_profit()

    def resolved_product_code(self) -> str:
        return self.product_code or self.commodity_code

    def resolved_customer_name(self) -> str:
        return self.customer_name or self.customer_ref


class BSASBackend(ABC):
    @abstractmethod
    def execute_leg(self, context: LegContext) -> LegExecutionResponse:
        pass

    @abstractmethod
    def get_certificate(self, external_ref: str) -> LegExecutionResponse | None:
        pass
