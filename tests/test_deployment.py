import os

os.environ.setdefault("AMANAH_ENABLED", "false")
os.environ.setdefault("KENYA_INTEGRATION_MODE", "mock")

from fastapi.testclient import TestClient

from tawarruq.config import get_settings
from tawarruq.database import Base, SessionLocal, engine, init_db
from tawarruq.deployment import normalize_mode, parse_products
from tawarruq.enums import ApiKeyRole
from tawarruq.main import create_app
from tawarruq.models.institution import Institution
from tawarruq.models.ops_user import OpsUser
from tawarruq.services.application_service import get_or_create_default_institution
from tawarruq.services.auth_service import create_api_key
from tawarruq.services.ops_seed_service import seed_ops_role_catalogue
from tawarruq.services.seed_service import seed_kenya_defaults


def _reset_db():
    get_settings.cache_clear()
    engine.dispose()
    Base.metadata.drop_all(bind=engine)
    init_db()


def test_normalize_mode_and_products():
    assert normalize_mode("on-prem") == "onprem"
    assert normalize_mode("managed") == "managed"
    assert parse_products("kenya,malaysia") == ["kenya", "malaysia"]
    assert "sacco" in parse_products("")


def test_health_exposes_managed_profile():
    get_settings.cache_clear()
    client = TestClient(create_app())
    payload = client.get("/health").json()
    assert payload["deployment_mode"] == "managed"
    assert "kenya" in payload["enabled_products"]
    assert payload["brand_name"]


def test_kenya_router_absent_when_product_disabled(monkeypatch):
    monkeypatch.setenv("ENABLED_PRODUCTS", "malaysia")
    get_settings.cache_clear()
    client = TestClient(create_app())
    missing = client.get("/api/v1/kenya/customers")
    assert missing.status_code == 404
    health = client.get("/health").json()
    assert health["enabled_products"] == ["malaysia"]


def test_onprem_seed_skips_demo_fis(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_MODE", "onprem")
    monkeypatch.setenv("BRAND_NAME", "Demo Bank")
    monkeypatch.setenv("ONPREM_INSTITUTION_CODE", "SITE")
    monkeypatch.setenv("OPS_SEED_USERS", "true")
    monkeypatch.setenv("OPS_SEED_EMAIL_DOMAIN", "demo-bank.test")
    _reset_db()
    db = SessionLocal()
    get_or_create_default_institution(db)
    seed_kenya_defaults(db)
    seed_ops_role_catalogue(db)
    db.commit()
    codes = {row.code for row in db.query(Institution).all()}
    assert "MWALIMU" not in codes
    assert "DIB" not in codes
    emails = {row.email for row in db.query(OpsUser).all()}
    assert not any(email.startswith("bti.ops@") for email in emails)
    assert any(email.startswith("admin@") or email.startswith("fi.admin@") for email in emails)
    db.close()
    get_settings.cache_clear()


def test_onprem_institution_admin_can_issue_api_keys(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_MODE", "onprem")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    _reset_db()
    db = SessionLocal()
    institution = get_or_create_default_institution(db)
    db.commit()
    _, raw = create_api_key(db, institution_id=institution.id, name="fi-admin", role=ApiKeyRole.INSTITUTION_ADMIN)
    db.commit()
    institution_id = institution.id
    db.close()

    client = TestClient(create_app())
    created = client.post(
        f"/api/v1/institutions/{institution_id}/api-keys",
        headers={"X-API-Key": raw},
        json={"name": "cbs-client", "role": "api_client"},
    )
    assert created.status_code == 201, created.text
    get_settings.cache_clear()


def test_managed_institution_admin_cannot_issue_api_keys(monkeypatch):
    monkeypatch.setenv("DEPLOYMENT_MODE", "managed")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    _reset_db()
    db = SessionLocal()
    institution = get_or_create_default_institution(db)
    db.commit()
    _, raw = create_api_key(db, institution_id=institution.id, name="fi-admin", role=ApiKeyRole.INSTITUTION_ADMIN)
    db.commit()
    institution_id = institution.id
    db.close()

    client = TestClient(create_app())
    blocked = client.post(
        f"/api/v1/institutions/{institution_id}/api-keys",
        headers={"X-API-Key": raw},
        json={"name": "cbs-client", "role": "api_client"},
    )
    assert blocked.status_code == 403
    get_settings.cache_clear()
