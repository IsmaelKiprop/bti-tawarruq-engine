import base64
from datetime import UTC, datetime
from typing import Any

import httpx

from tawarruq.integrations.base import IntegrationError, normalize_ke_phone
from tawarruq.integrations.config import InstitutionIntegrationProfile


class DarajaClient:
    """Safaricom Daraja API client — OAuth, B2C disbursement, STK Push, transaction status."""

    def __init__(self, profile: InstitutionIntegrationProfile) -> None:
        self.profile = profile

    @property
    def base_url(self) -> str:
        if self.profile.mpesa_env == "production":
            return "https://api.safaricom.co.ke"
        return "https://sandbox.safaricom.co.ke"

    def _require_config(self, *keys: str) -> None:
        missing = [key for key in keys if not getattr(self.profile, key, None)]
        if missing:
            raise IntegrationError(
                f"M-Pesa Daraja not configured for institution {self.profile.institution_id}. "
                f"Missing: {', '.join(missing)}"
            )

    def get_access_token(self) -> str:
        self._require_config("mpesa_consumer_key", "mpesa_consumer_secret")
        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        auth = base64.b64encode(
            f"{self.profile.mpesa_consumer_key}:{self.profile.mpesa_consumer_secret}".encode()
        ).decode()
        with httpx.Client(timeout=30.0) as client:
            response = client.get(url, headers={"Authorization": f"Basic {auth}"})
        if response.status_code != 200:
            raise IntegrationError(f"Daraja OAuth failed ({response.status_code}): {response.text}")
        data = response.json()
        token = data.get("access_token")
        if not token:
            raise IntegrationError(f"Daraja OAuth returned no access_token: {data}")
        return token

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.get_access_token()}", "Content-Type": "application/json"}

    def b2c_payment(
        self,
        *,
        phone: str,
        amount: int | float,
        remarks: str,
        occasion: str,
        command_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_config(
            "mpesa_shortcode",
            "mpesa_initiator_name",
            "mpesa_security_credential",
            "mpesa_b2c_result_url",
            "mpesa_b2c_timeout_url",
        )
        payload = {
            "InitiatorName": self.profile.mpesa_initiator_name,
            "SecurityCredential": self.profile.mpesa_security_credential,
            "CommandID": command_id or self.profile.mpesa_b2c_command_id,
            "Amount": str(int(amount)),
            "PartyA": self.profile.mpesa_shortcode,
            "PartyB": normalize_ke_phone(phone),
            "Remarks": remarks[:100],
            "QueueTimeOutURL": self.profile.mpesa_b2c_timeout_url,
            "ResultURL": self.profile.mpesa_b2c_result_url,
            "Occasion": occasion[:100],
        }
        url = f"{self.base_url}/mpesa/b2c/v1/paymentrequest"
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=payload, headers=self._auth_headers())
        data = response.json()
        if response.status_code not in (200, 201) or data.get("errorCode"):
            raise IntegrationError(f"B2C request failed: {data}")
        return data

    def stk_push(
        self,
        *,
        phone: str,
        amount: int | float,
        account_reference: str,
        transaction_desc: str,
    ) -> dict[str, Any]:
        self._require_config("mpesa_shortcode", "mpesa_stk_passkey", "mpesa_stk_callback_url")
        timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
        password_raw = f"{self.profile.mpesa_shortcode}{self.profile.mpesa_stk_passkey}{timestamp}"
        password = base64.b64encode(password_raw.encode()).decode()
        payload = {
            "BusinessShortCode": self.profile.mpesa_shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": str(int(amount)),
            "PartyA": normalize_ke_phone(phone),
            "PartyB": self.profile.mpesa_shortcode,
            "PhoneNumber": normalize_ke_phone(phone),
            "CallBackURL": self.profile.mpesa_stk_callback_url,
            "AccountReference": account_reference[:12],
            "TransactionDesc": transaction_desc[:13],
        }
        url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=payload, headers=self._auth_headers())
        data = response.json()
        if response.status_code not in (200, 201) or str(data.get("ResponseCode", "0")) != "0":
            raise IntegrationError(f"STK Push failed: {data}")
        return data


def get_daraja_client(profile: InstitutionIntegrationProfile) -> DarajaClient:
    return DarajaClient(profile)
