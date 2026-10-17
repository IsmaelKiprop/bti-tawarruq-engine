"""Third-party broker liquidation API (OTC desk / independent liquidator)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx

from tawarruq.integrations.base import IntegrationError, normalize_ke_phone
from tawarruq.integrations.config import InstitutionIntegrationProfile


@dataclass
class BrokerLiquidationRequest:
    transaction_id: str
    application_id: str
    commodity_code: str
    batch_id: str
    asset_ref_hash: str
    spot_amount: Decimal
    broker_code: str
    institution_code: str


@dataclass
class BrokerLiquidationResponse:
    success: bool
    external_ref: str | None = None
    certificate_number: str | None = None
    error_message: str | None = None


class BrokerLiquidationClient:
    """Live HTTP adapter to an independent third-party broker OTC API."""

    def __init__(self, profile: InstitutionIntegrationProfile) -> None:
        self.profile = profile

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.profile.broker_api_key:
            headers["Authorization"] = f"Bearer {self.profile.broker_api_key}"
        return headers

    def execute_liquidation(self, request: BrokerLiquidationRequest) -> BrokerLiquidationResponse:
        if not self.profile.broker_api_url:
            raise IntegrationError(
                f"Broker liquidation API not configured for institution {self.profile.institution_id}"
            )

        payload = {
            "transaction_id": request.transaction_id,
            "application_id": request.application_id,
            "commodity_code": request.commodity_code,
            "batch_id": request.batch_id,
            "asset_ref_hash": request.asset_ref_hash,
            "spot_amount": str(request.spot_amount),
            "broker_code": request.broker_code,
            "institution_code": request.institution_code,
        }
        url = f"{self.profile.broker_api_url.rstrip('/')}/v1/liquidation/execute"
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=payload, headers=self._headers())

        if response.status_code not in (200, 201):
            return BrokerLiquidationResponse(
                success=False,
                error_message=f"Broker API {response.status_code}: {response.text[:500]}",
            )

        data: dict[str, Any] = response.json()
        return BrokerLiquidationResponse(
            success=str(data.get("status", "success")).lower() in ("success", "confirmed", "completed"),
            external_ref=str(data.get("external_ref") or data.get("trade_id") or ""),
            certificate_number=str(data.get("certificate_number") or data.get("sale_ref") or ""),
        )


class MockBrokerLiquidationClient:
    """Simulated broker fill for mock/integration testing."""

    def execute_liquidation(self, request: BrokerLiquidationRequest) -> BrokerLiquidationResponse:
        ref = f"LIQ-{request.broker_code}-{request.transaction_id[:8]}"
        cert = f"SALE-{request.broker_code}-{request.asset_ref_hash[:8]}"
        return BrokerLiquidationResponse(success=True, external_ref=ref, certificate_number=cert)


def get_broker_client(profile: InstitutionIntegrationProfile) -> BrokerLiquidationClient | MockBrokerLiquidationClient:
    if profile.is_live and profile.broker_api_url:
        return BrokerLiquidationClient(profile)
    return MockBrokerLiquidationClient()
