import os

os.environ["AMANAH_ENABLED"] = "false"
os.environ["KENYA_INTEGRATION_MODE"] = "mock"

import pytest
from fastapi.testclient import TestClient

from tawarruq.database import Base, SessionLocal, engine, init_db
from tawarruq.main import app
from tawarruq.models.disbursement import Disbursement
from tawarruq.models.kenya_flow import WalletDisbursement
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


def test_mpesa_b2c_callback_completes_pending_wallet(client):
    app_resp = client.post(
        "/api/v1/applications",
        json={"amount_requested": "10000.00", "term_months": 6, "purpose": "Test"},
    )
    application_id = app_resp.json()["id"]
    client.post(f"/api/v1/applications/{application_id}/offer", json={})
    client.post(f"/api/v1/applications/{application_id}/accept")
    txn_id = client.post(
        "/api/v1/transactions",
        json={"application_id": application_id, "mode": "mock"},
    ).json()["id"]
    for endpoint in ("purchase", "transfer", "sale"):
        client.post(f"/api/v1/transactions/{txn_id}/legs/{endpoint}")
    disb_id = client.post(
        "/api/v1/disbursements",
        json={"application_id": application_id, "transaction_id": txn_id},
    ).json()["id"]

    db = SessionLocal()
    try:
        disbursement = db.get(Disbursement, disb_id)
        external_ref = "originator-test-123"
        wallet = WalletDisbursement(
            disbursement_id=disbursement.id,
            provider="mpesa",
            wallet_number="254700000001",
            amount=disbursement.amount,
            external_txn_id=external_ref,
            status="pending",
        )
        db.add(wallet)
        db.commit()
    finally:
        db.close()

    callback = client.post(
        "/api/v1/kenya/callbacks/mpesa/b2c/result",
        json={
            "Result": {
                "OriginatorConversationID": external_ref,
                "ConversationID": "conv-123",
                "ResultCode": 0,
                "ResultDesc": "Success",
                "ResultParameters": {
                    "ResultParameter": [{"Key": "TransactionReceipt", "Value": "QAB123XYZ"}]
                },
            }
        },
    )
    assert callback.status_code == 200
    assert callback.json()["processed"] is True

    db = SessionLocal()
    try:
        wallet = db.query(WalletDisbursement).filter(WalletDisbursement.external_txn_id == "QAB123XYZ").first()
        if not wallet:
            wallet = db.query(WalletDisbursement).filter(WalletDisbursement.disbursement_id == disbursement.id).first()
        assert wallet is not None
        assert wallet.status == "credited"
    finally:
        db.close()


def test_mno_possession_callback(client):
    customer = client.post(
        "/api/v1/kenya/customers",
        json={
            "phone": "254755666777",
            "full_name": "Possession Test",
            "wallet_number": "254755666777",
        },
    )
    customer_id = customer.json()["id"]
    app_resp = client.post(
        "/api/v1/kenya/applications",
        json={
            "customer_id": customer_id,
            "amount_requested": "9000.00",
            "term_months": 3,
            "purpose": "Float",
        },
    )
    application_id = app_resp.json()["id"]
    client.post(f"/api/v1/kenya/applications/{application_id}/eligibility")
    client.post(f"/api/v1/kenya/applications/{application_id}/offer", json={})
    client.post(f"/api/v1/kenya/applications/{application_id}/accept")
    txn = client.post(
        "/api/v1/kenya/transactions",
        json={"application_id": application_id},
    )
    assert txn.status_code == 201
    transaction_id = txn.json()["id"]
    purchase = client.post(f"/api/v1/kenya/transactions/{transaction_id}/purchase")
    assert purchase.status_code == 200

    db = SessionLocal()
    try:
        from tawarruq.enums import LegStatus, PossessionStatus
        from tawarruq.models.certificate import Certificate
        from tawarruq.models.kenya_flow import AssetBatch
        from tawarruq.models.transaction import CommodityTransaction

        transaction = db.get(CommodityTransaction, transaction_id)
        purchase_leg = next(leg for leg in transaction.legs if leg.leg_number == "1")
        batch = db.query(AssetBatch).filter(AssetBatch.leg_id == purchase_leg.id).first()
        batch_id = batch.batch_id
        if purchase_leg.status != LegStatus.AWAITING_POSSESSION:
            existing_cert = db.query(Certificate).filter(Certificate.leg_id == purchase_leg.id).first()
            if existing_cert:
                db.delete(existing_cert)
            purchase_leg.status = LegStatus.AWAITING_POSSESSION
            purchase_leg.executed_at = None
            if batch:
                batch.possession_status = PossessionStatus.PENDING
                batch.verified_at = None
            db.commit()
    finally:
        db.close()

    callback = client.post(
        "/api/v1/kenya/callbacks/mno/possession",
        json={
            "batch_id": batch_id,
            "receipt_id": "receipt-webhook-1",
            "status": "verified",
        },
    )
    assert callback.status_code == 200
    assert callback.json()["processed"] is True

    detail = client.get(f"/api/v1/transactions/{transaction_id}")
    assert detail.json()["legs"][0]["status"] == "confirmed"
