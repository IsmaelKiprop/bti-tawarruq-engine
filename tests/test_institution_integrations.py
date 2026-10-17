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


def test_institution_integration_profile(client):
    institutions = client.get("/api/v1/institutions")
    institution_id = institutions.json()[0]["id"]

    put = client.put(
        f"/api/v1/institutions/{institution_id}/integrations",
        json={
            "kenya_mode": "mock",
            "callback_base_url": "https://bank-a.example.com",
            "mpesa_shortcode": "600000",
            "mpesa_consumer_key": "test-key",
            "mpesa_consumer_secret": "test-secret",
            "mpesa_initiator_name": "testapi",
            "mpesa_security_credential": "test-credential",
            "mno_safaricom_dealer_code": "DEALER001",
            "mno_safaricom_api_url": "https://mno.example.com",
        },
    )
    assert put.status_code == 200
    data = put.json()
    assert data["mpesa_shortcode"] == "600000"
    assert data["mpesa_consumer_secret_set"] is True
    assert data["kenya_mode"] == "mock"

    urls = client.get(f"/api/v1/institutions/{institution_id}/integrations/callback-urls")
    assert urls.status_code == 200
    assert institution_id in urls.json()["mpesa_b2c_result_url"]

    status = client.get(f"/api/v1/institutions/{institution_id}/integrations/status")
    assert status.status_code == 200
    assert status.json()["kenya_mode"] == "mock"
