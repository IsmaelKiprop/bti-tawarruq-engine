"""Automated Kenya MNO Tawarruq flow demo against a running API."""

import httpx

BASE = "http://127.0.0.1:8000/api/v1"


def main() -> None:
    with httpx.Client(base_url=BASE, timeout=30.0) as client:
        customer = client.post(
            "/kenya/customers",
            json={
                "phone": "254712345678",
                "full_name": "Demo Customer",
                "wallet_number": "254712345678",
            },
        )
        customer.raise_for_status()
        customer_id = customer.json()["id"]
        print(f"Customer: {customer_id}")

        application = client.post(
            "/kenya/applications",
            json={
                "customer_id": customer_id,
                "amount_requested": "50000.00",
                "term_months": 6,
                "purpose": "MNO airtime float",
            },
        )
        application.raise_for_status()
        application_id = application.json()["id"]
        print(f"Application: {application_id}")

        flow = client.post(f"/kenya/applications/{application_id}/run-full-flow")
        flow.raise_for_status()
        print("Flow status:", flow.json())

        audit = client.get(f"/kenya/applications/{application_id}/shariah-audit")
        audit.raise_for_status()
        print(f"Shariah audit entries: {len(audit.json())}")
        for entry in audit.json():
            print(f"  - {entry['step_id']} hash={entry['payload_hash'][:16]}…")


if __name__ == "__main__":
    main()
