import os
from io import BytesIO

os.environ["AMANAH_ENABLED"] = "false"
os.environ["KENYA_INTEGRATION_MODE"] = "mock"
os.environ["AUTH_ENABLED"] = "false"

from fastapi.testclient import TestClient

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


def _start_manual_leg(client: TestClient) -> tuple[str, str]:
    app_resp = client.post(
        "/api/v1/applications",
        json={
            "customer_name": "Hidaya Said",
            "currency": "KES",
            "amount_requested": "50000.00",
            "term_months": 6,
            "purpose": "Working capital",
        },
    )
    assert app_resp.status_code == 201
    application_id = app_resp.json()["id"]
    assert client.post(
        f"/api/v1/applications/{application_id}/offer",
        json={"cost_price": "50000.00", "profit_rate_pct": "5.0"},
    ).status_code == 201
    assert client.post(f"/api/v1/applications/{application_id}/accept").status_code == 200
    txn = client.post(
        "/api/v1/transactions",
        json={"application_id": application_id, "commodity_code": "PALM_OIL", "mode": "manual_bridge"},
    )
    assert txn.status_code == 201
    transaction_id = txn.json()["id"]
    advanced = client.post(f"/api/v1/manual-bridge/transactions/{transaction_id}/advance")
    assert advanced.status_code == 200
    return transaction_id, application_id


def test_confirm_ecert_with_bursa_metadata_and_pdf():
    client = _client()
    transaction_id, _ = _start_manual_leg(client)

    pdf_bytes = b"%PDF-1.4 fake bursa ecert content"
    response = client.post(
        f"/api/v1/manual-bridge/transactions/{transaction_id}/legs/1/confirm",
        data={
            "certificate_number": "CPO28AUG26-0009491-000",
            "issuer": "Bursa Malaysia Islamic Services Sdn.Bhd.",
            "seller": "Hidaya Said ( 000 )",
            "buyer": "Bursa Malaysia Islamic Services",
            "bid_no": "1",
            "selling_time": "19:00:50.857",
            "selling_date": "28 AUGUST 2026",
            "value_date": "28 AUGUST 2026",
            "product_code": "CPO-MSIA-09",
            "product_description": "Crude Palm Oil - Malaysia - Listed 09",
            "unit": "Tonnage",
            "volume": ".32293179",
            "currency": "KES",
            "price": "154831.46067416",
            "price_myr_equivalent": "4823.00",
            "value_amount": "50000.00",
            "transaction_type": "-",
        },
        files={"file": ("CPO28AUG26-0009491-000.pdf", BytesIO(pdf_bytes), "application/pdf")},
    )
    assert response.status_code == 200, response.text
    leg1 = next(leg for leg in response.json()["legs"] if leg["leg_number"] == "1")
    assert leg1["status"] == "confirmed"
    cert = leg1["certificate"]
    assert cert["certificate_number"] == "CPO28AUG26-0009491-000"
    assert cert["seller"] == "Hidaya Said ( 000 )"
    assert cert["buyer"] == "Bursa Malaysia Islamic Services"
    assert cert["product_code"] == "CPO-MSIA-09"
    assert cert["currency"] == "KES"
    assert cert["value_amount"] == "50000.00"
    assert cert["price_myr_equivalent"] == "4823.00"
    assert cert["pdf_filename"] == "CPO28AUG26-0009491-000.pdf"
    assert cert["pdf_path"]
    assert "ecerts" in cert["pdf_path"].replace("\\", "/")


def test_upload_ecert_pdf_only():
    client = _client()
    transaction_id, _ = _start_manual_leg(client)

    response = client.post(
        f"/api/v1/manual-bridge/transactions/{transaction_id}/legs/1/ecert-pdf",
        data={"certificate_number": "CPO28AUG26-0009492-000"},
        files={"file": ("receipt.pdf", BytesIO(b"%PDF-1.4 x"), "application/pdf")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pdf_filename"] == "receipt.pdf"
    assert body["certificate_number"] == "CPO28AUG26-0009492-000"
