"""Sedania As-Sidq Tawarruq Platform client (API spec v2.1).

Live paths:
  POST /api/v1/trading
  GET  /api/v1/trading/status?ref_no=
  POST /api/v1/cancellation/request
  GET  certificate URL from the callback (`/api/v1/streamPdf?...`)

HTTP 200 means the request was accepted at the transport layer. Business outcome
is always `status_code` in the JSON body. Final trade outcome arrives on the
Trading Callback API (or Get Trading Status if the callback is missed).
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from urllib.parse import urljoin

import httpx

from tawarruq.config import get_settings
from tawarruq.integrations.base import IntegrationError

logger = logging.getLogger(__name__)

UAT_BASE_URL = "https://twq-uat.assidqlink.com"
TRADING_PATH = "/api/v1/trading"
STATUS_PATH = "/api/v1/trading/status"
CANCEL_PATH = "/api/v1/cancellation/request"

CANCEL_REASONS = {
    "incorrect_customer_details",
    "incorrect_financing_amount",
    "incorrect_profit_rate",
    "others",
}

# Trading submit
STATUS_ACCEPTED = 200
STATUS_VALIDATION = 422
STATUS_FAILED = 500
# Callback / status
STATUS_COMPLETE = 200
STATUS_CANCELLATION_REJECTED = 201
STATUS_PENDING = 202
STATUS_KEEP = 203
STATUS_CANCELLATION_PENDING = 399
STATUS_CANCELED = 400
STATUS_NOT_FOUND = 404
# Cancel submit
STATUS_CANCEL_SUBMITTED = 202
STATUS_CANCEL_WINDOW_EXPIRED = 400
STATUS_TRANSACTION_NOT_COMPLETED = 401
STATUS_DUPLICATE = 409


def alphanumeric_ref(value: str, *, prefix: str = "BTI", limit: int = 100) -> str:
    cleaned = "".join(ch for ch in (value or "") if ch.isalnum())
    if not cleaned:
        cleaned = f"{int(time.time())}"
    ref = f"{prefix}{cleaned}" if not cleaned.upper().startswith(prefix) else cleaned
    return ref[:limit].upper()


def certificate_password(ref_no: str, institution_prefix: str | None = None) -> str:
    prefix = (institution_prefix or get_settings().sedania_institution_prefix or "BTI").strip()
    return f"{prefix}@{ref_no}"


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _number(value: Decimal | int | float | str) -> float | int:
    quant = Decimal(str(value))
    if quant == quant.to_integral_value():
        return int(quant)
    return float(quant)


def _aes_encrypt_field(plain: str, key_material: str) -> str:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.padding import PKCS7
    from os import urandom

    digest = hashlib.sha256(key_material.encode("utf-8")).digest()
    iv = urandom(16)
    padder = PKCS7(128).padder()
    padded = padder.update(plain.encode("utf-8")) + padder.finalize()
    encryptor = Cipher(algorithms.AES(digest), modes.CBC(iv)).encryptor()
    cipher = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(iv + cipher).decode("ascii")


@dataclass
class SedaniaTradeSubmit:
    ref_no: str
    cust_name: str
    cust_id: str
    trading_amount: Decimal
    product_code: str
    currency: str = "MYR"
    profit_rate_pct: Decimal | None = None
    profit_amount: Decimal | None = None
    selling_price: Decimal | None = None
    keep_commodity: str = "N"


@dataclass
class SedaniaCancelSubmit:
    ref_no: str
    reason: str
    other_reason: str | None = None


@dataclass
class SedaniaApiResult:
    ref_no: str
    status_code: int
    status_desc: str
    description: str | None = None
    errors: Any = None
    callback: dict[str, Any] | None = None
    request_id: int | str | None = None
    http_status: int = 200
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def accepted(self) -> bool:
        return self.status_code == STATUS_ACCEPTED

    @property
    def complete(self) -> bool:
        return self.status_code in {STATUS_COMPLETE, STATUS_KEEP} and self.status_desc in {
            "COMPLETE",
            "KEEP",
            "SUCCESS",
        }

    @property
    def keep(self) -> bool:
        return self.status_code == STATUS_KEEP or self.status_desc == "KEEP"

    @property
    def pending(self) -> bool:
        return self.status_code in {STATUS_PENDING, STATUS_CANCELLATION_PENDING, STATUS_CANCEL_SUBMITTED}

    @property
    def failed(self) -> bool:
        return self.status_code == STATUS_FAILED

    @property
    def canceled(self) -> bool:
        return self.status_code == STATUS_CANCELED or self.status_desc in {"CANCELED", "CANCELLED"}


def parse_asidq_response(data: dict[str, Any], *, http_status: int = 200) -> SedaniaApiResult:
    message = data.get("message") if isinstance(data.get("message"), dict) else {}
    callback = data.get("callback") if isinstance(data.get("callback"), dict) else None
    status_code = data.get("status_code", http_status)
    try:
        status_code = int(status_code)
    except (TypeError, ValueError):
        status_code = http_status
    description = message.get("description") if isinstance(message, dict) else None
    if description is None and isinstance(data.get("message"), str):
        description = data.get("message")
    return SedaniaApiResult(
        ref_no=str(data.get("ref_no") or ""),
        status_code=status_code,
        status_desc=str(data.get("status_desc") or ""),
        description=str(description) if description else None,
        errors=message.get("errors") if isinstance(message, dict) else data.get("errors"),
        callback=callback,
        request_id=data.get("request_id"),
        http_status=http_status,
        raw=data,
    )


class SedaniaAsSidqClient:
    """Live HTTP adapter for the published As-Sidq APIs."""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_url = (settings.sedania_api_url or "").rstrip("/")
        self.api_key = (settings.sedania_api_key or "").strip()
        self.sign_requests = bool(settings.sedania_sign_requests)
        self.encrypt_customer = bool(settings.sedania_encrypt_customer)
        self.aes_key = (settings.sedania_aes_key or settings.integration_encryption_key or "").strip()

    def _headers(self, body: bytes | None = None) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.sign_requests and body is not None:
            digest = hashlib.sha256(body).digest()
            headers["X-Req-Signature"] = base64.b64encode(digest).decode("ascii")
        return headers

    def _require_url(self) -> str:
        if not self.api_url or not self.api_key:
            raise IntegrationError("Sedania API is not configured. Set SEDANIA_API_URL and SEDANIA_API_KEY.")
        return self.api_url

    def _trade_body(self, request: SedaniaTradeSubmit) -> dict[str, Any]:
        if request.profit_amount is None and request.selling_price is None:
            raise IntegrationError("As-Sidq trading requires profit_amount or selling_price.")
        keep = (request.keep_commodity or "N").upper()
        if keep not in {"Y", "N"}:
            raise IntegrationError("keep_commodity must be Y or N.")
        cust_name = request.cust_name
        cust_id = request.cust_id
        if self.encrypt_customer:
            if not self.aes_key:
                raise IntegrationError("SEDANIA_ENCRYPT_CUSTOMER is on but SEDANIA_AES_KEY is empty.")
            cust_name = _aes_encrypt_field(cust_name, self.aes_key)
            cust_id = _aes_encrypt_field(cust_id, self.aes_key)
        payload: dict[str, Any] = {
            "ref_no": request.ref_no,
            "cust_name": cust_name,
            "cust_id": cust_id,
            "trading_amount": _number(request.trading_amount),
            "product_code": request.product_code,
            "keep_commodity": keep,
        }
        if request.currency:
            payload["currency"] = request.currency
        if request.profit_rate_pct is not None:
            payload["profit_rate"] = _number(request.profit_rate_pct)
        if request.profit_amount is not None:
            payload["profit_amount"] = _number(request.profit_amount)
        elif request.selling_price is not None:
            payload["selling_price"] = _number(request.selling_price)
        return payload

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> SedaniaApiResult:
        base = self._require_url()
        url = urljoin(base + "/", path.lstrip("/")) if path.startswith("http") else f"{base}{path}"
        body = _json_bytes(payload) if payload is not None else None
        headers = self._headers(body)
        with httpx.Client(timeout=60.0) as client:
            response = client.request(
                method,
                url,
                content=body,
                headers=headers,
                params=params,
            )
        try:
        data = response.json()
        except Exception as exc:
            raise IntegrationError(
                f"Sedania {path} returned {response.status_code}: {response.text[:500]}"
            ) from exc
        if not isinstance(data, dict):
            raise IntegrationError(f"Sedania {path} returned a non-object payload")
        return parse_asidq_response(data, http_status=response.status_code)

    def submit_trade(self, request: SedaniaTradeSubmit) -> SedaniaApiResult:
        result = self._request("POST", TRADING_PATH, payload=self._trade_body(request))
        if result.status_code == STATUS_VALIDATION:
            logger.warning("As-Sidq rejected duplicate or invalid ref_no=%s: %s", request.ref_no, result.description)
        return result

    def get_status(self, ref_no: str) -> SedaniaApiResult:
        return self._request("GET", STATUS_PATH, params={"ref_no": ref_no})

    def cancel(self, request: SedaniaCancelSubmit) -> SedaniaApiResult:
        if request.reason not in CANCEL_REASONS:
            raise IntegrationError("Cancellation reason is not in the As-Sidq list.")
        payload: dict[str, Any] = {"ref_no": request.ref_no, "reason": request.reason}
        if request.reason == "others":
            if not (request.other_reason or "").strip():
                raise IntegrationError("other_reason is required when reason is others.")
            payload["other_reason"] = request.other_reason.strip()
        return self._request("POST", CANCEL_PATH, payload=payload)

    def download_certificate(self, cert_url: str) -> bytes:
        if not cert_url:
            raise IntegrationError("As-Sidq callback did not include a certificate URL.")
        headers = self._headers()
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            response = client.get(cert_url, headers=headers)
        if response.status_code != 200:
            raise IntegrationError(f"As-Sidq certificate download returned {response.status_code}")
        return bytes(response.content)


def _mock_callback(
    request: SedaniaTradeSubmit,
    *,
    status_code: int,
    status_desc: str,
    trading_status: str,
) -> dict[str, Any]:
    keep = request.keep_commodity.upper() == "Y"
    cert_no: dict[str, str] = {
        "A": f"AC{request.ref_no[-12:]}",
        "B": f"BC{request.ref_no[-12:]}",
    }
    if not keep:
        cert_no["C"] = f"CC{request.ref_no[-12:]}"
    return {
        "ref_no": request.ref_no,
        "status_code": status_code,
        "status_desc": status_desc,
        "message": {"description": "Trading completed" if status_code in {200, 203} else status_desc},
        "callback": {
            "ref_no": request.ref_no,
            "trading_status": trading_status,
            "delivery_order_no": f"DO{request.ref_no[-16:]}",
            "cert_no": cert_no,
            "cert": f"https://sedania.example/api/v1/streamPdf?ref_no={request.ref_no}&leg=master&type=master_cert",
            "cust_name": request.cust_name,
            "cust_id": request.cust_id,
            "supplying_party": "TELECOMMUNICATION_AIRTIME_AGGREGATOR",
            "buying_party": "SEDANIA_RANDOM_PURCHASER",
            "issue_date": int(time.time()),
            "commodity_type": "TELCO_AIRTIME",
            "value": str(request.trading_amount),
            "unit": 1,
        },
    }


class MockSedaniaAsSidqClient:
    """In-memory As-Sidq stand-in. Completes immediately so mock desks stay synchronous."""

    _trades: dict[str, dict[str, Any]] = {}

    def submit_trade(self, request: SedaniaTradeSubmit) -> SedaniaApiResult:
        if request.ref_no in self._trades and self._trades[request.ref_no].get("submitted"):
            return parse_asidq_response(
                {
                    "ref_no": request.ref_no,
                    "status_code": STATUS_VALIDATION,
                    "status_desc": "VALIDATION FAILED",
                    "message": {"description": "Validation errors", "errors": "The ref no already exists"},
                }
            )
        keep = (request.keep_commodity or "N").upper() == "Y"
        final = _mock_callback(
            request,
            status_code=STATUS_KEEP if keep else STATUS_COMPLETE,
            status_desc="KEEP" if keep else "COMPLETE",
            trading_status="KEEP" if keep else "COMPLETE",
        )
        self._trades[request.ref_no] = {
            "submitted": True,
            "request": request,
            "final": final,
            "status_code": STATUS_PENDING,
            "cancel": None,
        }
        return parse_asidq_response(
            {
                "ref_no": request.ref_no,
                "status_code": STATUS_ACCEPTED,
                "status_desc": "SUCCESS",
                "message": {"description": "Trading data imported"},
            }
        )

    def get_status(self, ref_no: str) -> SedaniaApiResult:
        row = self._trades.get(ref_no)
        if not row:
            return parse_asidq_response(
                {
                    "ref_no": ref_no,
                    "status_code": STATUS_NOT_FOUND,
                    "status_desc": "NOT_FOUND",
                    "message": {"description": "Transaction not found or does not belong to your institution"},
                }
            )
        if row.get("cancel") == "pending":
            return parse_asidq_response(
                {
                    "ref_no": ref_no,
                    "status_code": STATUS_CANCELLATION_PENDING,
                    "status_desc": "CANCELLATION_PENDING",
                    "message": {"description": "Cancellation request is currently under review."},
                }
            )
        if row.get("cancel") == "canceled":
            payload = dict(row["final"])
            payload["status_code"] = STATUS_CANCELED
            payload["status_desc"] = "CANCELED"
            payload["message"] = {"description": "Trading transaction cancelled successfully."}
            if isinstance(payload.get("callback"), dict):
                payload["callback"] = {**payload["callback"], "trading_status": "CANCELED"}
            return parse_asidq_response(payload)
        return parse_asidq_response(row["final"])

    def cancel(self, request: SedaniaCancelSubmit) -> SedaniaApiResult:
        if request.reason not in CANCEL_REASONS:
            raise IntegrationError("Cancellation reason is not in the As-Sidq list.")
        row = self._trades.get(request.ref_no)
        if not row:
            return parse_asidq_response(
                {
                    "ref_no": request.ref_no,
                    "status_code": STATUS_NOT_FOUND,
                    "status_desc": "TRANSACTION_NOT_FOUND",
                    "message": {"description": "Transaction not found or does not belong to your institution"},
                }
            )
        if row.get("cancel"):
            return parse_asidq_response(
                {
                    "ref_no": request.ref_no,
                    "status_code": STATUS_DUPLICATE,
                    "status_desc": "DUPLICATE_REQUEST",
                    "message": {"description": "Cancellation request already exists for this transaction"},
                }
            )
        row["cancel"] = "canceled"
        return parse_asidq_response(
            {
                "ref_no": request.ref_no,
                "status_code": STATUS_CANCEL_SUBMITTED,
                "status_desc": "SUCCESS",
                "message": {
                    "description": "Cancellation request submitted successfully. Use the status checker API to monitor transaction status."
                },
                "request_id": 801,
                "status": "pending",
                "reason": request.reason,
            }
        )

    def download_certificate(self, cert_url: str) -> bytes:
        return b"%PDF-1.4 mock-asidq-certificate"

    def completed_payload(self, ref_no: str) -> dict[str, Any] | None:
        row = self._trades.get(ref_no)
        if not row:
            return None
        return self.get_status(ref_no).raw


def get_sedania_client() -> SedaniaAsSidqClient | MockSedaniaAsSidqClient:
    settings = get_settings()
    if settings.is_live_sedania:
        return SedaniaAsSidqClient()
    return MockSedaniaAsSidqClient()
