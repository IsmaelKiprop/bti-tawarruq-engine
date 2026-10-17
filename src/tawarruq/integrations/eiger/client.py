"""Eiger Trading Platform client.

Eiger is a commodity Murabaha desk with web, trader, and API channels
(https://www.eigertrading.com/site/eiger-trading-platform/). Their production
paths are issued after onboarding. This adapter uses the same order/certificate
contract as the live BSAS client so credentials can drop in without changing
Amanah orchestration.
"""

import httpx

from tawarruq.bsas.base import BSASBackend, LegContext, LegExecutionResponse, LegExecutionResult
from tawarruq.config import get_settings


class EigerTradingBackend(BSASBackend):
    """Live (or sandbox) Eiger desk. Paths are config-driven until Eiger shares the contract."""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_url = (settings.eiger_api_url or "").rstrip("/")
        self.api_key = settings.eiger_api_key
        self.order_path = settings.eiger_order_path or "/v1/orders"
        self.certificate_path = settings.eiger_certificate_path or "/v1/certificates/{ref}"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def execute_leg(self, context: LegContext) -> LegExecutionResponse:
        if not self.api_url or not self.api_key:
            return LegExecutionResponse(
                result=LegExecutionResult.FAILED,
                error_message="Eiger API not configured. Set EIGER_API_URL and EIGER_API_KEY after onboarding.",
            )

        payload = {
            "desk": "eiger",
            "leg_number": context.leg_number,
            "transaction_ref": context.transaction_id,
            "application_id": context.application_id,
            "commodity_code": context.commodity_code,
            "product_code": context.resolved_product_code(),
            "amount": context.resolved_bid(),
            "bid_amount": context.resolved_bid(),
            "profit_amount": context.resolved_profit(),
            "murabaha_total": context.resolved_murabaha(),
            "currency": context.currency,
            "purchase_type": context.purchase_type or "A",
            "institution_code": context.institution_code,
            "institution_name": context.institution_name,
            "customer_ref": context.customer_ref,
            "end_customer_name": context.resolved_customer_name(),
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(f"{self.api_url}{self.order_path}", json=payload, headers=self._headers())
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            return LegExecutionResponse(
                result=LegExecutionResult.FAILED,
                error_message=f"Eiger API error: {exc}",
            )

        status = data.get("status", "confirmed")
        if status == "pending":
            return LegExecutionResponse(
                result=LegExecutionResult.AWAITING_CONFIRMATION,
                external_ref=data.get("external_ref") or data.get("order_id"),
            )

        return LegExecutionResponse(
            result=LegExecutionResult.CONFIRMED,
            external_ref=data.get("external_ref") or data.get("order_id"),
            certificate_number=data.get("certificate_number"),
            issuer=data.get("issuer", "EIGER"),
        )

    def get_certificate(self, external_ref: str) -> LegExecutionResponse | None:
        if not self.api_url or not self.api_key:
            return None
        path = self.certificate_path.replace("{ref}", external_ref)
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(f"{self.api_url}{path}", headers=self._headers())
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError:
            return None

        if data.get("status") != "confirmed":
            return LegExecutionResponse(
                result=LegExecutionResult.AWAITING_CONFIRMATION,
                external_ref=external_ref,
            )
        return LegExecutionResponse(
            result=LegExecutionResult.CONFIRMED,
            external_ref=external_ref,
            certificate_number=data.get("certificate_number"),
            issuer=data.get("issuer", "EIGER"),
        )
