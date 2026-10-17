"""Airtel Money wallet disbursement (B2C payout)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx

from tawarruq.integrations.base import IntegrationError, normalize_ke_phone
from tawarruq.integrations.config import InstitutionIntegrationProfile


class AirtelMoneyClient:
    """Airtel Money disbursement API — OAuth + payout."""

    def __init__(self, profile: InstitutionIntegrationProfile) -> None:
        self.profile = profile
        self._token: str | None = None

    @property
    def configured(self) -> bool:
        return bool(
            self.profile.mno_airtel_api_url
            and self.profile.mno_airtel_token_url
            and self.profile.mno_airtel_client_id
            and self.profile.mno_airtel_client_secret
        )

    def _get_token(self) -> str:
        if self._token:
            return self._token
        payload = {
            "client_id": self.profile.mno_airtel_client_id,
            "client_secret": self.profile.mno_airtel_client_secret,
            "grant_type": "client_credentials",
        }
        with httpx.Client(timeout=30.0) as client:
            response = client.post(self.profile.mno_airtel_token_url, json=payload)
        if response.status_code != 200:
            raise IntegrationError(f"Airtel OAuth failed: {response.text[:300]}")
        self._token = response.json()["access_token"]
        return self._token

    def disburse(self, *, phone: str, amount: Decimal, reference: str, remarks: str) -> dict[str, Any]:
        if not self.configured:
            raise IntegrationError("Airtel Money disbursement not configured")

        url = f"{self.profile.mno_airtel_api_url.rstrip('/')}/v1/money/disburse"
        headers = {"Authorization": f"Bearer {self._get_token()}", "Content-Type": "application/json"}
        payload = {
            "msisdn": normalize_ke_phone(phone),
            "amount": float(amount),
            "reference": reference,
            "remarks": remarks,
        }
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=payload, headers=headers)
        if response.status_code not in (200, 201, 202):
            raise IntegrationError(f"Airtel disbursement {response.status_code}: {response.text[:500]}")
        return response.json()


def get_airtel_money_client(profile: InstitutionIntegrationProfile) -> AirtelMoneyClient:
    return AirtelMoneyClient(profile)
