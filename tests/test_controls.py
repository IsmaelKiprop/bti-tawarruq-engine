import os

os.environ["AMANAH_ENABLED"] = "false"
os.environ["KENYA_INTEGRATION_MODE"] = "mock"

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from tawarruq.database import Base, SessionLocal, engine, init_db
from tawarruq.enums import ApiKeyRole
from tawarruq.main import app
from tawarruq.services.application_service import get_or_create_default_institution
from tawarruq.services.auth_service import create_api_key
from tawarruq.services.ops_user_service import create_ops_user, create_session_token
from tawarruq.services.seed_service import seed_kenya_defaults
from tawarruq.services.totp_service import totp_now, verify_totp


@pytest.fixture
def client(monkeypatch):
    from tawarruq.config import get_settings

    monkeypatch.setenv("AUTH_ENABLED", "false")
    get_settings.cache_clear()
    engine.dispose()
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    get_or_create_default_institution(db)
    seed_kenya_defaults(db)
    db.commit()
    db.close()
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def _key(db, institution_id, role):
    _, raw = create_api_key(db, institution_id=institution_id, name=f"k-{role.value}", role=role)
    db.commit()
    return raw


def _enable_auth(monkeypatch):
    from tawarruq.config import get_settings

    monkeypatch.setenv("AUTH_ENABLED", "true")
    get_settings.cache_clear()


def test_platform_admin_has_no_trade_execution(client, monkeypatch):
    db = SessionLocal()
    default = get_or_create_default_institution(db)
    admin_key = _key(db, default.id, ApiKeyRole.PLATFORM_ADMIN)
    db.close()
    _enable_auth(monkeypatch)
    headers = {"X-API-Key": admin_key}
    me = client.get("/api/v1/ops/auth/me", headers=headers)
    assert me.status_code == 200
    perms = set(me.json()["permissions"])
    assert "write_ops" not in perms
    assert "approve_txn" not in perms
    assert "write_bti_ops" in perms
    assert "manage_institutions" in perms
    blocked = client.post(
        "/api/v1/applications",
        headers=headers,
        json={"amount_requested": "1000.00", "term_months": 3, "purpose": "Should fail"},
    )
    assert blocked.status_code == 403


def test_maker_checker_queues_murabaha_and_blocks_self_approve(client, monkeypatch):
    db = SessionLocal()
    default = get_or_create_default_institution(db)
    institution_id = default.id
    ops_user, _ = create_ops_user(
        db,
        email="ops.maker@test.local",
        full_name="Maker",
        role=ApiKeyRole.INSTITUTION_OPS,
        institution_id=institution_id,
        temporary_password="MakerPass1!",
        must_change_password=False,
    )
    approver, _ = create_ops_user(
        db,
        email="approver@test.local",
        full_name="Approver",
        role=ApiKeyRole.FI_APPROVER,
        institution_id=institution_id,
        temporary_password="ApprPass1!",
        must_change_password=False,
        approval_limit_amount="100000",
    )
    db.commit()
    maker_token = create_session_token(ops_user)
    approver_token = create_session_token(approver)
    db.close()

    app_resp = client.post(
        "/api/v1/applications",
        json={"amount_requested": "25000.00", "term_months": 3, "purpose": "Float"},
    )
    assert app_resp.status_code == 201
    application_id = app_resp.json()["id"]
    offer = client.post(f"/api/v1/applications/{application_id}/offer", json={"profit_rate_pct": 5})
    assert offer.status_code in {200, 201}

    _enable_auth(monkeypatch)
    queued = client.post(
        f"/api/v1/applications/{application_id}/accept",
        headers={"Authorization": f"Bearer {maker_token}"},
    )
    assert queued.status_code == 202
    approval_id = queued.json()["approval_id"]

    self_approve = client.post(
        f"/api/v1/ops/approvals/{approval_id}/approve",
        headers={"Authorization": f"Bearer {maker_token}"},
        json={},
    )
    assert self_approve.status_code == 403

    approved = client.post(
        f"/api/v1/ops/approvals/{approval_id}/approve",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={"note": "Within limit"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "executed"


def test_approval_limit_blocks_over_cap(client, monkeypatch):
    db = SessionLocal()
    default = get_or_create_default_institution(db)
    institution_id = default.id
    default.approval_limit_amount = 1000
    db.add(default)
    ops_user, _ = create_ops_user(
        db,
        email="ops.limit@test.local",
        full_name="Maker",
        role=ApiKeyRole.INSTITUTION_OPS,
        institution_id=institution_id,
        temporary_password="MakerPass1!",
        must_change_password=False,
    )
    approver, _ = create_ops_user(
        db,
        email="approver.limit@test.local",
        full_name="Approver",
        role=ApiKeyRole.FI_APPROVER,
        institution_id=institution_id,
        temporary_password="ApprPass1!",
        must_change_password=False,
    )
    db.commit()
    maker_token = create_session_token(ops_user)
    approver_token = create_session_token(approver)
    db.close()

    app_resp = client.post(
        "/api/v1/applications",
        json={"amount_requested": "25000.00", "term_months": 3, "purpose": "Float"},
    )
    application_id = app_resp.json()["id"]
    client.post(f"/api/v1/applications/{application_id}/offer", json={"profit_rate_pct": 5})
    _enable_auth(monkeypatch)
    queued = client.post(
        f"/api/v1/applications/{application_id}/accept",
        headers={"Authorization": f"Bearer {maker_token}"},
    )
    assert queued.status_code == 202
    denied = client.post(
        f"/api/v1/ops/approvals/{queued.json()['approval_id']}/approve",
        headers={"Authorization": f"Bearer {approver_token}"},
        json={},
    )
    assert denied.status_code == 400
    assert "limit" in denied.json()["detail"].lower()


def test_tenant_suspend_blocks_writes(client, monkeypatch):
    db = SessionLocal()
    default = get_or_create_default_institution(db)
    institution_id = default.id
    admin_key = _key(db, institution_id, ApiKeyRole.PLATFORM_ADMIN)
    ops_key = _key(db, institution_id, ApiKeyRole.INSTITUTION_OPS)
    db.close()
    _enable_auth(monkeypatch)
    suspended = client.patch(
        f"/api/v1/institutions/{institution_id}",
        headers={"X-API-Key": admin_key},
        json={"active": False},
    )
    assert suspended.status_code == 200
    assert suspended.json()["active"] is False
    blocked = client.post(
        "/api/v1/applications",
        headers={"X-API-Key": ops_key},
        json={"amount_requested": "1000.00", "term_months": 3, "purpose": "Suspended"},
    )
    assert blocked.status_code == 403


def test_billing_and_reconciliation(client, monkeypatch):
    db = SessionLocal()
    default = get_or_create_default_institution(db)
    institution_id = default.id
    finance_key = _key(db, institution_id, ApiKeyRole.BTI_FINANCE)
    recon_key = _key(db, institution_id, ApiKeyRole.RECONCILER)
    db.close()

    start = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    _enable_auth(monkeypatch)
    invoice = client.post(
        "/api/v1/ops/billing/invoices",
        headers={"X-API-Key": finance_key},
        json={"institution_id": institution_id, "period_start": start, "period_end": end},
    )
    assert invoice.status_code == 201
    assert invoice.json()["status"] == "issued"

    scan = client.post("/api/v1/ops/reconciliation/scan", headers={"X-API-Key": recon_key})
    assert scan.status_code == 200
    listed = client.get("/api/v1/ops/reconciliation", headers={"X-API-Key": recon_key})
    assert listed.status_code == 200


def test_write_bti_ops_retry_endpoint(client, monkeypatch):
    db = SessionLocal()
    default = get_or_create_default_institution(db)
    institution_id = default.id
    bti_ops = _key(db, institution_id, ApiKeyRole.BTI_OPS)
    finance = _key(db, institution_id, ApiKeyRole.BTI_FINANCE)
    db.close()
    created = client.post(
        "/api/v1/kenya/customers",
        json={"phone": "254700000333", "full_name": "Retry Customer", "wallet_number": "254700000333"},
    )
    app_resp = client.post(
        "/api/v1/kenya/applications",
        json={
            "customer_id": created.json()["id"],
            "amount_requested": "5000.00",
            "term_months": 3,
            "purpose": "Retry",
        },
    )
    application_id = app_resp.json()["id"]
    _enable_auth(monkeypatch)
    denied = client.post(
        f"/api/v1/kenya/ops/cases/{application_id}/retry",
        headers={"X-API-Key": finance},
    )
    assert denied.status_code == 403
    ok = client.post(
        f"/api/v1/kenya/ops/cases/{application_id}/retry",
        headers={"X-API-Key": bti_ops},
    )
    assert ok.status_code == 200
    assert ok.json()["application_id"] == application_id


def test_totp_roundtrip():
    from tawarruq.services.totp_service import generate_totp_secret

    secret = generate_totp_secret()
    code = totp_now(secret)
    assert verify_totp(secret, code)
    assert not verify_totp(secret, "000000")
