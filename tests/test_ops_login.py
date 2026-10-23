import os

os.environ["AMANAH_ENABLED"] = "false"
os.environ["KENYA_INTEGRATION_MODE"] = "mock"
os.environ["OPS_BOOTSTRAP_ADMIN_EMAIL"] = "admin@bti.local"
os.environ["OPS_BOOTSTRAP_ADMIN_PASSWORD"] = "ChangeMeNow!123"
os.environ["OPS_SESSION_SECRET"] = "test-session-secret"

from fastapi.testclient import TestClient

from tawarruq.config import get_settings
from tawarruq.database import Base, SessionLocal, engine, init_db
from tawarruq.main import app
from tawarruq.services.application_service import get_or_create_default_institution
from tawarruq.services.ops_user_service import ensure_bootstrap_admin


def setup_module():
    os.environ["AUTH_ENABLED"] = "true"
    get_settings.cache_clear()


def teardown_module():
    os.environ["AUTH_ENABLED"] = "false"
    get_settings.cache_clear()


def _client():
    get_settings.cache_clear()
    engine.dispose()
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    get_or_create_default_institution(db)
    ensure_bootstrap_admin(db)
    db.commit()
    db.close()
    return TestClient(app)


def test_ops_login_change_password_and_create_user():
    client = _client()

    denied = client.get("/api/v1/applications")
    assert denied.status_code == 401

    bad = client.post("/api/v1/ops/auth/login", json={"email": "admin@bti.local", "password": "wrong"})
    assert bad.status_code == 401

    login = client.post(
        "/api/v1/ops/auth/login",
        json={"email": "admin@bti.local", "password": "ChangeMeNow!123"},
    )
    assert login.status_code == 200
    body = login.json()
    assert body["must_change_password"] is True
    token = body["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    blocked = client.get("/api/v1/applications", headers=headers)
    assert blocked.status_code == 403

    changed = client.post(
        "/api/v1/ops/auth/change-password",
        headers=headers,
        json={"current_password": "ChangeMeNow!123", "new_password": "NewSecurePass!99"},
    )
    assert changed.status_code == 200
    assert changed.json()["must_change_password"] is False
    headers = {"Authorization": f"Bearer {changed.json()['access_token']}"}

    ok = client.get("/api/v1/applications", headers=headers)
    assert ok.status_code == 200

    institutions = client.get("/api/v1/institutions", headers=headers)
    assert institutions.status_code == 200
    institution_id = institutions.json()[0]["id"]

    created = client.post(
        "/api/v1/ops/auth/users",
        headers=headers,
        json={
            "email": "ops.user@bank.local",
            "full_name": "Ops User",
            "role": "institution_ops",
            "institution_id": institution_id,
        },
    )
    assert created.status_code == 201
    temp = created.json()["temporary_password"]
    assert temp

    ops_login = client.post(
        "/api/v1/ops/auth/login",
        json={"email": "ops.user@bank.local", "password": temp},
    )
    assert ops_login.status_code == 200
    assert ops_login.json()["must_change_password"] is True


def test_ops_user_update_reset_and_delete():
    client = _client()
    login = client.post(
        "/api/v1/ops/auth/login",
        json={"email": "admin@bti.local", "password": "ChangeMeNow!123"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    changed = client.post(
        "/api/v1/ops/auth/change-password",
        headers=headers,
        json={"current_password": "ChangeMeNow!123", "new_password": "NewSecurePass!99"},
    )
    headers = {"Authorization": f"Bearer {changed.json()['access_token']}"}
    institution_id = client.get("/api/v1/institutions", headers=headers).json()[0]["id"]

    created = client.post(
        "/api/v1/ops/auth/users",
        headers=headers,
        json={
            "email": "desk@bank.local",
            "full_name": "Desk User",
            "role": "institution_ops",
            "institution_id": institution_id,
        },
    )
    assert created.status_code == 201
    user_id = created.json()["id"]

    updated = client.patch(
        f"/api/v1/ops/auth/users/{user_id}",
        headers=headers,
        json={"full_name": "Desk Lead", "role": "institution_admin"},
    )
    assert updated.status_code == 200
    assert updated.json()["full_name"] == "Desk Lead"
    assert updated.json()["role"] == "institution_admin"

    reset = client.post(f"/api/v1/ops/auth/users/{user_id}/reset-password", headers=headers)
    assert reset.status_code == 200
    temp = reset.json()["temporary_password"]
    relogin = client.post("/api/v1/ops/auth/login", json={"email": "desk@bank.local", "password": temp})
    assert relogin.status_code == 200
    assert relogin.json()["must_change_password"] is True

    deactivated = client.patch(
        f"/api/v1/ops/auth/users/{user_id}",
        headers=headers,
        json={"active": False},
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["active"] is False
    blocked = client.post("/api/v1/ops/auth/login", json={"email": "desk@bank.local", "password": temp})
    assert blocked.status_code == 401

    deleted = client.delete(f"/api/v1/ops/auth/users/{user_id}", headers=headers)
    assert deleted.status_code == 204
    remaining = client.get("/api/v1/ops/auth/users", headers=headers)
    assert all(item["id"] != user_id for item in remaining.json())

    me = client.get("/api/v1/ops/auth/me", headers=headers).json()
    self_delete = client.delete(f"/api/v1/ops/auth/users/{me['user_id']}", headers=headers)
    assert self_delete.status_code == 400


def test_shariah_officer_can_change_own_password():
    client = _client()
    admin = client.post(
        "/api/v1/ops/auth/login",
        json={"email": "admin@bti.local", "password": "ChangeMeNow!123"},
    )
    admin_headers = {"Authorization": f"Bearer {admin.json()['access_token']}"}
    admin_headers = {
        "Authorization": f"Bearer {client.post('/api/v1/ops/auth/change-password', headers=admin_headers, json={'current_password': 'ChangeMeNow!123', 'new_password': 'NewSecurePass!99'}).json()['access_token']}"
    }
    institution_id = client.get("/api/v1/institutions", headers=admin_headers).json()[0]["id"]
    created = client.post(
        "/api/v1/ops/auth/users",
        headers=admin_headers,
        json={
            "email": "shariah@bank.local",
            "full_name": "Shariah Officer",
            "role": "shariah_officer",
            "institution_id": institution_id,
            "temporary_password": "TempShariah!1",
        },
    )
    assert created.status_code == 201
    login = client.post(
        "/api/v1/ops/auth/login",
        json={"email": "shariah@bank.local", "password": "TempShariah!1"},
    )
    assert login.status_code == 200
    assert login.json()["institution_id"] == institution_id
    assert login.json()["institution_name"]
    changed = client.post(
        "/api/v1/ops/auth/change-password",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        json={"current_password": "TempShariah!1", "new_password": "OfficerPass!22"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["must_change_password"] is False
    relogin = client.post(
        "/api/v1/ops/auth/login",
        json={"email": "shariah@bank.local", "password": "OfficerPass!22"},
    )
    assert relogin.status_code == 200


def test_invite_user_emails_temp_password_via_smtp(monkeypatch, tmp_path):
    """When SMTP is configured, invite emails the password and withholds it from the API."""
    os.environ["SMTP_HOST"] = "smtp.test.local"
    os.environ["SMTP_FROM"] = "ops@test.local"
    os.environ["CUSTOMER_MAIL_DIR"] = str(tmp_path / "mail")
    get_settings.cache_clear()

    sent: list[tuple[str, str, str]] = []

    def _fake_smtp(to_email: str, subject: str, body: str, attachments=None):
        sent.append((to_email, subject, body))
        return True

    monkeypatch.setattr(
        "tawarruq.services.customer_notify_service._send_smtp",
        _fake_smtp,
    )

    try:
        client = _client()
        login = client.post(
            "/api/v1/ops/auth/login",
            json={"email": "admin@bti.local", "password": "ChangeMeNow!123"},
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        headers = {
            "Authorization": f"Bearer {client.post('/api/v1/ops/auth/change-password', headers=headers, json={'current_password': 'ChangeMeNow!123', 'new_password': 'NewSecurePass!99'}).json()['access_token']}"
        }
        institution_id = client.get("/api/v1/institutions", headers=headers).json()[0]["id"]

        created = client.post(
            "/api/v1/ops/auth/users",
            headers=headers,
            json={
                "email": "invited@bank.local",
                "full_name": "Invited Ops",
                "role": "institution_ops",
                "institution_id": institution_id,
            },
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["smtp_sent"] is True
        assert body["temporary_password"] is None
        assert body["must_change_password"] is True
        assert "emailed" in body["invite_message"].lower()
        assert len(sent) == 1
        assert sent[0][0] == "invited@bank.local"
        assert "Temporary password:" in sent[0][2]
        assert "change this password" in sent[0][2].lower()

        # Extract password from the emailed body so we can prove login + force change.
        line = next(l for l in sent[0][2].splitlines() if l.startswith("Temporary password:"))
        temp = line.split(":", 1)[1].strip()
        ops_login = client.post(
            "/api/v1/ops/auth/login",
            json={"email": "invited@bank.local", "password": temp},
        )
        assert ops_login.status_code == 200
        assert ops_login.json()["must_change_password"] is True
    finally:
        os.environ.pop("SMTP_HOST", None)
        os.environ.pop("SMTP_FROM", None)
        os.environ.pop("CUSTOMER_MAIL_DIR", None)
        get_settings.cache_clear()
