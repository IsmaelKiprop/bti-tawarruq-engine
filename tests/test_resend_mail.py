"""Outbound mail must go through Resend (not SMTP)."""

from __future__ import annotations

import io
import json
from urllib.error import HTTPError

import pytest


class _FakeResponse:
    def __init__(self, status: int = 200, body: bytes = b'{"id":"re_test"}'):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_send_outbound_email_requires_resend_key(monkeypatch):
    from tawarruq.config import get_settings
    from tawarruq.services import customer_notify_service as mail

    get_settings.cache_clear()
    monkeypatch.setenv("RESEND_API_KEY", "")
    get_settings.cache_clear()
    assert mail.send_outbound_email("ops@example.com", "Hi", "Body") is False
    get_settings.cache_clear()


def test_send_outbound_email_posts_to_resend(monkeypatch):
    from tawarruq.config import get_settings
    from tawarruq.services import customer_notify_service as mail

    get_settings.cache_clear()
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    monkeypatch.setenv("RESEND_FROM", "ops@buruujfintech.com")
    get_settings.cache_clear()

    captured: dict = {}

    def fake_urlopen(request, timeout=30):
        captured["url"] = request.full_url
        captured["auth"] = request.get_header("Authorization")
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse()

    import urllib.request as ur

    monkeypatch.setattr(ur, "urlopen", fake_urlopen)

    assert mail.send_outbound_email("fi.ops@example.com", "Invite", "temp pass") is True
    assert captured["url"] == "https://api.resend.com/emails"
    assert captured["auth"] == "Bearer re_test_key"
    assert captured["payload"]["to"] == ["fi.ops@example.com"]
    assert "Buruuj Fintech" in captured["payload"]["from"]
    assert "ops@buruujfintech.com" in captured["payload"]["from"]
    get_settings.cache_clear()


def test_send_outbound_email_retries_without_attachments(monkeypatch):
    from tawarruq.config import get_settings
    from tawarruq.services import customer_notify_service as mail

    get_settings.cache_clear()
    monkeypatch.setenv("RESEND_API_KEY", "re_test_key")
    get_settings.cache_clear()

    calls: list[dict] = []

    def fake_urlopen(request, timeout=30):
        payload = json.loads(request.data.decode("utf-8"))
        calls.append(payload)
        if payload.get("attachments"):
            raise HTTPError(
                request.full_url,
                422,
                "Unprocessable",
                hdrs=None,
                fp=io.BytesIO(b'{"message":"attachment too large"}'),
            )
        return _FakeResponse()

    import urllib.request as ur

    monkeypatch.setattr(ur, "urlopen", fake_urlopen)

    ok = mail.send_outbound_email(
        "customer@example.com",
        "Offer",
        "Accept link",
        attachments=[("offer.pdf", b"%PDF-1.4 test", "application/pdf")],
    )
    assert ok is True
    assert len(calls) == 2
    assert "attachments" in calls[0]
    assert "attachments" not in calls[1]
    get_settings.cache_clear()
