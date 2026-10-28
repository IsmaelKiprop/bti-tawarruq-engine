import os

os.environ["AMANAH_ENABLED"] = "false"
os.environ["KENYA_INTEGRATION_MODE"] = "mock"
os.environ["OPS_BOOTSTRAP_ADMIN_EMAIL"] = "admin@bti.local"
os.environ["OPS_BOOTSTRAP_ADMIN_PASSWORD"] = "ChangeMeNow!123"
os.environ["OPS_SESSION_SECRET"] = "test-session-secret"

from fastapi.testclient import TestClient

from tawarruq.config import get_settings
from tawarruq.database import Base, SessionLocal, engine, init_db
from tawarruq.enums import ApiKeyRole
from tawarruq.main import app
from tawarruq.services.application_service import get_or_create_default_institution
from tawarruq.services.ops_user_service import create_ops_user, ensure_bootstrap_admin


def _client():
    os.environ["AUTH_ENABLED"] = "true"
    get_settings.cache_clear()
    engine.dispose()
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    institution = get_or_create_default_institution(db)
    ensure_bootstrap_admin(db)
    ops, ops_pw = create_ops_user(
        db,
        email="fi.ops@bank.local",
        full_name="FI Ops",
        role=ApiKeyRole.INSTITUTION_OPS,
        institution_id=institution.id,
        temporary_password="OpsPass!123",
        must_change_password=False,
    )
    approver, appr_pw = create_ops_user(
        db,
        email="fi.approver@bank.local",
        full_name="FI Approver",
        role=ApiKeyRole.FI_APPROVER,
        institution_id=institution.id,
        temporary_password="ApprPass!123",
        must_change_password=False,
    )
    db.commit()
    ids = {
        "institution_id": institution.id,
        "ops_id": ops.id,
        "approver_id": approver.id,
        "ops_pw": ops_pw,
        "appr_pw": appr_pw,
    }
    db.close()
    return TestClient(app), ids


def _login(client: TestClient, email: str, password: str) -> dict:
    login = client.post("/api/v1/ops/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_desk_steps_otp_and_shariah_scope():
    client, ids = _client()
    ops = _login(client, "fi.ops@bank.local", ids["ops_pw"])
    approver = _login(client, "fi.approver@bank.local", ids["appr_pw"])

    blocked = client.post(
        "/api/v1/desk/cases",
        headers=ops,
        json={
            "customer_id": "CUST-MM",
            "document_type": "National ID",
            "customer_name": "Amina Otieno",
            "customer_phone": "+254700000001",
            "customer_email": "amina@example.com",
            "approved_facility_amount": "10000",
            "facility_product_type": "Mobile money float",
            "assigned_approver_id": ids["approver_id"],
        },
    )
    assert blocked.status_code == 400, blocked.text

    negative = client.post(
        "/api/v1/desk/cases",
        headers=ops,
        json={
            "customer_id": "CUST-NEG",
            "document_type": "National ID",
            "customer_name": "Amina Otieno",
            "customer_phone": "+254700000001",
            "customer_email": "amina@example.com",
            "approved_facility_amount": "-100",
            "facility_product_type": "Airtime",
            "assigned_approver_id": ids["approver_id"],
        },
    )
    assert negative.status_code == 400, negative.text

    created = client.post(
        "/api/v1/desk/cases",
        headers=ops,
        json={
            "customer_id": "CUST-1",
            "document_type": "National ID",
            "customer_name": "Amina Otieno",
            "customer_phone": "+254700000001",
            "customer_email": "amina@example.com",
            "approved_facility_amount": "10000",
            "facility_product_type": "Airtime",
            "assigned_approver_id": ids["approver_id"],
        },
    )
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]
    assert created.json()["status"] == "pending_approval"
    assert created.json()["current_step"] == 2

    early = client.post(f"/api/v1/desk/cases/{case_id}/steps/3", headers=ops, json={"fields": {"purchase_complete": "Yes"}})
    assert early.status_code == 400

    decided = client.post(
        f"/api/v1/desk/cases/{case_id}/decide",
        headers=approver,
        json={"decision": "approve", "comments": "Limit ok"},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["status"] == "approved"
    assert decided.json()["current_step"] == 3

    step3 = client.post(
        f"/api/v1/desk/cases/{case_id}/steps/3",
        headers=ops,
        json={"fields": {"purchase_complete": "Yes"}},
    )
    assert step3.status_code == 200, step3.text
    locked3 = client.post(
        f"/api/v1/desk/cases/{case_id}/steps/3",
        headers=ops,
        json={"fields": {"purchase_complete": "No"}},
    )
    assert locked3.status_code == 400

    sent = client.post(f"/api/v1/desk/cases/{case_id}/otp/send", headers=ops, json={"purpose": "murabaha"})
    assert sent.status_code == 200, sent.text
    code = sent.json()["dev_code"]
    assert code
    verified = client.post(
        f"/api/v1/desk/cases/{case_id}/otp/verify",
        headers=ops,
        json={"purpose": "murabaha", "code": code},
    )
    assert verified.status_code == 200, verified.text
    missing_facility = client.post(
        f"/api/v1/desk/cases/{case_id}/steps/4",
        headers=ops,
        json={"fields": {"profit": "500", "offer_reference": "OFF-1", "contract_reference": "CON-1"}},
    )
    assert missing_facility.status_code == 400
    step4 = client.post(
        f"/api/v1/desk/cases/{case_id}/steps/4",
        headers=ops,
        json={
            "fields": {
                "profit": "500",
                "offer_reference": "OFF-1",
                "contract_reference": "CON-1",
                "facility_account": "FAC-1001",
                "repayment_installments": "12",
                "first_installment_due_date": "2026-11-01",
                "last_installment_due_date": "2027-10-01",
            }
        },
    )
    assert step4.status_code == 200, step4.text

    otp5 = client.post(f"/api/v1/desk/cases/{case_id}/otp/send", headers=ops, json={"purpose": "agent"})
    assert otp5.status_code == 200, otp5.text
    ok5 = client.post(
        f"/api/v1/desk/cases/{case_id}/otp/verify",
        headers=ops,
        json={"purpose": "agent", "code": otp5.json()["dev_code"]},
    )
    assert ok5.status_code == 200, ok5.text
    step5 = client.post(f"/api/v1/desk/cases/{case_id}/steps/5", headers=ops, json={"fields": {}})
    assert step5.status_code == 200, step5.text

    otp6 = client.post(f"/api/v1/desk/cases/{case_id}/otp/send", headers=ops, json={"purpose": "casa"})
    assert otp6.status_code == 200, otp6.text
    ok6 = client.post(
        f"/api/v1/desk/cases/{case_id}/otp/verify",
        headers=ops,
        json={"purpose": "casa", "code": otp6.json()["dev_code"]},
    )
    assert ok6.status_code == 200, ok6.text
    missing_account = client.post(f"/api/v1/desk/cases/{case_id}/steps/6", headers=ops, json={"fields": {}})
    assert missing_account.status_code == 400
    step6 = client.post(
        f"/api/v1/desk/cases/{case_id}/steps/6",
        headers=ops,
        json={"fields": {"customer_account_number": "0112345678", "customer_branch": "Westlands"}},
    )
    assert step6.status_code == 200, step6.text
    assert step6.json()["payload"]["proceeds"]["customer_account_number"] == "0112345678"
    assert step6.json()["payload"]["proceeds"]["customer_branch"] == "Westlands"

    step7 = client.post(f"/api/v1/desk/cases/{case_id}/steps/7", headers=ops, json={"fields": {"settlement_ref": "CLR-1"}})
    assert step7.status_code == 200, step7.text
    step8 = client.post(f"/api/v1/desk/cases/{case_id}/steps/8", headers=ops, json={"fields": {}})
    assert step8.status_code == 200, step8.text
    assert step8.json()["status"] == "complete"
    assert step8.json()["payload"]["timestamps"]

    audit = client.get("/api/v1/desk/audit", headers=ops)
    assert audit.status_code == 200, audit.text
    assert any(row["entity_id"] == case_id for row in audit.json())
    get_settings.cache_clear()


def test_reveal_api_client_requires_session_password():
    client, ids = _client()
    admin = client.post("/api/v1/ops/auth/login", json={"email": "admin@bti.local", "password": "ChangeMeNow!123"})
    assert admin.status_code == 200
    token = admin.json()["access_token"]
    if admin.json().get("must_change_password"):
        changed = client.post(
            "/api/v1/ops/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={"current_password": "ChangeMeNow!123", "new_password": "AdminPass!123"},
        )
        assert changed.status_code == 200, changed.text
        token = changed.json()["access_token"]
        password = "AdminPass!123"
    else:
        password = "ChangeMeNow!123"
    headers = {"Authorization": f"Bearer {token}"}
    issued = client.post(
        f"/api/v1/institutions/{ids['institution_id']}/api-keys",
        headers=headers,
        json={"name": "desk-client", "role": "api_client"},
    )
    assert issued.status_code == 201, issued.text
    hidden = client.get(f"/api/v1/institutions/{ids['institution_id']}/api-keys/request", headers=headers)
    assert hidden.status_code == 200
    assert hidden.json()["api_key"] is None
    wrong = client.post(
        f"/api/v1/institutions/{ids['institution_id']}/api-keys/reveal",
        headers=headers,
        json={"password": "nope"},
    )
    assert wrong.status_code == 400
    shown = client.post(
        f"/api/v1/institutions/{ids['institution_id']}/api-keys/reveal",
        headers=headers,
        json={"password": password},
    )
    assert shown.status_code == 200, shown.text
    assert shown.json()["api_key"] == issued.json()["api_key"]
    get_settings.cache_clear()
