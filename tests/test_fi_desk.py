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


def test_desk_steps_journey_and_shariah_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("CUSTOMER_MAIL_DIR", str(tmp_path / "mail"))
    get_settings.cache_clear()
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
            "profit": "500",
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
            "profit": "500",
        },
    )
    assert negative.status_code == 400, negative.text

    missing_profit = client.post(
        "/api/v1/desk/cases",
        headers=ops,
        json={
            "customer_id": "CUST-NP",
            "document_type": "National ID",
            "customer_name": "Amina Otieno",
            "customer_phone": "+254700000001",
            "customer_email": "amina@example.com",
            "approved_facility_amount": "10000",
            "facility_product_type": "Airtime",
            "assigned_approver_id": ids["approver_id"],
        },
    )
    assert missing_profit.status_code == 400, missing_profit.text

    created = client.post(
        "/api/v1/desk/cases",
        headers=ops,
        json={
            "customer_name": "Amina Otieno",
            "customer_email": "amina@example.com",
            "customer_phone": "+254700000001",
            "approved_facility_amount": "10000",
            "assigned_approver_id": ids["approver_id"],
            "profit": "500",
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
    assert decided.json()["status"] == "in_progress"
    assert decided.json()["current_step"] == 4
    journey = decided.json()["payload"]["journey"]
    assert journey["customer_ref"]
    assert journey["application_id"]
    offer_mail = tmp_path / "mail" / f"{journey['customer_ref']}.txt"
    assert offer_mail.exists(), list((tmp_path / "mail").glob("*"))
    mail_text = offer_mail.read_text(encoding="utf-8")
    assert "Accept your Murabaha offer" in mail_text
    assert f"/customer/{journey['customer_ref']}" in mail_text

    locked3 = client.post(
        f"/api/v1/desk/cases/{case_id}/steps/3",
        headers=ops,
        json={"fields": {"purchase_complete": "No"}},
    )
    assert locked3.status_code == 400

    missing_accept = client.post(
        f"/api/v1/desk/cases/{case_id}/steps/4",
        headers=ops,
        json={"fields": {"profit": "500"}},
    )
    assert missing_accept.status_code == 400, missing_accept.text
    assert "accept" in missing_accept.json()["detail"].lower()

    accepted = client.post(f"/api/v1/customer/applications/{journey['customer_ref']}/accept")
    assert accepted.status_code == 200, accepted.text
    finished = client.get(f"/api/v1/desk/cases/{case_id}", headers=ops)
    assert finished.status_code == 200, finished.text
    body = finished.json()
    assert body["payload"]["journey"]["offer_accepted"] is True
    assert body["status"] == "complete"
    workflow = body["payload"].get("workflow") or []
    titles = [row.get("title") for row in workflow if isinstance(row, dict)]
    assert "Offer Letter accepted" not in titles
    assert "Customer offer emailed" not in titles
    assert titles.count("Commodity purchase Sedania to FI") == 1
    assert titles.count("Murabaha sale FI to Customer") == 1
    assert titles.count("Commodity sale Customer to Sedania") == 1
    assert "Workflow complete" in titles
    # Sequence: origination → approve → purchase → murabaha → customer sale → complete
    purchase_i = titles.index("Commodity purchase Sedania to FI")
    murabaha_i = titles.index("Murabaha sale FI to Customer")
    sale_i = titles.index("Commodity sale Customer to Sedania")
    done_i = titles.index("Workflow complete")
    assert purchase_i < murabaha_i < sale_i < done_i
    cert_kinds: list[str] = []
    for row in workflow:
        if isinstance(row, dict) and row.get("certificates"):
            cert_kinds.extend(row["certificates"])
    assert "sedania_to_fi" in cert_kinds
    assert "fi_to_customer" in cert_kinds
    assert "customer_to_sedania" in cert_kinds
    assert body["payload"]["initiate"]["commodity_seller"] == "Sedania"
    assert body["payload"]["initiate"]["commodity_agent"] == "Buruuj Fintech"
    assert body["payload"]["murabaha"]["agent_name"] == "Buruuj Fintech"
    assert body["payload"]["customer_sale"]["buyer_name"] == "Sedania"
    pdfs = list((tmp_path / "mail").glob("*certificate.pdf"))
    assert pdfs, list((tmp_path / "mail").iterdir())
    assert any("sedania_to_fi" in p.name for p in pdfs)
    assert any("fi_to_customer" in p.name for p in pdfs)
    assert any("customer_to_sedania" in p.name for p in pdfs)

    for kind in ("sedania_to_fi", "fi_to_customer", "customer_to_sedania"):
        dl = client.get(f"/api/v1/desk/cases/{case_id}/certificates/{kind}", headers=ops)
        assert dl.status_code == 200, dl.text
        assert dl.headers.get("content-type", "").startswith("application/pdf")
    resent = client.post(f"/api/v1/desk/cases/{case_id}/certificates/resend", headers=ops)
    assert resent.status_code == 200, resent.text
    assert resent.json()["attachments"] == 3
    assert resent.json()["kind"] == "all"

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
