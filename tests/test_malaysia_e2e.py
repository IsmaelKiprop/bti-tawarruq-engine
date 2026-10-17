import os

os.environ["AMANAH_ENABLED"] = "false"
os.environ["KENYA_INTEGRATION_MODE"] = "mock"

from fastapi.testclient import TestClient

from tawarruq.bsas.factory import get_bsas_backend
from tawarruq.config import get_settings
from tawarruq.database import Base, SessionLocal, engine, init_db
from tawarruq.enums import TransactionMode
from tawarruq.integrations.eiger.client import EigerTradingBackend
from tawarruq.main import app


def _client(tmp_path=None, monkeypatch=None):
    get_settings.cache_clear()
    if tmp_path is not None and monkeypatch is not None:
        monkeypatch.setenv("MANUAL_BRIDGE_INBOX_DIR", str(tmp_path))
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
    return TestClient(app)


def _accepted_application(client: TestClient) -> str:
    created = client.post(
        "/api/v1/applications",
        json={
            "customer_name": "Ahmad bin Ali",
            "currency": "MYR",
            "amount_requested": "100000.00",
            "term_months": 12,
            "purpose": "Working capital (Malaysia BSAS)",
        },
    )
    application_id = created.json()["id"]
    client.post(f"/api/v1/applications/{application_id}/offer", json={})
    client.post(f"/api/v1/applications/{application_id}/accept")
    return application_id


def test_malaysia_run_full_flow_mock():
    with _client() as client:
        application_id = _accepted_application(client)
        response = client.post(f"/api/v1/malaysia/applications/{application_id}/run-full-flow")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "completed"
        assert body["legs_confirmed"] == 3
        assert body["disbursement_id"]
        assert body["certificate_number"]

        journey = client.get(f"/api/v1/customer/applications/{application_id}/journey")
        assert journey.status_code == 200
        assert journey.json()["track"] == "malaysia"
        assert len(journey.json()["steps"]) == 8


def test_malaysia_manual_bridge_three_legs(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        application_id = _accepted_application(client)
        txn = client.post(
            "/api/v1/transactions",
            json={"application_id": application_id, "mode": "manual_bridge", "commodity_code": "PALM_OIL"},
        )
        transaction_id = txn.json()["id"]

        for leg_number, cert in (("1", "CERT-BSAS-L1"), ("2", "CERT-BSAS-L2"), ("3", "CERT-BSAS-L3")):
            advanced = client.post(f"/api/v1/manual-bridge/transactions/{transaction_id}/advance")
            assert advanced.status_code == 200, advanced.text
            confirm = client.post(
                f"/api/v1/transactions/{transaction_id}/legs/{leg_number}/confirm",
                json={"certificate_number": cert, "issuer": "BSAS"},
            )
            assert confirm.status_code == 200, confirm.text
            if leg_number == "2":
                status = client.get(f"/api/v1/applications/{application_id}/business-status")
                assert status.json()["ready_for_leg_3"] is True

        detail = client.get(f"/api/v1/transactions/{transaction_id}")
        assert detail.json()["status"] == "completed"

        disb = client.post(
            "/api/v1/disbursements",
            json={"application_id": application_id, "transaction_id": transaction_id},
        )
        assert disb.status_code == 201
        assert disb.json()["tawarruq_certificate"] is not None


def test_eiger_backend_selected_for_live_desk(monkeypatch):
    monkeypatch.setenv("MALAYSIA_COMMODITY_DESK", "eiger")
    get_settings.cache_clear()
    backend = get_bsas_backend(TransactionMode.LIVE)
    assert isinstance(backend, EigerTradingBackend)
    failed = backend.execute_leg(
        __import__("tawarruq.bsas.base", fromlist=["LegContext"]).LegContext(
            transaction_id="txn",
            leg_number="1",
            commodity_code="PALM_OIL",
            amount=1000,
            institution_code="DIB001",
            customer_ref="CUST-1",
        )
    )
    assert failed.result == "failed"
    get_settings.cache_clear()


def test_health_reports_malaysia_desk():
    with _client() as client:
        health = client.get("/health").json()
        assert health["malaysia_commodity_desk"] in {"bsas", "eiger"}
        assert "bsas_live_configured" in health
        assert "eiger_configured" in health
        assert health["manual_bridge_ready"] is True
