import os

os.environ["AMANAH_ENABLED"] = "false"
os.environ["KENYA_INTEGRATION_MODE"] = "mock"

import pytest
from fastapi.testclient import TestClient

from tawarruq.amanah.worker import AmanahWorker
from tawarruq.database import Base, SessionLocal, engine, init_db
from tawarruq.enums import ApplicationStatus, TransactionMode, TransactionStatus
from tawarruq.main import app
from tawarruq.models.application import FinancingApplication
from tawarruq.models.transaction import CommodityTransaction
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


def _eligible_application(client):
    customer = client.post(
        "/api/v1/kenya/customers",
        json={
            "phone": "254711222333",
            "full_name": "Amanah Test",
            "wallet_number": "254711222333",
        },
    )
    customer_id = customer.json()["id"]
    app_resp = client.post(
        "/api/v1/kenya/applications",
        json={
            "customer_id": customer_id,
            "amount_requested": "15000.00",
            "term_months": 3,
            "purpose": "Float",
        },
    )
    application_id = app_resp.json()["id"]
    client.post(f"/api/v1/kenya/applications/{application_id}/eligibility")
    return application_id


def test_amanah_advances_mno_mock_transaction(client):
    application_id = _eligible_application(client)

    db = SessionLocal()
    try:
        application = db.get(FinancingApplication, application_id)
        application.status = ApplicationStatus.IN_PROGRESS
        db.commit()

        worker = AmanahWorker(write_enabled=True)
        worker.tick()

        txn = (
            db.query(CommodityTransaction)
            .filter(CommodityTransaction.application_id == application_id)
            .first()
        )
        assert txn is not None
        assert txn.mode == TransactionMode.MNO

        for _ in range(12):
            worker.tick()
            db.expire_all()
            txn = db.get(CommodityTransaction, txn.id)
            if txn.status == TransactionStatus.COMPLETED:
                break

        assert txn.status == TransactionStatus.COMPLETED
    finally:
        db.close()


def test_malaysia_shariah_audit_on_flow(client):
    app_resp = client.post(
        "/api/v1/applications",
        json={
            "amount_requested": "80000.00",
            "term_months": 12,
            "purpose": "Inventory",
        },
    )
    application_id = app_resp.json()["id"]
    client.post(f"/api/v1/applications/{application_id}/offer", json={})
    client.post(f"/api/v1/applications/{application_id}/accept")

    txn = client.post(
        "/api/v1/transactions",
        json={"application_id": application_id, "mode": "mock"},
    ).json()
    transaction_id = txn["id"]

    for endpoint in ("purchase", "transfer", "sale"):
        client.post(f"/api/v1/transactions/{transaction_id}/legs/{endpoint}")

    shariah = client.get(f"/api/v1/applications/{application_id}/shariah-audit")
    assert shariah.status_code == 200
    steps = {entry["step_id"] for entry in shariah.json()}
    assert "FINANCING_REQUEST" in steps
    assert "MURABAHA_PURCHASE" in steps
    assert "THIRD_PARTY_LIQUIDATION" in steps
