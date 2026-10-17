import os

os.environ["AMANAH_ENABLED"] = "false"
os.environ["KENYA_INTEGRATION_MODE"] = "mock"

from fastapi.testclient import TestClient

from tawarruq.database import Base, SessionLocal, engine, init_db
from tawarruq.enums import ApiKeyRole
from tawarruq.main import app
from tawarruq.services.application_service import get_or_create_default_institution
from tawarruq.services.auth_service import create_api_key


def _client():
    from tawarruq.config import get_settings

    get_settings.cache_clear()
    engine.dispose()
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    from tawarruq.services.seed_service import seed_kenya_defaults

    get_or_create_default_institution(db)
    seed_kenya_defaults(db)
    db.commit()
    db.close()
    return TestClient(app)


def _key(institution_id: str, role: ApiKeyRole) -> str:
    db = SessionLocal()
    _, raw = create_api_key(db, institution_id=institution_id, name=f"k-{role.value}", role=role)
    db.commit()
    db.close()
    return raw


def test_tenant_cannot_list_other_customers(monkeypatch):
    from tawarruq.config import get_settings

    with _client() as client:
        default_id = client.get("/api/v1/institutions").json()[0]["id"]
        other = client.post(
            "/api/v1/institutions",
            json={"name": "Other Sacco", "code": "OTH3", "bsas_mode": "mock"},
        ).json()
        client.post(
            "/api/v1/kenya/customers",
            json={
                "institution_id": other["id"],
                "phone": "254700000001",
                "full_name": "Other Member",
                "wallet_number": "254700000001",
            },
        )
        ops_key = _key(default_id, ApiKeyRole.INSTITUTION_OPS)
        monkeypatch.setenv("AUTH_ENABLED", "true")
        get_settings.cache_clear()
        listed = client.get("/api/v1/kenya/customers", headers={"X-API-Key": ops_key})
        assert listed.status_code == 200
        assert all(row["institution_id"] == default_id for row in listed.json())
        get_settings.cache_clear()


def test_shariah_officer_cannot_register_customer(monkeypatch):
    from tawarruq.config import get_settings

    with _client() as client:
        default_id = client.get("/api/v1/institutions").json()[0]["id"]
        key = _key(default_id, ApiKeyRole.SHARIAH_OFFICER)
        monkeypatch.setenv("AUTH_ENABLED", "true")
        get_settings.cache_clear()
        blocked = client.post(
            "/api/v1/kenya/customers",
            headers={"X-API-Key": key},
            json={"phone": "254700000002", "full_name": "No Write", "wallet_number": "254700000002"},
        )
        assert blocked.status_code == 403
        allowed = client.get("/api/v1/kenya/customers", headers={"X-API-Key": key})
        assert allowed.status_code == 200
        get_settings.cache_clear()


def test_institution_eligibility_decision():
    with _client() as client:
        created = client.post(
            "/api/v1/kenya/customers",
            json={
                "phone": "254700000003",
                "full_name": "Approved Member",
                "wallet_number": "254700000003",
                "kyc_status": "pending",
                "aml_status": "pending",
                "credit_score": 200,
            },
        )
        assert created.status_code == 201
        customer_id = created.json()["id"]
        application = client.post(
            "/api/v1/kenya/applications",
            json={"customer_id": customer_id, "amount_requested": "15000.00", "term_months": 6, "purpose": "Float"},
        )
        assert application.status_code == 201
        engine_gate = client.post(f"/api/v1/kenya/applications/{application.json()['id']}/eligibility")
        assert engine_gate.json()["eligibility_passed"] is False

        decision = client.post(
            f"/api/v1/kenya/applications/{application.json()['id']}/eligibility/decision",
            json={
                "passed": True,
                "kyc_status": "verified",
                "aml_status": "clear",
                "credit_score": 720,
                "decision_ref": "CORE-ELIG-1",
            },
        )
        assert decision.status_code == 200, decision.text
        assert decision.json()["eligibility_passed"] is True
        assert decision.json()["source"] == "institution"


def test_customer_kyc_patch():
    with _client() as client:
        created = client.post(
            "/api/v1/kenya/customers",
            json={
                "phone": "254700000004",
                "full_name": "Patch Member",
                "wallet_number": "254700000004",
                "kyc_status": "pending",
                "aml_status": "pending",
                "credit_score": 100,
            },
        )
        customer_id = created.json()["id"]
        patched = client.patch(
            f"/api/v1/kenya/customers/{customer_id}",
            json={"kyc_status": "verified", "aml_status": "clear", "credit_score": 680, "national_id": "998877"},
        )
        assert patched.status_code == 200
        body = patched.json()
        assert body["kyc_status"] == "verified"
        assert body["aml_status"] == "clear"
        assert body["credit_score"] == 680
        assert body["national_id"] == "998877"


def test_delete_customer_and_journeys():
    with _client() as client:
        created = client.post(
            "/api/v1/kenya/customers",
            json={
                "phone": "254700000005",
                "full_name": "Delete Member",
                "wallet_number": "254700000005",
            },
        )
        assert created.status_code == 201
        customer_id = created.json()["id"]
        application = client.post(
            "/api/v1/kenya/applications",
            json={"customer_id": customer_id, "amount_requested": "12000.00", "term_months": 6, "purpose": "Float"},
        )
        assert application.status_code == 201
        application_id = application.json()["id"]

        deleted = client.delete(f"/api/v1/kenya/customers/{customer_id}")
        assert deleted.status_code == 204
        missing_customer = client.get(f"/api/v1/kenya/customers/{customer_id}")
        assert missing_customer.status_code == 404
        missing_app = client.get(f"/api/v1/applications/{application_id}")
        assert missing_app.status_code == 404


def test_read_only_cannot_delete_customer(monkeypatch):
    from tawarruq.config import get_settings

    with _client() as client:
        default_id = client.get("/api/v1/institutions").json()[0]["id"]
        created = client.post(
            "/api/v1/kenya/customers",
            json={
                "phone": "254700000006",
                "full_name": "Keep Member",
                "wallet_number": "254700000006",
            },
        )
        customer_id = created.json()["id"]
        key = _key(default_id, ApiKeyRole.READ_ONLY)
        monkeypatch.setenv("AUTH_ENABLED", "true")
        get_settings.cache_clear()
        blocked = client.delete(f"/api/v1/kenya/customers/{customer_id}", headers={"X-API-Key": key})
        assert blocked.status_code == 403
        get_settings.cache_clear()
