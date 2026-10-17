import httpx

from tawarruq.bsas.base import BSASBackend, LegContext, LegExecutionResponse, LegExecutionResult
from tawarruq.config import get_settings


class LiveBSASBackend(BSASBackend):
    """Direct BSAS API integration (stub ready for real credentials)."""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_url = settings.bsas_live_api_url.rstrip("/")
        self.api_key = settings.bsas_live_api_key

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def execute_leg(self, context: LegContext) -> LegExecutionResponse:
        if not self.api_url or not self.api_key:
            return LegExecutionResponse(
                result=LegExecutionResult.FAILED,
                error_message="BSAS live API not configured. Set BSAS_LIVE_API_URL and BSAS_LIVE_API_KEY.",
            )

        endpoint_map = {
            "1": "/v1/purchase",
            "2": "/v1/transfer",
            "3": "/v1/sale",
        }
        endpoint = endpoint_map.get(context.leg_number)
        if not endpoint:
            return LegExecutionResponse(
                result=LegExecutionResult.FAILED,
                error_message=f"Unknown leg number: {context.leg_number}",
            )

        payload = {
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
                response = client.post(f"{self.api_url}{endpoint}", json=payload, headers=self._headers())
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            return LegExecutionResponse(
                result=LegExecutionResult.FAILED,
                error_message=f"BSAS API error: {exc}",
            )

        status = data.get("status", "confirmed")
        if status == "pending":
            return LegExecutionResponse(
                result=LegExecutionResult.AWAITING_CONFIRMATION,
                external_ref=data.get("external_ref"),
            )

        return LegExecutionResponse(
            result=LegExecutionResult.CONFIRMED,
            external_ref=data.get("external_ref"),
            certificate_number=data.get("certificate_number"),
            issuer=data.get("issuer", "BSAS"),
        )

    def get_certificate(self, external_ref: str) -> LegExecutionResponse | None:
        if not self.api_url or not self.api_key:
            return None
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    f"{self.api_url}/v1/certificates/{external_ref}",
                    headers=self._headers(),
                )
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
            issuer=data.get("issuer", "BSAS"),
        )
