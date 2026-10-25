import os

os.environ["AMANAH_ENABLED"] = "false"
os.environ["KENYA_INTEGRATION_MODE"] = "mock"

import pytest
from decimal import Decimal
from fastapi.testclient import TestClient

from tawarruq.database import Base, SessionLocal, engine, init_db
from tawarruq.main import app


@pytest.fixture
def client():
    from tawarruq.config import get_settings

    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    from tawarruq.services.application_service import get_or_create_default_institution
    from tawarruq.services.seed_service import seed_kenya_defaults

    get_or_create_default_institution(db)
    seed_kenya_defaults(db)
    db.commit()
    db.close()
    with TestClient(app) as test_client:
        yield test_client


def _create_accepted_application(client):
    app_resp = client.post(
        "/api/v1/applications",
        json={
            "customer_ref": "CUST-001",
            "amount_requested": "100000.00",
            "term_months": 12,
            "purpose": "Working capital",
        },
    )
    application_id = app_resp.json()["id"]
    client.post(f"/api/v1/applications/{application_id}/offer", json={})
    client.post(f"/api/v1/applications/{application_id}/accept")
    return application_id


def test_auto_generated_customer_ref(client):
    resp = client.post(
        "/api/v1/applications",
        json={
            "amount_requested": "75000.00",
            "term_months": 6,
            "purpose": "Inventory",
        },
    )
    assert resp.status_code == 201
    ref = resp.json()["customer_ref"]
    assert ref.startswith("CUST-DEFAULT-")
    assert ref.split("-")[-1].isdigit()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["uptime_pct"] == 100
    assert payload["uptime_seconds"] >= 0


def test_full_tawarruq_flow_mock(client):
    application_id = _create_accepted_application(client)

    txn_resp = client.post(
        "/api/v1/transactions",
        json={"application_id": application_id, "mode": "mock"},
    )
    assert txn_resp.status_code == 201
    transaction_id = txn_resp.json()["id"]

    for endpoint in ("purchase", "transfer", "sale"):
        leg_resp = client.post(f"/api/v1/transactions/{transaction_id}/legs/{endpoint}")
        assert leg_resp.status_code == 200

    detail = client.get(f"/api/v1/transactions/{transaction_id}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["status"] == "completed"

    biz = client.get(f"/api/v1/applications/{application_id}/business-status")
    assert biz.json()["ready_for_leg_3"] is True

    disb_resp = client.post(
        "/api/v1/disbursements",
        json={"application_id": application_id, "transaction_id": transaction_id},
    )
    assert disb_resp.status_code == 201
    assert disb_resp.json()["tawarruq_certificate"] is not None

    audit = client.get(f"/api/v1/audit?entity_id={transaction_id}")
    assert audit.status_code == 200
    assert len(audit.json()) > 0


def test_list_endpoints(client):
    _create_accepted_application(client)
    apps = client.get("/api/v1/applications")
    assert apps.status_code == 200
    assert len(apps.json()) >= 1
    txns = client.get("/api/v1/transactions")
    assert txns.status_code == 200


def test_webhook_registration(client):
    institutions = client.get("/api/v1/institutions")
    institution_id = institutions.json()[0]["id"]
    resp = client.post(
        "/api/v1/webhooks",
        json={
            "institution_id": institution_id,
            "url": "https://example.com/webhook",
            "events": ["transaction.completed"],
        },
    )
    assert resp.status_code == 201
    assert "secret" in resp.json()


def test_manual_bridge_flow(client, tmp_path, monkeypatch):
    from tawarruq.config import get_settings

    monkeypatch.setenv("MANUAL_BRIDGE_INBOX_DIR", str(tmp_path))
    get_settings.cache_clear()

    application_id = _create_accepted_application(client)
    txn_resp = client.post(
        "/api/v1/transactions",
        json={"application_id": application_id, "mode": "manual_bridge"},
    )
    transaction_id = txn_resp.json()["id"]

    purchase = client.post(f"/api/v1/manual-bridge/transactions/{transaction_id}/advance")
    assert purchase.status_code == 200
    leg = purchase.json()["legs"][0]
    assert leg["status"] == "awaiting_confirmation"
    external_ref = leg["external_ref"]

    pending = client.get("/api/v1/manual-bridge/pending")
    assert pending.status_code == 200
    assert any(item["transaction_id"] == transaction_id for item in pending.json())

    detail = client.get(f"/api/v1/manual-bridge/transactions/{transaction_id}/legs/1")
    assert detail.status_code == 200
    assert detail.json()["external_ref"] == external_ref
    assert detail.json()["request"] is not None

    confirm = client.post(
        f"/api/v1/transactions/{transaction_id}/legs/1/confirm",
        json={"certificate_number": "CERT-TEST-001", "issuer": "BSAS"},
    )
    assert confirm.status_code == 200
    assert confirm.json()["legs"][0]["status"] == "confirmed"

    reply_path = tmp_path / "replies" / f"{external_ref}.json"
    assert reply_path.exists()
    assert "CERT-TEST-001" in reply_path.read_text(encoding="utf-8")

    get_settings.cache_clear()


def test_audit_export(client):
    application_id = _create_accepted_application(client)
    export = client.get(f"/api/v1/audit/export?entity_id={application_id}")
    assert export.status_code == 200
    assert "application.created" in export.text


def test_delete_application(client):
    application_id = _create_accepted_application(client)
    deleted = client.delete(f"/api/v1/applications/{application_id}")
    assert deleted.status_code == 204
    missing = client.get(f"/api/v1/applications/{application_id}")
    assert missing.status_code == 404
    remaining = client.get("/api/v1/applications")
    assert all(item["id"] != application_id for item in remaining.json())


def test_update_and_delete_institution(client):
    created = client.post(
        "/api/v1/institutions",
        json={"name": "Temp Desk Bank", "code": "TMP1", "bsas_mode": "mock"},
    )
    assert created.status_code == 201, created.text
    institution_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/institutions/{institution_id}",
        json={"name": "Temp Desk Bank Updated", "bsas_mode": "manual_bridge"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Temp Desk Bank Updated"
    assert updated.json()["bsas_mode"] == "manual_bridge"

    default = next(item for item in client.get("/api/v1/institutions").json() if item["code"] == "DEFAULT")
    blocked = client.delete(f"/api/v1/institutions/{default['id']}")
    assert blocked.status_code == 400

    deleted = client.delete(f"/api/v1/institutions/{institution_id}")
    assert deleted.status_code == 204
    missing = client.get(f"/api/v1/institutions/{institution_id}")
    assert missing.status_code == 404


def test_create_application_links_onboarded_customer(client):
    customer = client.post(
        "/api/v1/kenya/customers",
        json={
            "phone": "60123456789",
            "full_name": "Marian Abubakar",
            "wallet_number": "60123456789",
        },
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]

    created = client.post(
        "/api/v1/applications",
        json={
            "customer_id": customer_id,
            "currency": "MYR",
            "amount_requested": "550000.00",
            "term_months": 12,
            "purpose": "Working capital (Malaysia BSAS)",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["customer_id"] == customer_id
    assert body["customer_name"] == "Marian Abubakar"

    missing = client.post(
        "/api/v1/applications",
        json={
            "customer_id": "00000000-0000-0000-0000-000000000000",
            "amount_requested": "1000.00",
            "term_months": 6,
            "purpose": "Working capital",
        },
    )
    assert missing.status_code == 404
