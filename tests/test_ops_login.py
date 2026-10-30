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


def _login(client, email: str, password: str) -> dict:
    login = client.post("/api/v1/ops/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return login.json()


def _change_password(client, token: str, current: str, new: str) -> dict:
    changed = client.post(
        "/api/v1/ops/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": current, "new_password": new},
    )
    assert changed.status_code == 200, changed.text
    return changed.json()


def _super_admin_headers(client) -> tuple[dict, str]:
    login = _login(client, "admin@bti.local", "ChangeMeNow!123")
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    if login.get("must_change_password"):
        changed = _change_password(client, login["access_token"], "ChangeMeNow!123", "NewSecurePass!99")
        headers = {"Authorization": f"Bearer {changed['access_token']}"}
    institution_id = client.get("/api/v1/institutions", headers=headers).json()[0]["id"]
    return headers, institution_id


def _invite_fi_admin(client, headers: dict, institution_id: str, email="fi.admin@bank.local") -> tuple[str, str]:
    created = client.post(
        "/api/v1/ops/auth/users",
        headers=headers,
        json={
            "email": email,
            "full_name": "FI Admin",
            "role": "institution_admin",
            "institution_id": institution_id,
        },
    )
    assert created.status_code == 201, created.text
    temp = created.json()["temporary_password"]
    assert temp
    return created.json()["id"], temp


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

    _, fi_temp = _invite_fi_admin(client, headers, institution_id, email="ops.admin@bank.local")
    fi_login = _login(client, "ops.admin@bank.local", fi_temp)
    fi_changed = _change_password(client, fi_login["access_token"], fi_temp, "FiAdminPass!22")
    fi_headers = {"Authorization": f"Bearer {fi_changed['access_token']}"}

    created = client.post(
        "/api/v1/ops/auth/users",
        headers=fi_headers,
        json={
            "email": "ops.user@bank.local",
            "full_name": "Ops User",
            "role": "institution_ops",
            "institution_id": institution_id,
        },
    )
    assert created.status_code == 201, created.text
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
    headers, institution_id = _super_admin_headers(client)

    created = client.post(
        "/api/v1/ops/auth/users",
        headers=headers,
        json={
            "email": "desk@bank.local",
            "full_name": "Desk User",
            "role": "institution_admin",
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


def test_shariah_officer_audit_at_bti_and_fi_level():
    client = _client()
    admin_headers, institution_id = _super_admin_headers(client)

    bti_created = client.post(
        "/api/v1/ops/auth/users",
        headers=admin_headers,
        json={
            "email": "bti.shariah@bank.local",
            "full_name": "BTI Shariah Officer",
            "role": "shariah_officer",
            "temporary_password": "TempBtiShariah!1",
        },
    )
    assert bti_created.status_code == 201, bti_created.text
    assert bti_created.json()["institution_id"] is None

    fi_created = client.post(
        "/api/v1/ops/auth/users",
        headers=admin_headers,
        json={
            "email": "fi.shariah@bank.local",
            "full_name": "FI Shariah Officer",
            "role": "shariah_officer",
            "institution_id": institution_id,
            "temporary_password": "TempFiShariah!1",
        },
    )
    assert fi_created.status_code == 201, fi_created.text
    assert fi_created.json()["institution_id"] == institution_id

    bti_login = _login(client, "bti.shariah@bank.local", "TempBtiShariah!1")
    assert bti_login["institution_id"] is None
    bti_changed = _change_password(client, bti_login["access_token"], "TempBtiShariah!1", "BtiShariahPass!22")
    bti_headers = {"Authorization": f"Bearer {bti_changed['access_token']}"}

    fi_login = _login(client, "fi.shariah@bank.local", "TempFiShariah!1")
    assert fi_login["institution_id"] == institution_id
    fi_changed = _change_password(client, fi_login["access_token"], "TempFiShariah!1", "FiShariahPass!22")
    fi_headers = {"Authorization": f"Bearer {fi_changed['access_token']}"}

    bti_books = client.get("/api/v1/institutions", headers=bti_headers)
    assert bti_books.status_code == 200
    assert len(bti_books.json()) >= 1
    assert client.get("/api/v1/desk/audit", headers=bti_headers).status_code == 200
    assert client.get("/api/v1/desk/cases", headers=bti_headers).status_code == 200

    fi_books = client.get("/api/v1/institutions", headers=fi_headers)
    assert fi_books.status_code == 200
    assert [item["id"] for item in fi_books.json()] == [institution_id]
    assert client.get("/api/v1/desk/audit", headers=fi_headers).status_code == 200
    assert client.get("/api/v1/desk/cases", headers=fi_headers).status_code == 200


def test_super_admin_sets_sedania_charge_pct():
    client = _client()
    admin_headers, institution_id = _super_admin_headers(client)
    password = "NewSecurePass!99"

    loaded = client.get("/api/v1/ops/settings", headers=admin_headers)
    assert loaded.status_code == 200, loaded.text
    assert loaded.json()["sedania_charge_pct"] == 0.0035
    assert loaded.json()["active_provider"] == "sedania"
    assert loaded.json()["rate_pct"] == 0.0035
    assert any(item["id"] == institution_id and item["bti_charge_pct"] == 0.004 for item in loaded.json()["institutions"])

    denied = client.patch(
        "/api/v1/ops/settings",
        headers=admin_headers,
        json={"sedania_charge_pct": 0.01},
    )
    assert denied.status_code == 400

    def _otp() -> str:
        challenge = client.post("/api/v1/ops/settings/challenge", headers=admin_headers, json={"password": password})
        assert challenge.status_code == 200, challenge.text
        code = challenge.json()["dev_code"]
        assert code
        return code

    saved = client.patch(
        "/api/v1/ops/settings",
        headers=admin_headers,
        json={
            "password": password,
            "otp_code": _otp(),
            "sedania_charge_pct": 0.0035,
            "institutions": [{"id": institution_id, "bti_charge_pct": 0.004}],
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["sedania_charge_pct"] == 0.0035
    assert saved.json()["active_provider"] == "sedania"

    second_sedania = client.patch(
        "/api/v1/ops/settings",
        headers=admin_headers,
        json={
            "password": password,
            "otp_code": _otp(),
            "active_provider": "sedania",
            "rate_pct": 0.005,
        },
    )
    assert second_sedania.status_code == 200, second_sedania.text
    assert second_sedania.json()["active_provider"] == "sedania"
    assert second_sedania.json()["rate_pct"] == 0.005
    assert second_sedania.json()["sedania_charge_pct"] == 0.005

    bursa = client.patch(
        "/api/v1/ops/settings",
        headers=admin_headers,
        json={
            "password": password,
            "otp_code": _otp(),
            "active_provider": "bursa",
            "rate_pct": 0.01,
        },
    )
    assert bursa.status_code == 200, bursa.text
    assert bursa.json()["active_provider"] == "bursa"
    assert bursa.json()["rate_pct"] == 0.01
    me = client.get("/api/v1/ops/auth/me", headers=admin_headers)
    assert me.status_code == 200, me.text
    assert me.json()["active_provider"] == "bursa"

    restored = client.patch(
        "/api/v1/ops/settings",
        headers=admin_headers,
        json={
            "password": password,
            "otp_code": _otp(),
            "active_provider": "sedania",
            "rate_pct": 0.0035,
            "institutions": [{"id": institution_id, "bti_charge_pct": 0.004}],
        },
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["active_provider"] == "sedania"
    assert restored.json()["rate_pct"] == 0.0035

    too_high = client.patch(
        "/api/v1/ops/settings",
        headers=admin_headers,
        json={"password": password, "otp_code": "000000", "sedania_charge_pct": 101},
    )
    assert too_high.status_code in {400, 403, 422}

    _, temp = _invite_fi_admin(client, admin_headers, institution_id, email="fi.admin.settings@bank.local")
    fi_login = _login(client, "fi.admin.settings@bank.local", temp)
    fi_changed = _change_password(client, fi_login["access_token"], temp, "FiAdminPass!22")
    fi_headers = {"Authorization": f"Bearer {fi_changed['access_token']}"}
    blocked = client.get("/api/v1/ops/settings", headers=fi_headers)
    assert blocked.status_code == 403
    blocked_patch = client.patch("/api/v1/ops/settings", headers=fi_headers, json={"sedania_charge_pct": 8})
    assert blocked_patch.status_code == 403


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
                "full_name": "Invited Admin",
                "role": "institution_admin",
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


def test_super_admin_cannot_invite_fi_ops_or_approver():
    client = _client()
    headers, institution_id = _super_admin_headers(client)

    for role in ("institution_ops", "fi_approver"):
        denied = client.post(
            "/api/v1/ops/auth/users",
            headers=headers,
            json={
                "email": f"{role}@bank.local",
                "full_name": role,
                "role": role,
                "institution_id": institution_id,
            },
        )
        assert denied.status_code == 403, denied.text
        assert "not allowed to invite" in denied.json()["detail"].lower()

    fi_id, _ = _invite_fi_admin(client, headers, institution_id, email="desk.lead.patch@bank.local")
    patched = client.patch(
        f"/api/v1/ops/auth/users/{fi_id}",
        headers=headers,
        json={"role": "institution_ops"},
    )
    assert patched.status_code == 403, patched.text


def test_fi_admin_cannot_invite_bti_roles():
    client = _client()
    headers, institution_id = _super_admin_headers(client)
    _, fi_temp = _invite_fi_admin(client, headers, institution_id)
    fi_login = _login(client, "fi.admin@bank.local", fi_temp)
    fi_changed = _change_password(client, fi_login["access_token"], fi_temp, "FiAdminPass!22")
    fi_headers = {"Authorization": f"Bearer {fi_changed['access_token']}"}

    for role in ("platform_admin", "bti_ops", "bti_finance"):
        denied = client.post(
            "/api/v1/ops/auth/users",
            headers=fi_headers,
            json={
                "email": f"{role}@bank.local",
                "full_name": role,
                "role": role,
            },
        )
        assert denied.status_code == 403, denied.text
        assert "not allowed to invite" in denied.json()["detail"].lower()


def test_fi_ops_cannot_invite_anyone():
    client = _client()
    headers, institution_id = _super_admin_headers(client)
    _, fi_temp = _invite_fi_admin(client, headers, institution_id)
    fi_login = _login(client, "fi.admin@bank.local", fi_temp)
    fi_changed = _change_password(client, fi_login["access_token"], fi_temp, "FiAdminPass!22")
    fi_headers = {"Authorization": f"Bearer {fi_changed['access_token']}"}

    ops = client.post(
        "/api/v1/ops/auth/users",
        headers=fi_headers,
        json={
            "email": "desk.ops@bank.local",
            "full_name": "FI Ops",
            "role": "institution_ops",
        },
    )
    assert ops.status_code == 201, ops.text
    ops_temp = ops.json()["temporary_password"]
    ops_login = _login(client, "desk.ops@bank.local", ops_temp)
    ops_changed = _change_password(client, ops_login["access_token"], ops_temp, "FiOpsPass!33")
    ops_headers = {"Authorization": f"Bearer {ops_changed['access_token']}"}

    denied = client.post(
        "/api/v1/ops/auth/users",
        headers=ops_headers,
        json={
            "email": "another@bank.local",
            "full_name": "Another",
            "role": "institution_ops",
        },
    )
    assert denied.status_code == 403, denied.text


def test_fi_admin_cannot_create_api_key():
    client = _client()
    headers, institution_id = _super_admin_headers(client)
    _, fi_temp = _invite_fi_admin(client, headers, institution_id)
    fi_login = _login(client, "fi.admin@bank.local", fi_temp)
    fi_changed = _change_password(client, fi_login["access_token"], fi_temp, "FiAdminPass!22")
    fi_headers = {"Authorization": f"Bearer {fi_changed['access_token']}"}

    denied = client.post(
        f"/api/v1/institutions/{institution_id}/api-keys",
        headers=fi_headers,
        json={"name": "should-fail", "role": "api_client"},
    )
    assert denied.status_code == 403, denied.text
    assert "super admin" in denied.json()["detail"].lower()


def test_login_writes_evidence_and_ui_click_is_audited():
    client = _client()
    headers, _institution_id = _super_admin_headers(client)

    failed = client.post("/api/v1/ops/auth/login", json={"email": "nobody@bti.local", "password": "wrong-pass-99"})
    assert failed.status_code == 401

    ui = client.post(
        "/api/v1/ops/audit/ui",
        headers=headers,
        json={"action": "ui.click", "label": "Invite user", "path": "/users"},
    )
    assert ui.status_code == 204, ui.text

    feed = client.get("/api/v1/ops/audit?grouped=false&limit=500", headers=headers)
    assert feed.status_code == 200, feed.text
    events = feed.json()["events"]
    login_ok = [event for event in events if event["action"] == "auth.login_ok" and event.get("evidence_ref")]
    assert login_ok
    assert "email=" in login_ok[-1]["evidence_ref"]
    assert "mfa=" in login_ok[-1]["evidence_ref"]
    login_failed = [event for event in events if event["action"] == "auth.login_failed" and event.get("evidence_ref")]
    assert login_failed
    ui_events = [event for event in events if event["action"] == "ui.click"]
    assert ui_events
    assert ui_events[-1]["action_group"] == "ui"
    assert "Invite user" in (ui_events[-1]["evidence_ref"] or "")


def test_super_admin_cannot_patch_to_machine_role():
    client = _client()
    headers, institution_id = _super_admin_headers(client)
    user_id, _ = _invite_fi_admin(client, headers, institution_id, email="desk.lead@bank.local")

    denied = client.patch(
        f"/api/v1/ops/auth/users/{user_id}",
        headers=headers,
        json={"role": "api_client"},
    )
    assert denied.status_code == 403, denied.text
    assert "not allowed to invite" in denied.json()["detail"].lower()
