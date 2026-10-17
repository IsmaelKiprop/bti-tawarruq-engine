"""Smoke-test the Kenya API sequence used by the Expo mobile app."""

from __future__ import annotations

import os
import sys
from datetime import datetime

import httpx

BASE = os.environ.get("MOBILE_API_BASE", "http://127.0.0.1:8000/api/v1").rstrip("/")
ROOT = BASE.replace("/api/v1", "")


def main() -> int:
    phone = f"2547{datetime.now().strftime('%H%M%S')}1"
    print(f"API: {BASE}")
    with httpx.Client(timeout=60.0) as client:
        health = client.get(f"{ROOT}/health")
        health.raise_for_status()
        print("health:", health.json().get("status"), "kenya:", health.json().get("kenya_integration_mode"))

        customer = client.post(
            f"{BASE}/kenya/customers",
            json={
                "phone": phone,
                "full_name": "Mobile Smoke Test",
                "wallet_number": phone,
                "wallet_provider": "mpesa",
            },
        )
        customer.raise_for_status()
        customer_id = customer.json()["id"]
        print("customer:", customer_id[:8])

        app = client.post(
            f"{BASE}/kenya/applications",
            json={
                "customer_id": customer_id,
                "amount_requested": "25000",
                "term_months": 3,
                "purpose": "Mobile smoke test float",
            },
        )
        app.raise_for_status()
        application_id = app.json()["id"]
        print("application:", application_id[:8])

        elig = client.post(f"{BASE}/kenya/applications/{application_id}/eligibility")
        elig.raise_for_status()
        assert elig.json().get("eligibility_passed") is True
        print("eligibility: passed")

        txn = client.post(f"{BASE}/kenya/transactions", json={"application_id": application_id})
        txn.raise_for_status()
        transaction_id = txn.json()["id"]

        purchase = client.post(f"{BASE}/kenya/transactions/{transaction_id}/purchase")
        purchase.raise_for_status()
        if purchase.json()["legs"][0]["status"] == "awaiting_possession":
            poss = client.post(f"{BASE}/kenya/transactions/{transaction_id}/possession", json={})
            poss.raise_for_status()
        print("phase1: purchase + possession")

        client.post(f"{BASE}/kenya/applications/{application_id}/offer", json={}).raise_for_status()
        client.post(f"{BASE}/kenya/applications/{application_id}/accept").raise_for_status()
        client.post(f"{BASE}/kenya/applications/{application_id}/murabaha").raise_for_status()
        client.post(
            f"{BASE}/kenya/applications/{application_id}/murabaha/sign",
            json={"signature_ref": "SMOKE-SIGN"},
        ).raise_for_status()
        print("phase2: offer + contract")

        client.post(f"{BASE}/kenya/transactions/{transaction_id}/transfer").raise_for_status()
        client.post(
            f"{BASE}/kenya/applications/{application_id}/wakala",
            json={"consent_ref": "SMOKE-WAKALA", "notes": "smoke test"},
        ).raise_for_status()
        settle = client.post(f"{BASE}/kenya/applications/{application_id}/complete-settlement")
        settle.raise_for_status()
        print("phase3: settlement", settle.json().get("installment_count"), "installments")

        status = client.get(f"{BASE}/kenya/applications/{application_id}/status")
        status.raise_for_status()
        print("status wallet_credited:", status.json().get("wallet_credited"))

        repayments = client.get(f"{BASE}/kenya/applications/{application_id}/repayments")
        repayments.raise_for_status()
        print("repayments:", len(repayments.json()))

    print("MOBILE API FLOW OK")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print("FAILED:", exc, file=sys.stderr)
        raise SystemExit(1) from exc
