import os

os.environ["AMANAH_ENABLED"] = "false"
os.environ["KENYA_INTEGRATION_MODE"] = "mock"

import pytest
from fastapi.testclient import TestClient

from tawarruq.database import Base, SessionLocal, engine, init_db
from tawarruq.enums import TransactionMode, TransactionStatus
from tawarruq.main import app
from tawarruq.models.institution import Institution
from tawarruq.models.kenya_flow import ThirdPartyBroker
from tawarruq.models.transaction import CommodityTransaction
from tawarruq.services.application_service import get_or_create_default_institution
from tawarruq.services.no_inah_service import validate_no_inah
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


def _eligible_application_with_txn(client):
    customer = client.post(
        "/api/v1/kenya/customers",
        json={"phone": "254700555666", "full_name": "No Inah Test", "wallet_number": "254700555666"},
    ).json()
    app_resp = client.post(
        "/api/v1/kenya/applications",
        json={
            "customer_id": customer["id"],
            "amount_requested": "10000.00",
            "term_months": 3,
            "purpose": "Test",
        },
    )
    application_id = app_resp.json()["id"]
    client.post(f"/api/v1/kenya/applications/{application_id}/eligibility")
    txn = client.post("/api/v1/kenya/transactions", json={"application_id": application_id}).json()
    return application_id, txn["id"]


def test_offer_blocked_before_possession(client):
    application_id, _txn_id = _eligible_application_with_txn(client)
    offer = client.post(f"/api/v1/kenya/applications/{application_id}/offer", json={})
    assert offer.status_code == 400
    detail = offer.json()["detail"].lower()
    assert "possession" in detail or "purchase" in detail


def test_no_inah_blocks_financier_broker(client):
    application_id, txn_id = _eligible_application_with_txn(client)
    db = SessionLocal()
    try:
        institution = db.query(Institution).first()
        financier_broker = ThirdPartyBroker(
            code=institution.code,
            name="Financier Self",
            mno_codes="AIRTIME_SAFARICOM",
            is_mno_pool=False,
        )
        db.add(financier_broker)
        db.commit()

        txn = db.get(CommodityTransaction, txn_id)
        assert validate_no_inah(db, txn, broker=financier_broker) is False
    finally:
        db.close()


def test_no_inah_blocks_mno_pool_broker(client):
    application_id, txn_id = _eligible_application_with_txn(client)
    db = SessionLocal()
    try:
        pool = db.query(ThirdPartyBroker).filter(ThirdPartyBroker.code == "SAFARICOM_MNO").first()
        txn = db.get(CommodityTransaction, txn_id)
        assert pool is not None
        assert pool.is_mno_pool is True
        assert validate_no_inah(db, txn, broker=pool) is False
    finally:
        db.close()


def test_liquidation_requires_wakala(client):
    application_id, txn_id = _eligible_application_with_txn(client)
    purchase = client.post(f"/api/v1/kenya/transactions/{txn_id}/purchase").json()
    if purchase["legs"][0]["status"] == "awaiting_possession":
        client.post(f"/api/v1/kenya/transactions/{txn_id}/possession", json={})
    client.post(f"/api/v1/kenya/applications/{application_id}/offer", json={})
    client.post(f"/api/v1/kenya/applications/{application_id}/accept")
    client.post(f"/api/v1/kenya/applications/{application_id}/murabaha")
    client.post(f"/api/v1/kenya/applications/{application_id}/murabaha/sign", json={"signature_ref": "test"})
    client.post(f"/api/v1/kenya/transactions/{txn_id}/transfer")

    liquidate = client.post(f"/api/v1/kenya/transactions/{txn_id}/liquidate")
    assert liquidate.status_code == 400
    assert "wakala" in liquidate.json()["detail"].lower()


def test_no_inah_blocks_originating_agent_dealer(client):
    dealer = client.post(
        "/api/v1/kenya/agent-dealers",
        json={
            "business_name": "Dealer A",
            "mpesa_number": "254711999000",
            "code": "DEALER_A",
        },
    )
    assert dealer.status_code == 201
    topup = client.post(
        f"/api/v1/kenya/agent-dealers/{dealer.json()['id']}/topup",
        json={"amount": 200000},
    )
    assert topup.status_code == 200

    customer = client.post(
        "/api/v1/kenya/customers",
        json={"phone": "254700555667", "full_name": "Dealer Buyback", "wallet_number": "254700555667"},
    ).json()
    app_resp = client.post(
        "/api/v1/kenya/applications",
        json={
            "customer_id": customer["id"],
            "amount_requested": "10000.00",
            "term_months": 3,
            "purpose": "Test",
        },
    )
    application_id = app_resp.json()["id"]
    client.post(f"/api/v1/kenya/applications/{application_id}/eligibility")
    txn = client.post(
        "/api/v1/kenya/transactions",
        json={"application_id": application_id, "commodity_code": "FLOAT_MPESA_DEALER", "mode": "agent_dealer"},
    )
    assert txn.status_code == 201, txn.text
    txn_id = txn.json()["id"]
    purchase = client.post(f"/api/v1/kenya/transactions/{txn_id}/purchase")
    assert purchase.status_code == 200, purchase.text

    db = SessionLocal()
    try:
        buyback = ThirdPartyBroker(
            code="DEALER_A",
            name="Same Dealer A",
            mno_codes="FLOAT_MPESA_DEALER",
            is_mno_pool=False,
        )
        db.add(buyback)
        db.commit()
        commodity = db.get(CommodityTransaction, txn_id)
        assert validate_no_inah(db, commodity, broker=buyback) is False
    finally:
        db.close()


def test_no_inah_allows_independent_otc(client):
    application_id, txn_id = _eligible_application_with_txn(client)
    db = SessionLocal()
    try:
        otc = db.query(ThirdPartyBroker).filter(ThirdPartyBroker.code == "OTC_KENYA").first()
        txn = db.get(CommodityTransaction, txn_id)
        assert validate_no_inah(db, txn, broker=otc) is True
    finally:
        db.close()
