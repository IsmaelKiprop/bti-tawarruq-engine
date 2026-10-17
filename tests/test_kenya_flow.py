import os

os.environ["AMANAH_ENABLED"] = "false"
os.environ["KENYA_INTEGRATION_MODE"] = "mock"

import pytest
from fastapi.testclient import TestClient

from tawarruq.database import Base, SessionLocal, engine, init_db
from tawarruq.main import app
from tawarruq.services.seed_service import seed_kenya_defaults


@pytest.fixture
def client():
    from tawarruq.config import get_settings

    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    from tawarruq.services.application_service import get_or_create_default_institution

    get_or_create_default_institution(db)
    seed_kenya_defaults(db)
    db.commit()
    db.close()
    with TestClient(app) as test_client:
        yield test_client


def test_kenya_full_flow(client):
    customer = client.post(
        "/api/v1/kenya/customers",
        json={
            "phone": "254700111222",
            "full_name": "Test Customer",
            "email": "test.customer@example.com",
            "wallet_number": "254700111222",
        },
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]

    app_resp = client.post(
        "/api/v1/kenya/applications",
        json={
            "customer_id": customer_id,
            "amount_requested": "25000.00",
            "term_months": 3,
            "purpose": "Airtime float",
        },
    )
    assert app_resp.status_code == 201
    assert app_resp.json()["wad_accepted_at"]
    application_id = app_resp.json()["id"]

    flow = client.post(f"/api/v1/kenya/applications/{application_id}/run-full-flow")
    assert flow.status_code == 200
    data = flow.json()
    assert data["eligibility_passed"] is True
    assert data["murabaha_signed"] is True
    assert data["transaction_status"] == "completed"
    assert data["installments_total"] == 3
    assert data["current_phase"] == "phase_4_repayment"

    shariah = client.get(f"/api/v1/kenya/applications/{application_id}/shariah-audit")
    assert shariah.status_code == 200
    steps = {entry["step_id"] for entry in shariah.json()}
    assert "WAD_UNDERTAKING" in steps
    assert "ELIGIBILITY_CHECK" in steps
    assert "CONSTRUCTIVE_POSSESSION" in steps
    assert "WALLET_DISBURSEMENT" in steps

    status = client.get(f"/api/v1/kenya/applications/{application_id}/status")
    assert status.status_code == 200
    assert status.json()["wad_accepted"] is True

    journey = client.get(f"/api/v1/customer/applications/{application_id}/journey")
    assert journey.status_code == 200
    body = journey.json()
    docs = body["trade_documents"]
    assert body["term_months"] == 3
    assert body["steps"][6]["status"] == "done"
    assert body["steps"][6]["certificate"]["type"] == "bti_tawarruq_cert"
    assert body["steps"][7]["wallet_txn_id"]
    assert any(cert.get("type") == "bti_tawarruq_cert" for cert in body["certificates"])
    assert docs["purchase_order"].startswith("EPO-")
    assert docs["delivery_order"].startswith("DO-AIRTIME-SAFARICOM-")
    assert docs["commodity_label"] == "Safaricom airtime"
    assert docs["downloadable"] is True
    epo = client.get(
        f"/api/v1/customer/applications/{application_id}/trade-documents/purchase_order"
    )
    assert epo.status_code == 200, epo.text
    assert "Electronic Purchase Order" in epo.text
    assert docs["purchase_order"] in epo.text
    invoice = client.get(
        f"/api/v1/customer/applications/{application_id}/trade-documents/invoice"
    )
    assert invoice.status_code == 200
    do = client.get(f"/api/v1/customer/applications/{application_id}/trade-documents/do")
    assert do.status_code == 200
    assert docs["delivery_order"] in do.text
    assert "Safaricom airtime" in do.text
    from pathlib import Path

    from tawarruq.config import get_settings

    mailed = get_settings().customer_mail_path / f"{journey.json()['customer_ref']}-trade-docs.txt"
    assert mailed.exists()
    mailed_text = mailed.read_text(encoding="utf-8")
    assert "test.customer@example.com" in mailed_text
    assert "Safaricom airtime" in mailed_text
    assert docs["delivery_order"] in mailed_text

    repayments = client.get(f"/api/v1/kenya/applications/{application_id}/repayments")
    assert repayments.status_code == 200
    assert len(repayments.json()) == 3

    first = repayments.json()[0]["id"]
    paid = client.post(f"/api/v1/kenya/repayments/{first}/collect")
    assert paid.status_code == 200
    assert paid.json()["status"] == "paid"


def test_eligibility_failure_low_credit(client):
    customer = client.post(
        "/api/v1/kenya/customers",
        json={
            "phone": "254700333444",
            "full_name": "Low Credit",
            "wallet_number": "254700333444",
            "credit_score": 200,
        },
    )
    customer_id = customer.json()["id"]
    app_resp = client.post(
        "/api/v1/kenya/applications",
        json={
            "customer_id": customer_id,
            "amount_requested": "10000.00",
            "term_months": 3,
            "purpose": "Test",
        },
    )
    application_id = app_resp.json()["id"]
    elig = client.post(f"/api/v1/kenya/applications/{application_id}/eligibility")
    assert elig.status_code == 200
    assert elig.json()["eligibility_passed"] is False
