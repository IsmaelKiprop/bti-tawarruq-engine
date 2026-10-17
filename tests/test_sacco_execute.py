import json
import os
import time

os.environ["AMANAH_ENABLED"] = "false"
os.environ["KENYA_INTEGRATION_MODE"] = "mock"
os.environ["SEDANIA_MODE"] = "mock"

import pytest
from fastapi.testclient import TestClient

from tawarruq.database import Base, SessionLocal, engine, init_db
from tawarruq.main import app
from tawarruq.models.kenya_flow import WalletDisbursement
from tawarruq.services.application_service import get_or_create_default_institution
from tawarruq.services.auth_service import sign_sacco_payload
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


def _mwalimu(client: TestClient) -> dict:
    institutions = client.get("/api/v1/institutions").json()
    return next(item for item in institutions if item["code"] == "MWALIMU")


def _onboard_member(client: TestClient, institution_id: str) -> dict:
    resp = client.post(
        "/api/v1/kenya/customers",
        json={
            "institution_id": institution_id,
            "phone": "254711500001",
            "full_name": "Amina Otieno",
            "wallet_number": "254711500001",
            "national_id": "SACCO-MEM-0001",
            "email": "amina.otieno@example.com",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_sacco_execute_stamps_trades_and_vaults_without_bti_cash(client):
    sacco = _mwalimu(client)
    member = _onboard_member(client, sacco["id"])

    resp = client.post(
        "/api/v1/tawarruq/execute",
        json={
            "customer_id": member["id"],
            "amount": "50000.00",
            "tenor": 6,
            "institution_id": sacco["id"],
            "client_request_id": "MWALIMU-REQ-001",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "ready_for_sacco_disbursement"
    assert body["cash_disbursement"] == "sacco_cbs"
    assert body["amount"] == "50000.00"
    assert body["profit_amount"] == "2500.00"
    assert body["deferred_price"] == "52500.00"
    assert body["wad"]["token_id"].startswith("WAD-")
    assert body["wakalah"]["token_id"].startswith("WAKALAH-")
    assert body["sedania_batch_id"]
    for kind in ("wad", "wakalah", "purchase", "murabahah", "liquidation"):
        assert kind in body["certificates"]
        assert body["certificates"][kind]["url"]
    assert body["certificates"]["purchase"]["serial_numbers"]
    assert body["certificates"]["purchase"]["source"] == "sedania"

    purchase_url = body["certificates"]["purchase"]["url"]
    vault_resp = client.get(purchase_url.replace("http://127.0.0.1:8000", ""))
    assert vault_resp.status_code == 200, vault_resp.text
    vault = vault_resp.json()
    assert vault["kind"] == "purchase"
    assert vault["payload"]["qabd_hukmi"] is True
    assert "Certificate 1" in vault["payload"]["title"]

    db = SessionLocal()
    try:
        wallets = db.query(WalletDisbursement).all()
        assert wallets == []
    finally:
        db.close()

    replay = client.post(
        "/api/v1/tawarruq/execute",
        json={
            "customer_id": member["id"],
            "amount": "50000.00",
            "tenor": 6,
            "institution_id": sacco["id"],
            "client_request_id": "MWALIMU-REQ-001",
        },
    )
    assert replay.status_code == 200
    assert replay.json()["execution_id"] == body["execution_id"]


def test_sacco_execute_relays_three_certificate_urls(client, monkeypatch):
    captured: dict = {}

    def fake_deliver(*, url, secret, payload, event_name):
        captured["url"] = url
        captured["event"] = event_name
        captured["body"] = json.loads(payload)
        return True

    monkeypatch.setattr("tawarruq.services.sacco_execute_service.deliver_signed_webhook", fake_deliver)
    sacco = _mwalimu(client)
    member = _onboard_member(client, sacco["id"])
    resp = client.post(
        "/api/v1/tawarruq/execute",
        json={
            "customer_id": member["phone"],
            "amount": "50000.00",
            "tenor": 6,
            "institution_id": sacco["id"],
            "callback_url": "https://mwalimu.example/api/tawarruq/callback",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["callback_delivered"] is True
    assert captured["url"] == "https://mwalimu.example/api/tawarruq/callback"
    assert captured["event"] == "tawarruq.certificates_ready"
    certs = captured["body"]["data"]["certificates"]
    assert certs["purchase"] and certs["murabahah"] and certs["liquidation"]
    assert captured["body"]["data"]["cash_disbursement"] == "sacco_cbs"


def test_sacco_execute_unknown_borrower(client):
    sacco = _mwalimu(client)
    resp = client.post(
        "/api/v1/tawarruq/execute",
        json={
            "customer_id": "missing-member",
            "amount": "50000.00",
            "tenor": 6,
            "institution_id": sacco["id"],
        },
    )
    assert resp.status_code == 404


def test_sacco_execute_hmac_required_when_auth_enabled(client, monkeypatch):
    from tawarruq.config import get_settings
    from tawarruq.database import SessionLocal as Db
    from tawarruq.services.auth_service import create_api_key

    sacco = _mwalimu(client)
    member = _onboard_member(client, sacco["id"])
    db = Db()
    record, raw_key = create_api_key(db, institution_id=sacco["id"], name="mwalimu-cbs")
    hmac_secret = record.hmac_secret
    db.commit()
    db.close()

    monkeypatch.setenv("AUTH_ENABLED", "true")
    get_settings.cache_clear()

    payload = {
        "customer_id": member["id"],
        "amount": "50000.00",
        "tenor": 6,
        "institution_id": sacco["id"],
    }
    raw = json.dumps(payload).encode()
    unsigned = client.post(
        "/api/v1/tawarruq/execute",
        content=raw,
        headers={"Content-Type": "application/json", "X-API-Key": raw_key},
    )
    assert unsigned.status_code == 401

    timestamp = str(int(time.time()))
    signature = sign_sacco_payload(hmac_secret=hmac_secret, timestamp=timestamp, body=raw)
    signed = client.post(
        "/api/v1/tawarruq/execute",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "X-API-Key": raw_key,
            "X-BTI-Timestamp": timestamp,
            "X-BTI-Signature": signature,
        },
    )
    assert signed.status_code == 200, signed.text
    assert signed.json()["status"] == "ready_for_sacco_disbursement"
