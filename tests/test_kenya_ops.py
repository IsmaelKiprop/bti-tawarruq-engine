import os

os.environ["AMANAH_ENABLED"] = "false"
os.environ["KENYA_INTEGRATION_MODE"] = "mock"

from fastapi.testclient import TestClient

from tawarruq.database import Base, SessionLocal, engine, init_db
from tawarruq.main import app
from tawarruq.services.application_service import get_or_create_default_institution


def test_kenya_ops_endpoints():
    from tawarruq.config import get_settings

    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    get_or_create_default_institution(db)
    db.commit()
    db.close()

    client = TestClient(app)

    customer = client.post(
        "/api/v1/kenya/customers",
        json={
            "phone": "254700000001",
            "full_name": "Ops Test",
            "wallet_number": "254700000001",
        },
    )
    assert customer.status_code == 201

    application = client.post(
        "/api/v1/kenya/applications",
        json={
            "customer_id": customer.json()["id"],
            "amount_requested": "10000.00",
            "term_months": 3,
            "purpose": "Ops desk test",
        },
    )
    assert application.status_code == 201
    app_id = application.json()["id"]

    cases = client.get("/api/v1/kenya/ops/cases")
    assert cases.status_code == 200
    assert any(item["application_id"] == app_id for item in cases.json())

    detail = client.get(f"/api/v1/kenya/ops/cases/{app_id}")
    assert detail.status_code == 200
    assert detail.json()["next_action"] in {"eligibility", "start_transaction"}

    brokers = client.get("/api/v1/kenya/ops/brokers")
    assert brokers.status_code == 200
    assert isinstance(brokers.json(), list)

    repayments = client.get("/api/v1/kenya/ops/repayments")
    assert repayments.status_code == 200
