"""Sedania As-Sidq trading client.

Sedania owns commodity order matching and inventory. Buruuj only calls purchase,
Murabahah transfer, and independent liquidation. Buruuj does not build the book.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import httpx

from tawarruq.config import get_settings
from tawarruq.integrations.base import IntegrationError


@dataclass
class SedaniaPurchaseRequest:
    execution_id: str
    institution_code: str
    customer_id: str
    amount: Decimal
    currency: str
    commodity: str = "AIRTIME_CREDIT"


@dataclass
class SedaniaMurabahahRequest:
    execution_id: str
    batch_id: str
    cost_price: Decimal
    profit_amount: Decimal
    deferred_price: Decimal
    currency: str
    customer_id: str
    tenor_months: int


@dataclass
class SedaniaLiquidateRequest:
    execution_id: str
    batch_id: str
    spot_amount: Decimal
    currency: str
    wakeel_ref: str


@dataclass
class SedaniaTradeResult:
    success: bool
    batch_id: str | None = None
    serial_numbers: list[str] = field(default_factory=list)
    certificate_number: str | None = None
    certificate_url: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None


class SedaniaAsSidqClient:
    """Live HTTP adapter for Sedania As-Sidq trading APIs."""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_url = (settings.sedania_api_url or "").rstrip("/")
        self.api_key = settings.sedania_api_key

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_url:
            raise IntegrationError("Sedania API is not configured. Set SEDANIA_API_URL and SEDANIA_API_KEY.")
        url = f"{self.api_url}{path}"
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=payload, headers=self._headers())
        if response.status_code not in (200, 201):
            raise IntegrationError(f"Sedania {path} returned {response.status_code}: {response.text[:500]}")
        data = response.json()
        if not isinstance(data, dict):
            raise IntegrationError(f"Sedania {path} returned a non-object payload")
        return data

    def purchase(self, request: SedaniaPurchaseRequest) -> SedaniaTradeResult:
        data = self._post(
            "/v1/trading/purchase",
            {
                "execution_id": request.execution_id,
                "institution_code": request.institution_code,
                "customer_id": request.customer_id,
                "amount": str(request.amount),
                "currency": request.currency,
                "commodity": request.commodity,
            },
        )
        return _parse_trade_result(data, default_kind="purchase")

    def transfer_murabahah(self, request: SedaniaMurabahahRequest) -> SedaniaTradeResult:
        data = self._post(
            "/v1/trading/transfer-murabahah",
            {
                "execution_id": request.execution_id,
                "batch_id": request.batch_id,
                "cost_price": str(request.cost_price),
                "profit_amount": str(request.profit_amount),
                "deferred_price": str(request.deferred_price),
                "currency": request.currency,
                "customer_id": request.customer_id,
                "tenor_months": request.tenor_months,
            },
        )
        return _parse_trade_result(data, default_kind="murabahah")

    def liquidate(self, request: SedaniaLiquidateRequest) -> SedaniaTradeResult:
        data = self._post(
            "/v1/trading/liquidate",
            {
                "execution_id": request.execution_id,
                "batch_id": request.batch_id,
                "spot_amount": str(request.spot_amount),
                "currency": request.currency,
                "wakeel_ref": request.wakeel_ref,
            },
        )
        return _parse_trade_result(data, default_kind="liquidation")


class MockSedaniaAsSidqClient:
    """Simulated Sedania fills for local and test runs. No order book is built here."""

    def purchase(self, request: SedaniaPurchaseRequest) -> SedaniaTradeResult:
        batch_id = f"SED-BATCH-{request.execution_id[:8].upper()}"
        serials = [f"ATU-{request.execution_id[:8].upper()}-{i:04d}" for i in range(1, 4)]
        number = f"CERT1-PURCHASE-{request.execution_id[:8].upper()}"
        payload = {
            "certificate_type": "purchase_confirmation",
            "title": "Certificate 1 (Purchase Confirmation)",
            "batch_id": batch_id,
            "serial_numbers": serials,
            "commodity": request.commodity,
            "amount": str(request.amount),
            "currency": request.currency,
            "institution_code": request.institution_code,
            "qabd_hukmi": True,
        }
        return SedaniaTradeResult(
            success=True,
            batch_id=batch_id,
            serial_numbers=serials,
            certificate_number=number,
            certificate_url=f"https://sedania.example/certificates/{number}",
            payload=payload,
        )

    def transfer_murabahah(self, request: SedaniaMurabahahRequest) -> SedaniaTradeResult:
        number = f"CERT2-MURABAHAH-{request.execution_id[:8].upper()}"
        payload = {
            "certificate_type": "murabahah_sale_receipt",
            "title": "Certificate 2 (Murabahah Sale Receipt)",
            "batch_id": request.batch_id,
            "cost_price": str(request.cost_price),
            "profit_amount": str(request.profit_amount),
            "deferred_price": str(request.deferred_price),
            "currency": request.currency,
            "customer_id": request.customer_id,
            "tenor_months": request.tenor_months,
        }
        return SedaniaTradeResult(
            success=True,
            batch_id=request.batch_id,
            certificate_number=number,
            certificate_url=f"https://sedania.example/certificates/{number}",
            payload=payload,
        )

    def liquidate(self, request: SedaniaLiquidateRequest) -> SedaniaTradeResult:
        number = f"CERT3-LIQUIDATION-{request.execution_id[:8].upper()}"
        payload = {
            "certificate_type": "sale_liquidation_confirmation",
            "title": "Certificate 3 (Sale & Liquidation Confirmation)",
            "batch_id": request.batch_id,
            "spot_amount": str(request.spot_amount),
            "currency": request.currency,
            "independent_buyer": "SEDANIA_TELCO_MARKET",
            "wakeel_ref": request.wakeel_ref,
            "bai_al_inah_avoided": True,
        }
        return SedaniaTradeResult(
            success=True,
            batch_id=request.batch_id,
            certificate_number=number,
            certificate_url=f"https://sedania.example/certificates/{number}",
            payload=payload,
        )


def _parse_trade_result(data: dict[str, Any], default_kind: str) -> SedaniaTradeResult:
    status = str(data.get("status", "success")).lower()
    ok = status in {"ok", "success", "confirmed", "completed"}
    serials = data.get("serial_numbers") or data.get("inventory_serial_numbers") or []
    if isinstance(serials, str):
        serials = [s.strip() for s in serials.split(",") if s.strip()]
    cert = data.get("certificate") if isinstance(data.get("certificate"), dict) else {}
    number = (
        data.get("certificate_number")
        or cert.get("number")
        or data.get("certificate_id")
        or f"SED-{default_kind.upper()}-{data.get('batch_id', 'NA')}"
    )
    url = data.get("certificate_url") or cert.get("url")
    return SedaniaTradeResult(
        success=ok,
        batch_id=str(data.get("batch_id") or data.get("batchId") or "") or None,
        serial_numbers=[str(item) for item in serials],
        certificate_number=str(number) if number else None,
        certificate_url=str(url) if url else None,
        payload=data,
        error_message=None if ok else str(data.get("error") or data.get("message") or "Sedania trade failed"),
    )


def get_sedania_client() -> SedaniaAsSidqClient | MockSedaniaAsSidqClient:
    settings = get_settings()
    if settings.is_live_sedania:
        return SedaniaAsSidqClient()
    return MockSedaniaAsSidqClient()
