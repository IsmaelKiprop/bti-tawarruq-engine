from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENGINE_ROOT = Path(__file__).resolve().parents[2]


def _resolve_sqlite_url(url: str) -> str:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return url
    path = url[len(prefix):]
    if path.startswith(":memory:"):
        return url
    raw = Path(path)
    resolved = raw if raw.is_absolute() else (ENGINE_ROOT / raw).resolve()
    return f"sqlite:///{resolved.as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENGINE_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./tawarruq.db"
    amanah_enabled: bool = True
    amanah_poll_interval_seconds: int = 5
    amanah_write_enabled: bool = True
    amanah_escalation_webhook_url: str = ""
    amanah_certificate_timeout_seconds: int = 300

    bsas_live_api_url: str = ""
    bsas_live_api_key: str = ""
    malaysia_commodity_desk: str = "bsas"

    eiger_api_url: str = ""
    eiger_api_key: str = ""
    eiger_order_path: str = "/v1/orders"
    eiger_certificate_path: str = "/v1/certificates/{ref}"

    manual_bridge_inbox_dir: str = "./data/manual_bridge"
    manual_bridge_email_enabled: bool = False
    manual_bridge_email_to: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "amanah@bti-fintech.local"

    portal_public_url: str = "http://127.0.0.1:5173"
    customer_mail_dir: str = "./data/customer_mail"

    auth_enabled: bool = False
    api_key_header: str = "X-API-Key"
    callback_auth_token: str = ""
    callback_auth_header: str = "X-Callback-Token"
    ops_session_secret: str = ""
    ops_bootstrap_admin_email: str = "admin@bti.local"
    ops_bootstrap_admin_password: str = "ChangeMeNow!123"

    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    webhook_timeout_seconds: int = 10
    webhook_max_retries: int = 3

    kenya_integration_mode: str = "live"
    mpesa_env: str = "sandbox"
    mpesa_consumer_key: str = ""
    mpesa_consumer_secret: str = ""
    mpesa_shortcode: str = ""
    mpesa_initiator_name: str = ""
    mpesa_security_credential: str = ""
    mpesa_b2c_command_id: str = "BusinessPayment"
    mpesa_b2c_result_url: str = ""
    mpesa_b2c_timeout_url: str = ""
    mpesa_stk_passkey: str = ""
    mpesa_stk_callback_url: str = ""
    mpesa_status_result_url: str = ""
    mpesa_status_timeout_url: str = ""

    mno_safaricom_api_url: str = ""
    mno_safaricom_api_key: str = ""
    mno_safaricom_dealer_code: str = ""
    mno_airtel_api_url: str = ""
    mno_airtel_token_url: str = ""
    mno_airtel_client_id: str = ""
    mno_airtel_client_secret: str = ""
    mno_possession_callback_url: str = ""

    public_api_base_url: str = ""
    integration_encryption_key: str = ""
    broker_liquidation_api_url: str = ""
    broker_liquidation_api_key: str = ""

    sedania_mode: str = "mock"
    sedania_api_url: str = ""
    sedania_api_key: str = ""
    sedania_default_profit_rate: float = 0.05
    hmac_max_skew_seconds: int = 300
    legal_token_signing_key: str = ""
    certificate_retention_years: int = 7

    shariah_audit_service_url: str = ""
    shariah_audit_service_token: str = ""
    shariah_audit_database_url: str = "sqlite:///./data/shariah_audit.db"

    @model_validator(mode="after")
    def resolve_local_sqlite(self) -> Settings:
        object.__setattr__(self, "database_url", _resolve_sqlite_url(self.database_url))
        object.__setattr__(
            self,
            "shariah_audit_database_url",
            _resolve_sqlite_url(self.shariah_audit_database_url),
        )
        return self

    @property
    def bsas_live_configured(self) -> bool:
        return bool(self.bsas_live_api_url and self.bsas_live_api_key)

    @property
    def eiger_configured(self) -> bool:
        return bool(self.eiger_api_url and self.eiger_api_key)

    @property
    def broker_configured(self) -> bool:
        return bool(self.broker_liquidation_api_url)

    @property
    def sedania_configured(self) -> bool:
        return bool(self.sedania_api_url and self.sedania_api_key)

    @property
    def is_live_sedania(self) -> bool:
        return self.sedania_mode == "live" and self.sedania_configured

    @property
    def airtel_money_configured(self) -> bool:
        return bool(
            self.mno_airtel_api_url
            and self.mno_airtel_token_url
            and self.mno_airtel_client_id
            and self.mno_airtel_client_secret
        )

    @property
    def mpesa_configured(self) -> bool:
        return bool(
            self.mpesa_consumer_key
            and self.mpesa_consumer_secret
            and self.mpesa_shortcode
            and self.mpesa_initiator_name
            and self.mpesa_security_credential
        )

    @property
    def mno_safaricom_configured(self) -> bool:
        return bool(self.mno_safaricom_api_url and self.mno_safaricom_dealer_code)

    @property
    def is_live_kenya(self) -> bool:
        return self.kenya_mode == "live" if hasattr(self, "kenya_mode") else self.kenya_integration_mode == "live"

    @property
    def manual_bridge_path(self) -> Path:
        path = Path(self.manual_bridge_inbox_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def customer_mail_path(self) -> Path:
        path = Path(self.customer_mail_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    if "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
        s = Settings()
        env_auth = os.environ.get("AUTH_ENABLED", "false").lower()
        s.auth_enabled = env_auth in ("true", "1", "yes")
        s.kenya_integration_mode = os.environ.get("KENYA_INTEGRATION_MODE", "mock")
        s.sedania_mode = os.environ.get("SEDANIA_MODE", "mock")
        return s
    return Settings()
