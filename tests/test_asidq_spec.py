import os

os.environ["AMANAH_ENABLED"] = "false"
os.environ["KENYA_INTEGRATION_MODE"] = "mock"
os.environ["SEDANIA_MODE"] = "mock"

from decimal import Decimal

from tawarruq.integrations.sedania.client import (
    STATUS_ACCEPTED,
    STATUS_VALIDATION,
    SedaniaAsSidqClient,
    SedaniaTradeSubmit,
    alphanumeric_ref,
    certificate_password,
)


def test_ref_no_is_alphanumeric_and_capped():
    assert alphanumeric_ref("bti-abc-123") == "BTIABC123"
    assert len(alphanumeric_ref("x" * 200)) <= 100


def test_certificate_password_format():
    assert certificate_password("BTIABC", institution_prefix="BTI") == "BTI@BTIABC"


def test_live_client_posts_spec_trading_path(monkeypatch):
    os.environ["SEDANIA_API_URL"] = "https://twq-uat.assidqlink.com"
    os.environ["SEDANIA_API_KEY"] = "test-token"
    os.environ["SEDANIA_SIGN_REQUESTS"] = "true"
    from tawarruq.config import get_settings

    get_settings.cache_clear()
    captured: dict = {}

    class _Resp:
        status_code = 200

        def json(self):
            return {
                "ref_no": "BTI123",
                "status_code": 200,
                "status_desc": "SUCCESS",
                "message": {"description": "Trading data imported"},
            }

    class _FakeClient:
        def __init__(self, timeout=60.0, follow_redirects=False):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, method, url, content=None, headers=None, params=None):
            captured["method"] = method
            captured["url"] = url
            captured["body"] = content
            captured["headers"] = headers
            return _Resp()

    monkeypatch.setattr("tawarruq.integrations.sedania.client.httpx.Client", _FakeClient)
    client = SedaniaAsSidqClient()
    result = client.submit_trade(
        SedaniaTradeSubmit(
            ref_no="BTI123",
            cust_name="Amina Rahman",
            cust_id="201010108888",
            trading_amount=Decimal("2000"),
            product_code="P01",
            profit_amount=Decimal("200"),
            keep_commodity="N",
        )
    )
    assert result.status_code == STATUS_ACCEPTED
    assert captured["url"] == "https://twq-uat.assidqlink.com/api/v1/trading"
    assert captured["headers"]["Authorization"] == "Bearer test-token"
    assert captured["headers"]["X-Req-Signature"]
    import json

    body = json.loads(captured["body"])
    assert body["ref_no"] == "BTI123"
    assert body["cust_name"] == "Amina Rahman"
    assert body["trading_amount"] == 2000
    assert body["profit_amount"] == 200
    assert body["product_code"] == "P01"
    assert body["keep_commodity"] == "N"
    get_settings.cache_clear()
