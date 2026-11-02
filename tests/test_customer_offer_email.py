import os
from decimal import Decimal

os.environ["AMANAH_ENABLED"] = "false"
os.environ["KENYA_INTEGRATION_MODE"] = "mock"

from tawarruq.config import get_settings
from tawarruq.database import Base, SessionLocal, engine, init_db
from tawarruq.services.application_service import (
    create_application,
    create_offer,
    get_or_create_default_institution,
)
from tawarruq.services.customer_service import create_customer


def _fresh_db():
    get_settings.cache_clear()
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    institution = get_or_create_default_institution(db)
    db.commit()
    return db, institution


def test_offer_lock_writes_customer_mail(tmp_path):
    os.environ["CUSTOMER_MAIL_DIR"] = str(tmp_path)
    db, institution = _fresh_db()
    customer = create_customer(
        db,
        institution_id=institution.id,
        phone="254700999000",
        email="accept.me@example.com",
        full_name="Accept Me",
        wallet_number="254700999000",
    )
    application = create_application(
        db,
        customer_id=customer.id,
        amount_requested=Decimal("10000.00"),
        term_months=3,
        purpose="Offer email test",
        institution_id=institution.id,
    )
    create_offer(db, application.id)
    db.commit()
    mail = tmp_path / f"{application.customer_ref}.txt"
    assert mail.exists()
    text = mail.read_text(encoding="utf-8")
    assert "accept.me@example.com" in text
    assert "/customer/" in text
    assert application.customer_ref in text
    db.close()


def test_send_uses_resend_when_api_key_set(monkeypatch):
    import json

    os.environ["RESEND_API_KEY"] = "re_test_key"
    os.environ["RESEND_FROM"] = "ops@buruujfintech.com"
    os.environ.pop("SMTP_HOST", None)
    get_settings.cache_clear()
    captured: dict = {}

    class _FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b'{"id":"email_test"}'

    def _fake_urlopen(request, timeout=20):
        captured["url"] = request.full_url
        captured["auth"] = request.get_header("Authorization")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    from tawarruq.services.customer_notify_service import _send_smtp

    try:
        assert _send_smtp("customer@bank.local", "Accept your offer", "Open this link") is True
        assert captured["url"] == "https://api.resend.com/emails"
        assert captured["auth"] == "Bearer re_test_key"
        assert captured["body"]["to"] == ["customer@bank.local"]
        assert captured["body"]["from"] == "Buruuj Fintech <ops@buruujfintech.com>"
        assert captured["body"]["subject"] == "Accept your offer"
    finally:
        os.environ.pop("RESEND_API_KEY", None)
        os.environ.pop("RESEND_FROM", None)
        get_settings.cache_clear()


def test_offer_lock_skips_without_email(tmp_path):
    os.environ["CUSTOMER_MAIL_DIR"] = str(tmp_path)
    db, institution = _fresh_db()
    customer = create_customer(
        db,
        institution_id=institution.id,
        phone="254700999001",
        full_name="No Mail",
        wallet_number="254700999001",
    )
    application = create_application(
        db,
        customer_id=customer.id,
        amount_requested=Decimal("10000.00"),
        term_months=3,
        purpose="No email test",
        institution_id=institution.id,
    )
    create_offer(db, application.id)
    db.commit()
    assert list(tmp_path.iterdir()) == []
    db.close()
