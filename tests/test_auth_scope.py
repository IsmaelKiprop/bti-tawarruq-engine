import os

os.environ["AMANAH_ENABLED"] = "false"
os.environ["KENYA_INTEGRATION_MODE"] = "mock"

import pytest
from fastapi.testclient import TestClient

from tawarruq.database import Base, SessionLocal, engine, init_db
from tawarruq.main import app
from tawarruq.services.application_service import get_or_create_default_institution


@pytest.fixture
def client():
    from tawarruq.config import get_settings

    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    from tawarruq.services.seed_service import seed_kenya_defaults

    get_or_create_default_institution(db)
    seed_kenya_defaults(db)
    db.commit()
    db.close()
    with TestClient(app) as test_client:
        yield test_client


def _create_second_institution(client):
    resp = client.post(
        "/api/v1/institutions",
        json={"name": "Other Bank", "code": "OTHER", "bsas_mode": "mock"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def test_api_key_required_when_auth_enabled(client, monkeypatch):
    from tawarruq.config import get_settings

    monkeypatch.setenv("AUTH_ENABLED", "true")
    get_settings.cache_clear()

    resp = client.get("/api/v1/applications")
    assert resp.status_code == 401

    institutions = client.get("/api/v1/institutions")
    assert institutions.status_code == 401


def test_tenant_scoped_list_and_access(client, monkeypatch):
    from tawarruq.config import get_settings
    from tawarruq.services.auth_service import create_api_key

    institutions = {row["code"]: row["id"] for row in client.get("/api/v1/institutions").json()}
    default = institutions["DEFAULT"]
    other_id = _create_second_institution(client)

    app_resp = client.post(
        "/api/v1/applications",
        json={
            "amount_requested": "50000.00",
            "term_months": 6,
            "purpose": "Working capital",
        },
    )
    assert app_resp.status_code == 201
    app_id = app_resp.json()["id"]

    other_app = client.post(
        "/api/v1/applications",
        json={
            "institution_id": other_id,
            "amount_requested": "10000.00",
            "term_months": 3,
            "purpose": "Other",
        },
    )
    assert other_app.status_code == 201

    db = SessionLocal()
    _, raw_key = create_api_key(db, institution_id=default, name="ops")
    db.commit()
    db.close()

    monkeypatch.setenv("AUTH_ENABLED", "true")
    get_settings.cache_clear()
    headers = {"X-API-Key": raw_key}

    listed = client.get("/api/v1/applications", headers=headers)
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()}
    assert app_id in ids
    assert other_app.json()["id"] not in ids

    forbidden = client.get(f"/api/v1/applications/{other_app.json()['id']}", headers=headers)
    assert forbidden.status_code == 403

    get_settings.cache_clear()


def test_callback_token_when_configured(client, monkeypatch):
    from tawarruq.config import get_settings

    monkeypatch.setenv("CALLBACK_AUTH_TOKEN", "secret-callback-token")
    get_settings.cache_clear()

    resp = client.post(
        "/api/v1/kenya/callbacks/mpesa/b2c/result",
        json={"Result": {"ResultCode": 1, "ResultDesc": "Failed"}},
    )
    assert resp.status_code == 401

    ok = client.post(
        "/api/v1/kenya/callbacks/mpesa/b2c/result",
        headers={"X-Callback-Token": "secret-callback-token"},
        json={"Result": {"ResultCode": 1, "ResultDesc": "Failed"}},
    )
    assert ok.status_code == 200

    get_settings.cache_clear()
