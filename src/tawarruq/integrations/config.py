from dataclasses import dataclass

from tawarruq.config import Settings, get_settings


@dataclass
class InstitutionIntegrationProfile:
    """Resolved integration credentials for one institution (global defaults + overrides)."""

    institution_id: str
    kenya_mode: str  # live | mock

    mpesa_env: str = "sandbox"
    mpesa_consumer_key: str = ""
    mpesa_consumer_secret: str = ""
    mpesa_shortcode: str = ""
    mpesa_initiator_name: str = ""
    mpesa_security_credential: str = ""
    mpesa_stk_passkey: str = ""
    mpesa_b2c_command_id: str = "BusinessPayment"
    mpesa_b2c_result_url: str = ""
    mpesa_b2c_timeout_url: str = ""
    mpesa_stk_callback_url: str = ""
    mpesa_status_result_url: str = ""
    mpesa_status_timeout_url: str = ""

    mno_safaricom_api_url: str = ""
    mno_safaricom_api_key: str = ""
    mno_safaricom_dealer_code: str = ""
    mno_possession_callback_url: str = ""

    mno_airtel_api_url: str = ""
    mno_airtel_token_url: str = ""
    mno_airtel_client_id: str = ""
    mno_airtel_client_secret: str = ""

    broker_api_url: str = ""
    broker_api_key: str = ""

    @property
    def broker_configured(self) -> bool:
        return bool(self.broker_api_url)

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
            and self.mpesa_b2c_result_url
        )

    @property
    def mno_safaricom_configured(self) -> bool:
        return bool(self.mno_safaricom_api_url and self.mno_safaricom_dealer_code)

    @property
    def is_live(self) -> bool:
        return self.kenya_mode == "live"
