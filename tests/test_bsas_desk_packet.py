import os
from decimal import Decimal

os.environ["AMANAH_ENABLED"] = "false"
os.environ["KENYA_INTEGRATION_MODE"] = "mock"
os.environ["AUTH_ENABLED"] = "false"

from fastapi.testclient import TestClient

from tawarruq.bsas.product_codes import bsas_product_code
from tawarruq.config import get_settings
from tawarruq.database import Base, SessionLocal, engine, init_db
from tawarruq.main import app
from tawarruq.services.application_service import get_or_create_default_institution


def setup_module():
    get_settings.cache_clear()


def _client():
    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    get_or_create_default_institution(db)
    db.commit()
    db.close()
    return TestClient(app)


def test_bsas_product_code_maps_palm_oil_to_acpo():
    assert bsas_product_code("PALM_OIL") == "ACPO"
    assert bsas_product_code("ACPO") == "ACPO"


def test_manual_bridge_desk_packet_matches_bursa_sample_fields():
    client = _client()

    app_resp = client.post(
        "/api/v1/applications",
        json={
            "customer_name": "Marian Abubakar",
            "currency": "KES",
            "amount_requested": "550000.00",
            "term_months": 12,
            "purpose": "Working capital",
        },
    )
    assert app_resp.status_code == 201
    application_id = app_resp.json()["id"]
    assert app_resp.json()["customer_name"] == "Marian Abubakar"
    assert app_resp.json()["currency"] == "KES"

    offer = client.post(
        f"/api/v1/applications/{application_id}/offer",
        json={"cost_price": "550000.00", "profit_rate_pct": "5.0"},
    )
    assert offer.status_code == 201
    assert Decimal(offer.json()["cost_price"]) == Decimal("550000.00")
    assert Decimal(offer.json()["profit_amount"]) == Decimal("27500.00")
    assert Decimal(offer.json()["total_payable"]) == Decimal("577500.00")

    accept = client.post(f"/api/v1/applications/{application_id}/accept")
    assert accept.status_code == 200

    txn = client.post(
        "/api/v1/transactions",
        json={"application_id": application_id, "commodity_code": "PALM_OIL", "mode": "manual_bridge"},
    )
    assert txn.status_code == 201
    transaction_id = txn.json()["id"]

    advanced = client.post(f"/api/v1/manual-bridge/transactions/{transaction_id}/advance")
    assert advanced.status_code == 200
    leg1 = next(leg for leg in advanced.json()["legs"] if leg["leg_number"] == "1")
    assert leg1["status"] == "awaiting_confirmation"
    assert leg1["external_ref"]

    detail = client.get(f"/api/v1/manual-bridge/transactions/{transaction_id}/legs/1")
    assert detail.status_code == 200
    body = detail.json()
    assert body["customer_name"] == "Marian Abubakar"
    assert body["product_code"] == "ACPO"
    assert body["purchase_type"] == "A"
    assert body["currency"] == "KES"
    assert body["bid_amount"] == "550000.00"
    assert body["profit_amount"] == "27500.00"
    assert body["murabaha_total"] == "577500.00"
    assert body["email_body"]
    assert "End Customer Name: Marian Abubakar" in body["email_body"]
    assert "Product Code: ACPO" in body["email_body"]
    assert "Purchase Type: Agent (A)" in body["email_body"]
    assert "Ownership Transfer (OTC)" in body["email_body"]
    assert body["request"]["format"] == "bursa_bsas_desk_v1"
    assert body["request"]["amounts"]["bid_amount_cost_price"] == "550000.00"

    batch = client.get("/api/v1/manual-bridge/desk-batch")
    assert batch.status_code == 200
    batch_body = batch.json()
    assert batch_body["customer_count"] >= 1
    assert batch_body["customers"][0]["product_code"] == "ACPO"
    assert "REQUEST FOR LIVE ACCESS" in batch_body["email_body"]
    assert "Marian Abubakar" in batch_body["email_body"]

    text = client.get("/api/v1/manual-bridge/desk-batch.txt")
    assert text.status_code == 200
    assert "Agent (A)" in text.text
