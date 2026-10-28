import os

os.environ["AMANAH_ENABLED"] = "false"
os.environ["KENYA_INTEGRATION_MODE"] = "mock"

import pytest
from fastapi.testclient import TestClient

from tawarruq.database import Base, SessionLocal, engine, init_db
from tawarruq.enums import ApiKeyRole
from tawarruq.main import app
from tawarruq.services.application_service import get_or_create_default_institution
from tawarruq.services.auth_service import create_api_key


@pytest.fixture
def client(monkeypatch):
    from tawarruq.config import get_settings

    monkeypatch.setenv("AUTH_ENABLED", "false")
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
    with TestClient(app) as test_client:
        yield test_client
    get_settings.cache_clear()


def _key(role: ApiKeyRole) -> str:
    db = SessionLocal()
    default = get_or_create_default_institution(db)
    _, raw = create_api_key(db, institution_id=default.id, name=f"kyc-{role.value}", role=role)
    db.commit()
    db.close()
    return raw


def _kyc(name="Coastal Islamic Bank", code="COAST1"):
    return {
        "legal_registered_name": name,
        "code": code,
        "institution_type": "BANK",
        "support_email": "ops@coastal.example",
        "main_telephone": "+254700000001",
        "primary_regulator": "CBK",
        "licence_number": "CBK-001",
        "licence_issue_date": "2024-01-15",
        "licence_status": "ACTIVE",
        "primary_contact_full_name": "Amina Hassan",
        "primary_contact_title": "Head of Islamic Banking",
        "primary_contact_work_email": "amina@coastal.example",
        "primary_contact_phone": "+254700000002",
        "authorized_signatories": [{"name": "Amina Hassan", "title": "Head of Islamic Banking"}],
        "representative_id_type": "NATIONAL_ID",
        "representative_id_number": "12345678",
        "representative_identity_verification_status": "VERIFIED",
        "authority_to_act_document_id": "BOARD-RES-2024-01",
        "settlement_bank_name": "Kenya Commercial Bank",
        "settlement_account_name": "Coastal Islamic Bank Settlement",
        "settlement_account_number": "123456789012",
        "settlement_currency": "KES",
        "settlement_account_verification_status": "VERIFIED",
        "expected_monthly_transaction_count": 120,
        "expected_monthly_transaction_value": "15000000.00",
        "typical_transaction_amount": "125000.00",
        "maximum_transaction_amount": "2000000.00",
        "target_go_live_date": "2026-12-01",
        "commercial_agreement_status": "SIGNED",
    }


def test_super_admin_submit_activates_and_allows_invite(client, monkeypatch):
    from tawarruq.config import get_settings

    admin = _key(ApiKeyRole.PLATFORM_ADMIN)
    monkeypatch.setenv("AUTH_ENABLED", "true")
    get_settings.cache_clear()
    headers = {"X-API-Key": admin}

    created = client.post("/api/v1/institutions/onboarding", headers=headers, json=_kyc())
    assert created.status_code == 201, created.text
    fi_id = created.json()["id"]
    assert created.json()["lifecycle_status"] == "draft"

    submitted = client.post(f"/api/v1/institutions/{fi_id}/onboarding/submit", headers=headers)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["lifecycle_status"] == "active"
    assert submitted.json()["application_status"] == "ACTIVE"

    invite = client.post(
        "/api/v1/ops/auth/users",
        headers=headers,
        json={
            "email": "fi.lead@coastal.example",
            "full_name": "FI Lead",
            "role": "institution_admin",
            "institution_id": fi_id,
        },
    )
    assert invite.status_code in {200, 201}, invite.text
    get_settings.cache_clear()


def test_bti_ops_submit_needs_super_admin_and_blocks_invite(client, monkeypatch):
    from tawarruq.config import get_settings

    ops = _key(ApiKeyRole.BTI_OPS)
    admin = _key(ApiKeyRole.PLATFORM_ADMIN)
    monkeypatch.setenv("AUTH_ENABLED", "true")
    get_settings.cache_clear()
    ops_headers = {"X-API-Key": ops}
    admin_headers = {"X-API-Key": admin}

    created = client.post("/api/v1/institutions/onboarding", headers=ops_headers, json=_kyc("Rift SACCO", "RIFT1"))
    assert created.status_code == 201, created.text
    fi_id = created.json()["id"]
    submitted = client.post(f"/api/v1/institutions/{fi_id}/onboarding/submit", headers=ops_headers)
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["lifecycle_status"] == "pending_approval"

    invite_body = {
        "email": "fi.lead@rift.example",
        "full_name": "FI Lead",
        "role": "institution_admin",
        "institution_id": fi_id,
    }
    blocked = client.post("/api/v1/ops/auth/users", headers=admin_headers, json=invite_body)
    assert blocked.status_code == 400
    ops_blocked = client.post("/api/v1/ops/auth/users", headers=ops_headers, json=invite_body)
    assert ops_blocked.status_code == 400

    decided = client.post(
        f"/api/v1/institutions/{fi_id}/onboarding/decide",
        headers=admin_headers,
        json={"decision": "approve"},
    )
    assert decided.status_code == 200, decided.text
    assert decided.json()["lifecycle_status"] == "active"

    desk_denied = client.post(
        "/api/v1/ops/auth/users",
        headers=ops_headers,
        json={
            "email": "desk.ops@rift.example",
            "full_name": "FI Ops",
            "role": "institution_ops",
            "institution_id": fi_id,
        },
    )
    assert desk_denied.status_code == 403

    invite = client.post("/api/v1/ops/auth/users", headers=ops_headers, json=invite_body)
    assert invite.status_code in {200, 201}, invite.text
    get_settings.cache_clear()


def test_fi_admin_cannot_onboard_or_see_other_tenant(client, monkeypatch):
    from tawarruq.config import get_settings

    admin = _key(ApiKeyRole.PLATFORM_ADMIN)
    fi = _key(ApiKeyRole.INSTITUTION_ADMIN)
    monkeypatch.setenv("AUTH_ENABLED", "true")
    get_settings.cache_clear()
    admin_headers = {"X-API-Key": admin}
    headers = {"X-API-Key": fi}

    other = client.post("/api/v1/institutions/onboarding", headers=admin_headers, json=_kyc("Other Bank", "OTH99"))
    assert other.status_code == 201
    other_id = other.json()["id"]

    assert client.post("/api/v1/institutions/onboarding", headers=headers, json=_kyc("Blocked Bank", "BLK99")).status_code == 403
    assert client.post("/api/v1/institutions", headers=headers, json={"name": "X", "code": "XXX"}).status_code == 403
    listed = client.get("/api/v1/institutions", headers=headers)
    assert listed.status_code == 200
    assert all(row["id"] != other_id for row in listed.json())
    assert client.get(f"/api/v1/institutions/{other_id}/onboarding", headers=headers).status_code == 403
    mine = next((row for row in listed.json() if row["id"] != other_id), None)
    assert mine
    own = client.get(f"/api/v1/institutions/{mine['id']}/onboarding", headers=headers)
    assert own.status_code == 200, own.text
    assert client.patch(
        f"/api/v1/institutions/{mine['id']}/onboarding",
        headers=headers,
        json={"trading_name": "Nope"},
    ).status_code == 403
    get_settings.cache_clear()


def test_incomplete_kyc_rejected_on_submit(client, monkeypatch):
    from tawarruq.config import get_settings

    admin = _key(ApiKeyRole.PLATFORM_ADMIN)
    monkeypatch.setenv("AUTH_ENABLED", "true")
    get_settings.cache_clear()
    headers = {"X-API-Key": admin}
    created = client.post(
        "/api/v1/institutions/onboarding",
        headers=headers,
        json={"legal_registered_name": "Thin File Bank", "code": "THIN1"},
    )
    assert created.status_code == 201
    fi_id = created.json()["id"]
    submitted = client.post(f"/api/v1/institutions/{fi_id}/onboarding/submit", headers=headers)
    assert submitted.status_code == 400
    get_settings.cache_clear()


def test_fi_admin_can_request_api_client_on_active_fi(client, monkeypatch):
    from tawarruq.config import get_settings

    admin = _key(ApiKeyRole.PLATFORM_ADMIN)
    fi = _key(ApiKeyRole.INSTITUTION_ADMIN)
    monkeypatch.setenv("AUTH_ENABLED", "true")
    get_settings.cache_clear()
    admin_headers = {"X-API-Key": admin}
    fi_headers = {"X-API-Key": fi}

    mine = client.get("/api/v1/institutions", headers=fi_headers).json()[0]["id"]
    admin_request = client.post(f"/api/v1/institutions/{mine}/api-keys/request", headers=admin_headers)
    assert admin_request.status_code == 400

    first = client.post(f"/api/v1/institutions/{mine}/api-keys/request", headers=fi_headers)
    assert first.status_code == 200, first.text
    assert first.json()["status"] == "requested"
    again = client.post(f"/api/v1/institutions/{mine}/api-keys/request", headers=fi_headers)
    assert again.status_code == 200
    assert again.json()["status"] == "requested"
    queued = client.get("/api/v1/institutions/api-client-requests", headers=admin_headers)
    assert queued.status_code == 200, queued.text
    assert any(row["institution_id"] == mine for row in queued.json())
    pending = client.get(f"/api/v1/institutions/{mine}/api-keys/request", headers=fi_headers)
    assert pending.status_code == 200
    assert pending.json()["status"] == "requested"
    assert pending.json()["api_key"] is None
    issued = client.post(
        f"/api/v1/institutions/{mine}/api-keys",
        headers=admin_headers,
        json={"name": "dib-api-client", "role": "api_client"},
    )
    assert issued.status_code == 201, issued.text
    shown = client.get(f"/api/v1/institutions/{mine}/api-keys/request", headers=fi_headers)
    assert shown.status_code == 200
    body = shown.json()
    assert body["status"] == "issued"
    assert body["api_key"] is None
    assert body["hmac_secret"] is None
    assert body["key_prefix"]
    blocked = client.post(
        f"/api/v1/institutions/{mine}/api-keys/reveal",
        headers=fi_headers,
        json={"password": "anything"},
    )
    assert blocked.status_code == 401
    get_settings.cache_clear()
