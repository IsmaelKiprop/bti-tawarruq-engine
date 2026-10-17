import os

os.environ["AMANAH_ENABLED"] = "false"
os.environ["KENYA_INTEGRATION_MODE"] = "mock"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from tawarruq.database import Base, SessionLocal, engine, init_db
from tawarruq.enums import ShariahStepId, TransactionPhase
from tawarruq.main import app
from tawarruq.models.kenya_flow import ShariahAuditLog
from tawarruq.services.application_service import get_or_create_default_institution
from tawarruq.services.seed_service import seed_kenya_defaults
from tawarruq.services.shariah_audit_service import log_shariah_step, verify_application_shariah_integrity
from tawarruq.services.shariah_ledger_service import verify_ledger_chain
from tawarruq.services.shariah_state_machine import ShariahStateViolation, advance_phase


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


def _kenya_application_id(client):
    customer = client.post(
        "/api/v1/kenya/customers",
        json={"phone": "254700999888", "full_name": "Shariah Test", "wallet_number": "254700999888"},
    ).json()
    app_resp = client.post(
        "/api/v1/kenya/applications",
        json={
            "customer_id": customer["id"],
            "amount_requested": "20000.00",
            "term_months": 3,
            "purpose": "Audit test",
        },
    )
    return app_resp.json()["id"]


def test_shariah_audit_entry_has_required_fields(client):
    application_id = _kenya_application_id(client)
    client.post(f"/api/v1/kenya/applications/{application_id}/run-full-flow")

    audit = client.get(f"/api/v1/kenya/applications/{application_id}/shariah-audit")
    assert audit.status_code == 200
    entries = audit.json()
    assert len(entries) > 0

    possession = next(e for e in entries if e["step_id"] == ShariahStepId.CONSTRUCTIVE_POSSESSION)
    assert possession["timestamp"]
    assert possession["payload_hash"]
    assert possession["actor_from"]
    assert possession["actor_to"]
    assert possession["mno_receipt_id"]
    assert possession["verified_at"]
    assert possession["entry_hash"]
    assert possession["previous_hash"]


def test_append_only_ledger_blocks_mutations(client):
    application_id = _kenya_application_id(client)
    client.post(f"/api/v1/kenya/applications/{application_id}/run-full-flow")

    db = SessionLocal()
    try:
        entry = db.query(ShariahAuditLog).first()
        entry.details = "tampered"
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

        with pytest.raises(IntegrityError):
            db.delete(entry)
            db.commit()
    finally:
        db.close()


def test_cannot_skip_to_liquidation_without_possession(client):
    application_id = _kenya_application_id(client)
    client.post(f"/api/v1/kenya/applications/{application_id}/eligibility")
    txn = client.post("/api/v1/kenya/transactions", json={"application_id": application_id}).json()

    offer = client.post(f"/api/v1/kenya/applications/{application_id}/offer", json={})
    assert offer.status_code == 400

    liquidate = client.post(f"/api/v1/kenya/transactions/{txn['id']}/liquidate")
    assert liquidate.status_code in (400, 409)
    assert "possession" in liquidate.json()["detail"].lower() or "liquidat" in liquidate.json()["detail"].lower()


def test_hash_chain_verification(client):
    application_id = _kenya_application_id(client)
    client.post(f"/api/v1/kenya/applications/{application_id}/run-full-flow")

    verify = client.get(f"/api/v1/kenya/applications/{application_id}/shariah-audit/verify")
    assert verify.status_code == 200
    body = verify.json()
    assert body["valid"] is True
    assert body["ledger_chain"]["valid"] is True
    assert body["possession_sealed"] is True
    assert body["entry_count"] > 0

    chain = client.get("/api/v1/kenya/shariah-audit/verify-chain")
    assert chain.status_code == 200
    assert chain.json()["valid"] is True


def test_state_machine_blocks_phase_skip_in_service(client):
    application_id = _kenya_application_id(client)
    client.post(f"/api/v1/kenya/applications/{application_id}/eligibility")
    txn_id = client.post("/api/v1/kenya/transactions", json={"application_id": application_id}).json()["id"]

    db = SessionLocal()
    try:
        from tawarruq.models.transaction import CommodityTransaction

        txn = db.get(CommodityTransaction, txn_id)
        with pytest.raises(ShariahStateViolation):
            advance_phase(db, txn, TransactionPhase.PHASE_3_LIQUIDATION)
    finally:
        db.close()
