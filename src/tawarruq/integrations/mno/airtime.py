import hashlib
from typing import Any

import httpx

from tawarruq.integrations.base import IntegrationError, normalize_ke_phone
from tawarruq.integrations.config import InstitutionIntegrationProfile
from tawarruq.mno.base import (
    MnoPurchaseRequest,
    MnoPurchaseResponse,
    MnoPurchaseResult,
    PossessionVerifyRequest,
    PossessionVerifyResponse,
)


class SafaricomAirtimeClient:
    """Safaricom dealer / airtime partner API (per-institution credentials)."""

    def __init__(self, profile: InstitutionIntegrationProfile) -> None:
        self.profile = profile

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.profile.mno_safaricom_api_key:
            headers["Authorization"] = f"Bearer {self.profile.mno_safaricom_api_key}"
        return headers

    def purchase_airtime(self, request: MnoPurchaseRequest) -> MnoPurchaseResponse:
        if not self.profile.mno_safaricom_api_url:
            raise IntegrationError(
                f"Safaricom MNO API not configured for institution {self.profile.institution_id}"
            )

        payload = {
            "dealer_code": self.profile.mno_safaricom_dealer_code,
            "msisdn": normalize_ke_phone(request.customer_phone),
            "amount": int(request.amount),
            "reference": request.leg_id,
            "transaction_id": request.transaction_id,
            "institution_code": request.institution_code,
            "callback_url": self.profile.mno_possession_callback_url,
        }
        url = f"{self.profile.mno_safaricom_api_url.rstrip('/')}/v1/airtime/purchase"
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=payload, headers=self._headers())

        if response.status_code not in (200, 201, 202):
            return MnoPurchaseResponse(
                result=MnoPurchaseResult.FAILED,
                error_message=f"Safaricom API {response.status_code}: {response.text[:500]}",
            )

        data: dict[str, Any] = response.json()
        batch_id = str(data.get("batch_id") or data.get("BatchId") or data.get("reference") or request.leg_id)
        receipt_id = data.get("receipt_id") or data.get("ReceiptId")
        status = str(data.get("status") or data.get("Status") or "pending").lower()
        asset_hash = hashlib.sha256(f"{batch_id}:{receipt_id or ''}:{request.amount}".encode()).hexdigest()

        if status in ("completed", "confirmed", "success"):
            return MnoPurchaseResponse(
                result=MnoPurchaseResult.CONFIRMED,
                batch_id=batch_id,
                mno_receipt_id=str(receipt_id) if receipt_id else None,
                asset_ref_hash=asset_hash,
            )
        return MnoPurchaseResponse(
            result=MnoPurchaseResult.AWAITING_POSSESSION,
            batch_id=batch_id,
            mno_receipt_id=str(receipt_id) if receipt_id else None,
            asset_ref_hash=asset_hash,
        )

    def verify_possession(self, request: PossessionVerifyRequest) -> PossessionVerifyResponse:
        if not self.profile.mno_safaricom_api_url:
            raise IntegrationError("Safaricom MNO API URL not configured")

        url = f"{self.profile.mno_safaricom_api_url.rstrip('/')}/v1/airtime/possession/verify"
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                url,
                json={"batch_id": request.batch_id, "receipt_id": request.mno_receipt_id},
                headers=self._headers(),
            )

        if response.status_code != 200:
            return PossessionVerifyResponse(
                verified=False,
                error_message=f"Possession verify failed ({response.status_code}): {response.text[:300]}",
            )

        data = response.json()
        verified = str(data.get("status") or data.get("verified", "")).lower() in (
            "verified",
            "confirmed",
            "success",
            "true",
        )
        asset_hash = data.get("asset_ref_hash")
        if verified and not asset_hash:
            asset_hash = hashlib.sha256(f"{request.batch_id}:{request.mno_receipt_id}".encode()).hexdigest()
        return PossessionVerifyResponse(verified=verified, asset_ref_hash=asset_hash)


class AirtelAirtimeClient:
    """Airtel Kenya airtime / float partner API (per-institution credentials)."""

    def __init__(self, profile: InstitutionIntegrationProfile) -> None:
        self.profile = profile
        self._token: str | None = None

    def _get_token(self) -> str:
        if self._token:
            return self._token
        if not self.profile.mno_airtel_token_url:
            raise IntegrationError("Airtel token URL not configured")
        payload = {
            "client_id": self.profile.mno_airtel_client_id,
            "client_secret": self.profile.mno_airtel_client_secret,
            "grant_type": "client_credentials",
        }
        with httpx.Client(timeout=30.0) as client:
            response = client.post(self.profile.mno_airtel_token_url, json=payload)
        if response.status_code != 200:
            raise IntegrationError(f"Airtel OAuth failed: {response.text}")
        self._token = response.json()["access_token"]
        return self._token

    def purchase_airtime(self, request: MnoPurchaseRequest) -> MnoPurchaseResponse:
        if not self.profile.mno_airtel_api_url:
            raise IntegrationError("Airtel MNO API URL not configured")

        payload = {
            "msisdn": normalize_ke_phone(request.customer_phone),
            "amount": int(request.amount),
            "reference": request.leg_id,
            "callback_url": self.profile.mno_possession_callback_url,
        }
        url = f"{self.profile.mno_airtel_api_url.rstrip('/')}/v1/airtime/purchase"
        headers = {"Authorization": f"Bearer {self._get_token()}", "Content-Type": "application/json"}
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=payload, headers=headers)

        if response.status_code not in (200, 201, 202):
            return MnoPurchaseResponse(
                result=MnoPurchaseResult.FAILED,
                error_message=f"Airtel API {response.status_code}: {response.text[:500]}",
            )

        data = response.json()
        batch_id = str(data.get("batch_id") or request.leg_id)
        receipt_id = data.get("receipt_id")
        status = str(data.get("status", "pending")).lower()
        asset_hash = hashlib.sha256(f"{batch_id}:{receipt_id or ''}:{request.amount}".encode()).hexdigest()

        if status in ("completed", "confirmed", "success"):
            return MnoPurchaseResponse(
                result=MnoPurchaseResult.CONFIRMED,
                batch_id=batch_id,
                mno_receipt_id=str(receipt_id) if receipt_id else None,
                asset_ref_hash=asset_hash,
            )
        return MnoPurchaseResponse(
            result=MnoPurchaseResult.AWAITING_POSSESSION,
            batch_id=batch_id,
            mno_receipt_id=str(receipt_id) if receipt_id else None,
            asset_ref_hash=asset_hash,
        )

    def verify_possession(self, request: PossessionVerifyRequest) -> PossessionVerifyResponse:
        url = f"{self.profile.mno_airtel_api_url.rstrip('/')}/v1/airtime/possession/verify"
        headers = {"Authorization": f"Bearer {self._get_token()}", "Content-Type": "application/json"}
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                url,
                json={"batch_id": request.batch_id, "receipt_id": request.mno_receipt_id},
                headers=headers,
            )
        if response.status_code != 200:
            return PossessionVerifyResponse(verified=False, error_message=response.text[:300])
        data = response.json()
        verified = str(data.get("status", "")).lower() in ("verified", "confirmed", "success")
        return PossessionVerifyResponse(verified=verified, asset_ref_hash=data.get("asset_ref_hash"))


def get_airtime_client(mno_code: str, profile: InstitutionIntegrationProfile) -> SafaricomAirtimeClient | AirtelAirtimeClient:
    if "AIRTEL" in mno_code.upper():
        return AirtelAirtimeClient(profile)
    return SafaricomAirtimeClient(profile)
