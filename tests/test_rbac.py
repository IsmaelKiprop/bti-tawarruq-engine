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

    # Keep setup routes open; individual tests enable AUTH_ENABLED when needed.
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


def _create_key(db, institution_id: str, role: ApiKeyRole) -> str:
    _, raw = create_api_key(db, institution_id=institution_id, name=f"test-{role.value}", role=role)
    db.commit()
    return raw


def test_read_only_blocks_writes(client, monkeypatch):
    from tawarruq.config import get_settings

    db = SessionLocal()
    default = get_or_create_default_institution(db)
    db.commit()
    read_key = _create_key(db, default.id, ApiKeyRole.READ_ONLY)
    db.close()

    created = client.post(
        "/api/v1/applications",
        json={"amount_requested": "1000.00", "term_months": 3, "purpose": "Test"},
    )
    assert created.status_code == 201

    monkeypatch.setenv("AUTH_ENABLED", "true")
    get_settings.cache_clear()
    headers = {"X-API-Key": read_key}

    get_ok = client.get("/api/v1/applications", headers=headers)
    assert get_ok.status_code == 200

    post_blocked = client.post(
        "/api/v1/applications",
        headers=headers,
        json={"amount_requested": "1000.00", "term_months": 3, "purpose": "Test"},
    )
    assert post_blocked.status_code == 403
    blocked_delete = client.delete(f"/api/v1/applications/{created.json()['id']}", headers=headers)
    assert blocked_delete.status_code == 403

    get_settings.cache_clear()


def test_institution_ops_cannot_manage_credentials(client, monkeypatch):
    from tawarruq.config import get_settings

    db = SessionLocal()
    default = get_or_create_default_institution(db)
    db.commit()
    institution_id = default.id
    ops_key = _create_key(db, institution_id, ApiKeyRole.INSTITUTION_OPS)
    db.close()

    monkeypatch.setenv("AUTH_ENABLED", "true")
    get_settings.cache_clear()
    headers = {"X-API-Key": ops_key}

    blocked = client.post(
        f"/api/v1/institutions/{institution_id}/api-keys",
        headers=headers,
        json={"name": "should-fail"},
    )
    assert blocked.status_code == 403

    get_settings.cache_clear()


def test_platform_admin_cross_tenant(client, monkeypatch):
    from tawarruq.config import get_settings

    db = SessionLocal()
    default = get_or_create_default_institution(db)
    db.commit()
    admin_key = _create_key(db, default.id, ApiKeyRole.PLATFORM_ADMIN)

    other = client.post(
        "/api/v1/institutions",
        json={"name": "Other", "code": "OTH2", "bsas_mode": "mock"},
    )
    assert other.status_code == 201
    other_id = other.json()["id"]

    other_app = client.post(
        "/api/v1/applications",
        json={
            "institution_id": other_id,
            "amount_requested": "5000.00",
            "term_months": 6,
            "purpose": "Other tenant",
        },
    )
    assert other_app.status_code == 201
    db.close()

    monkeypatch.setenv("AUTH_ENABLED", "true")
    get_settings.cache_clear()
    headers = {"X-API-Key": admin_key}

    listed = client.get("/api/v1/applications", headers=headers)
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()}
    assert other_app.json()["id"] in ids

    get_settings.cache_clear()


def test_ops_metrics_and_auth_me(client, monkeypatch):
    from tawarruq.config import get_settings

    db = SessionLocal()
    default = get_or_create_default_institution(db)
    db.commit()
    admin_key = _create_key(db, default.id, ApiKeyRole.PLATFORM_ADMIN)
    db.close()

    monkeypatch.setenv("AUTH_ENABLED", "true")
    get_settings.cache_clear()
    headers = {"X-API-Key": admin_key}

    me = client.get("/api/v1/ops/auth/me", headers=headers)
    assert me.status_code == 200
    body = me.json()
    assert body["role"] == "platform_admin"
    assert "view_metrics" in body["permissions"]

    metrics = client.get("/api/v1/ops/metrics", headers=headers)
    assert metrics.status_code == 200
    assert "applications_total" in metrics.json()

    prom = client.get("/metrics")
    assert prom.status_code == 200
    assert "tawarruq_up" in prom.text

    get_settings.cache_clear()


def test_bti_ops_cross_tenant_without_manage_institutions(client, monkeypatch):
    from tawarruq.config import get_settings

    db = SessionLocal()
    default = get_or_create_default_institution(db)
    db.commit()
    bti_ops_key = _create_key(db, default.id, ApiKeyRole.BTI_OPS)
    db.close()

    monkeypatch.setenv("AUTH_ENABLED", "true")
    get_settings.cache_clear()
    headers = {"X-API-Key": bti_ops_key}

    me = client.get("/api/v1/ops/auth/me", headers=headers)
    assert me.status_code == 200
    perms = me.json()["permissions"]
    assert "write_bti_ops" in perms
    assert "manage_institutions" not in perms

    blocked = client.post(
        "/api/v1/institutions",
        headers=headers,
        json={"name": "Should Fail", "code": "NOPE", "bsas_mode": "mock"},
    )
    assert blocked.status_code == 403
    get_settings.cache_clear()


def test_fi_approver_cannot_write_ops_but_has_approve(client, monkeypatch):
    from tawarruq.config import get_settings

    db = SessionLocal()
    default = get_or_create_default_institution(db)
    db.commit()
    approver_key = _create_key(db, default.id, ApiKeyRole.FI_APPROVER)
    db.close()

    monkeypatch.setenv("AUTH_ENABLED", "true")
    get_settings.cache_clear()
    headers = {"X-API-Key": approver_key}

    me = client.get("/api/v1/ops/auth/me", headers=headers)
    assert me.status_code == 200
    perms = set(me.json()["permissions"])
    assert "approve_txn" in perms
    assert "write_ops" not in perms

    blocked = client.post(
        "/api/v1/applications",
        headers=headers,
        json={"amount_requested": "1000.00", "term_months": 3, "purpose": "Test"},
    )
    assert blocked.status_code == 403
    get_settings.cache_clear()


def test_api_client_role_allowed_for_keys(client, monkeypatch):
    from tawarruq.config import get_settings

    db = SessionLocal()
    default = get_or_create_default_institution(db)
    admin_key = _create_key(db, default.id, ApiKeyRole.PLATFORM_ADMIN)
    institution_id = default.id
    db.commit()
    db.close()

    monkeypatch.setenv("AUTH_ENABLED", "true")
    get_settings.cache_clear()
    headers = {"X-API-Key": admin_key}

    created = client.post(
        f"/api/v1/institutions/{institution_id}/api-keys",
        headers=headers,
        json={"name": "core-banking", "role": "api_client"},
    )
    assert created.status_code == 201
    assert created.json()["role"] == "api_client"
    get_settings.cache_clear()


def test_create_institution_requires_platform_admin(client, monkeypatch):
    from tawarruq.config import get_settings

    db = SessionLocal()
    default = get_or_create_default_institution(db)
    db.commit()
    institution_id = default.id
    ops_key = _create_key(db, institution_id, ApiKeyRole.INSTITUTION_OPS)
    db.close()

    monkeypatch.setenv("AUTH_ENABLED", "true")
    get_settings.cache_clear()
    headers = {"X-API-Key": ops_key}

    blocked = client.post(
        "/api/v1/institutions",
        headers=headers,
        json={"name": "Blocked Bank", "code": "BLK1", "bsas_mode": "mock"},
    )
    assert blocked.status_code == 403

    blocked_update = client.patch(
        f"/api/v1/institutions/{institution_id}",
        headers=headers,
        json={"name": "Renamed"},
    )
    assert blocked_update.status_code == 403

    blocked_delete = client.delete(f"/api/v1/institutions/{institution_id}", headers=headers)
    assert blocked_delete.status_code == 403

    get_settings.cache_clear()
