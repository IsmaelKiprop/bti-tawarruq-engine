#!/usr/bin/env python
"""Run the full Tawarruq flow against a local API server (mock mode)."""

import json
import sys
import httpx

BASE = "http://127.0.0.1:8000"
API = f"{BASE}/api/v1"


def step(name: str, method: str, path: str, **kwargs) -> dict:
    url = f"{BASE}{path}" if path.startswith("/health") else f"{API}{path}"
    print(f"\n--- {name} ---")
    print(f"{method} {url}")
    response = httpx.request(method, url, timeout=30.0, **kwargs)
    print(f"Status: {response.status_code}")
    try:
        data = response.json()
    except Exception:
        print(response.text)
        response.raise_for_status()
        return {}
    print(json.dumps(data, indent=2, default=str))
    response.raise_for_status()
    return data


def main() -> int:
    print("Buruuj Tawarruq Engine - Local flow test (mock mode)")
    print("=" * 50)

    try:
        httpx.get(f"{BASE}/health", timeout=5.0).raise_for_status()
    except httpx.HTTPError:
        print("\nERROR: API not running. Start it first:")
        print('  python -m tawarruq.cli serve --reload')
        return 1

    step("1. Health", "GET", "/health")

    app = step(
        "2. Create application",
        "POST",
        "/applications",
        json={
            "customer_ref": "CUST-DEMO-001",
            "amount_requested": "100000.00",
            "term_months": 12,
            "purpose": "Working capital (demo)",
        },
    )
    app_id = app["id"]

    step("3. Generate offer", "POST", f"/applications/{app_id}/offer", json={"profit_rate_pct": "5.0"})
    step("4. Accept offer", "POST", f"/applications/{app_id}/accept")

    txn = step(
        "5. Create transaction (mock)",
        "POST",
        "/transactions",
        json={"application_id": app_id, "mode": "mock", "commodity_code": "PALM_OIL"},
    )
    txn_id = txn["id"]

    for leg_name, leg_path in [
        ("6. Leg 1 purchase", "purchase"),
        ("7. Leg 2 transfer", "transfer"),
        ("8. Leg 3 sale", "sale"),
    ]:
        step(leg_name, "POST", f"/transactions/{txn_id}/legs/{leg_path}")

    detail = step("9. Full transaction status", "GET", f"/transactions/{txn_id}")
    assert detail["status"] == "completed", f"Expected completed, got {detail['status']}"
    assert all(leg["status"] == "confirmed" for leg in detail["legs"])

    step(
        "10. Disbursement",
        "POST",
        "/disbursements",
        json={"application_id": app_id, "transaction_id": txn_id},
    )

    audit = step("11. Audit trail", "GET", f"/audit?entity_id={txn_id}")
    assert len(audit) > 0

    print("\n" + "=" * 50)
    print("ALL STEPS PASSED")
    print(f"Application ID:  {app_id}")
    print(f"Transaction ID:  {txn_id}")
    print(f"Swagger UI:      {BASE}/docs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
