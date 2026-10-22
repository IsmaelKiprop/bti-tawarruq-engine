import os

os.environ["AMANAH_ENABLED"] = "false"
os.environ["KENYA_INTEGRATION_MODE"] = "mock"
os.environ["SEDANIA_MODE"] = "mock"

import pytest
from fastapi.testclient import TestClient

from tawarruq.database import Base, SessionLocal, engine, init_db
from tawarruq.main import app
from tawarruq.services.application_service import get_or_create_default_institution
from tawarruq.services.seed_service import seed_kenya_defaults


@pytest.fixture
def client():
    from tawarruq.config import get_settings

    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    get_or_create_default_institution(db)
    seed_kenya_defaults(db)
    db.commit()
    db.close()
    with TestClient(app) as test_client:
        yield test_client


def _dib(client: TestClient) -> dict:
    institutions = client.get("/api/v1/institutions").json()
    return next(item for item in institutions if item["code"] == "DIB")


def _onboard(client: TestClient, institution_id: str, phone: str = "60123450999") -> dict:
    resp = client.post(
        "/api/v1/kenya/customers",
        json={
            "institution_id": institution_id,
            "phone": phone,
            "full_name": "Amina Rahman",
            "wallet_number": "CASA-DIB-0001",
            "national_id": f"SED-{phone}",
            "email": "amina.rahman@example.com",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_approved_wakeel_runs_muqassah_and_credits_casa(client):
    bank = _dib(client)
    customer = _onboard(client, bank["id"])

    resp = client.post(
        "/api/v1/sedania/financing",
        json={
            "customer_id": customer["id"],
            "amount": "10000.00",
            "tenor": 12,
            "currency": "MYR",
            "flow_variant": "approved_wakeel",
            "delivery_mode": "constructive",
            "casa_account": "CASA-DIB-0001",
            "institution_id": bank["id"],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["path"] == "bank_financing"
    assert body["agency_role"] == "wakeel"
    assert body["agency_party"] == "SEDANIA_AS_SALAM_CAPITAL"
    assert body["cash_disbursement"] == "bank_casa"
    assert body["muqassah_ref"]
    assert body["casa_ref"]
    assert body["casa_account"] == "CASA-DIB-0001"
    assert body["purchase_order_ref"].startswith("PO-ASSIDQ-")
    assert body["commodity_invoice_ref"].startswith("INV-AIRTIME-")
    assert body["delivery_order_ref"].startswith("DO-AIRTIME-")
    assert body["trading_ecert_ref"].startswith("ECERT-ASSIDQ-")
    assert body["wakalah"]["token_id"].startswith("WAKALAH-")
    for kind in ("purchase_order", "commodity_invoice", "delivery_order", "trading_ecert", "muqassah", "casa_advice"):
        assert kind in body["certificates"]

    html = client.get(f"/api/v1/sedania/financing/{body['execution_id']}/documents/purchase_order")
    assert html.status_code == 200
    assert "Purchase Order" in html.text
    assert "AS SIDQ" in html.text
    assert "SEDANIA As Salam Capital" in html.text

    muqassah = client.get(f"/api/v1/sedania/financing/{body['execution_id']}/documents/muqassah")
    assert muqassah.status_code == 200
    assert "set-off" in muqassah.text.lower() or "Muqassah" in muqassah.text

    steps = {step["id"]: step["status"] for step in body["steps"]}
    assert steps["muqassah"] == "done"
    assert steps["casa"] == "done"


def test_aaoifi_rasul_skips_muqassah_and_credits_casa(client):
    bank = _dib(client)
    customer = _onboard(client, bank["id"], phone="60123450888")

    resp = client.post(
        "/api/v1/sedania/financing",
        json={
            "customer_id": customer["id"],
            "amount": "1500.00",
            "tenor": 6,
            "currency": "USD",
            "flow_variant": "aaoifi_rasul",
            "delivery_mode": "constructive",
            "casa_account": "CASA-DIB-USD-1",
            "institution_id": bank["id"],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["agency_role"] == "rasul"
    assert body["wakalah"]["token_id"].startswith("RASUL-")
    assert body["muqassah_ref"] is None
    assert body["casa_ref"]
    assert "muqassah" not in body["certificates"]
    assert "casa_advice" in body["certificates"]
    steps = {step["id"]: step["status"] for step in body["steps"]}
    assert "muqassah" not in steps
    assert steps["casa"] == "done"


def test_physical_delivery_waits_for_settlement(client):
    bank = _dib(client)
    customer = _onboard(client, bank["id"], phone="60123450777")

    resp = client.post(
        "/api/v1/sedania/financing",
        json={
            "customer_id": customer["id"],
            "amount": "10000.00",
            "tenor": 12,
            "currency": "MYR",
            "delivery_mode": "physical",
            "institution_id": bank["id"],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "awaiting_settlement"
    assert body["cash_disbursement"] == "withheld_physical"
    assert body["casa_ref"] is None
    assert body["purchaser_ref"] is None
    assert "liquidation" not in body["certificates"]

    arranged = client.post(f"/api/v1/sedania/financing/{body['execution_id']}/physical-delivery")
    assert arranged.status_code == 200, arranged.text
    done = arranged.json()
    assert done["status"] == "completed"
    assert done["physical_delivery_status"] == "arranged"
    assert "physical_delivery" in done["certificates"]
    html = client.get(f"/api/v1/sedania/financing/{body['execution_id']}/documents/physical_delivery")
    assert html.status_code == 200
    assert "qabd hakiki" in html.text.lower() or "Physical delivery" in html.text


def test_sacco_path_still_avoids_casa_and_issues_trade_pack(client):
    institutions = client.get("/api/v1/institutions").json()
    sacco = next(item for item in institutions if item["code"] == "MWALIMU")
    member = _onboard(client, sacco["id"], phone="254711500099")

    resp = client.post(
        "/api/v1/tawarruq/execute",
        json={
            "customer_id": member["id"],
            "amount": "50000.00",
            "tenor": 6,
            "institution_id": sacco["id"],
            "client_request_id": "MWALIMU-SED-DOC-001",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ready_for_sacco_disbursement"
    assert body["cash_disbursement"] == "sacco_cbs"
    assert body["casa_ref"] is None
    assert body["purchase_order_ref"]
    assert "purchase_order" in body["certificates"]
    wakalah = body["certificates"]["wakalah"]
    vault = client.get(wakalah["url"].replace("http://127.0.0.1:8000", ""))
    assert vault.status_code == 200
    assert "SEDANIA As Salam Capital" in vault.json()["payload"]["text"]
