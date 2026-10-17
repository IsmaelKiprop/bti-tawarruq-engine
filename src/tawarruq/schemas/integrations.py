from pydantic import BaseModel, Field


class InstitutionIntegrationUpdate(BaseModel):
    kenya_mode: str | None = Field(None, description="live | mock | null=inherit platform default")
    callback_base_url: str | None = Field(
        None,
        description="Public HTTPS base for this institution, e.g. https://bank-a.api.bti.fintech",
        examples=["https://bank-a.api.bti.fintech"],
    )
    mpesa_env: str | None = Field(None, examples=["sandbox", "production"])
    mpesa_consumer_key: str | None = None
    mpesa_consumer_secret: str | None = None
    mpesa_shortcode: str | None = None
    mpesa_initiator_name: str | None = None
    mpesa_security_credential: str | None = None
    mpesa_stk_passkey: str | None = None
    mpesa_b2c_command_id: str | None = None
    mno_safaricom_api_url: str | None = None
    mno_safaricom_api_key: str | None = None
    mno_safaricom_dealer_code: str | None = None
    mno_airtel_api_url: str | None = None
    mno_airtel_token_url: str | None = None
    mno_airtel_client_id: str | None = None
    mno_airtel_client_secret: str | None = None
    active: bool | None = None


class InstitutionIntegrationRead(BaseModel):
    institution_id: str
    kenya_mode: str | None
    callback_base_url: str | None
    mpesa_env: str | None
    mpesa_shortcode: str | None
    mpesa_initiator_name: str | None
    mpesa_b2c_command_id: str | None
    mno_safaricom_api_url: str | None
    mno_safaricom_dealer_code: str | None
    mno_airtel_api_url: str | None
    mno_airtel_token_url: str | None = None
    mno_airtel_client_id: str | None
    active: bool
    mpesa_consumer_key_set: bool = False
    mpesa_consumer_secret_set: bool = False
    mpesa_security_credential_set: bool = False
    mpesa_stk_passkey_set: bool = False
    mno_safaricom_api_key_set: bool = False
    mno_airtel_client_secret_set: bool = False


class InstitutionIntegrationStatusRead(BaseModel):
    institution_id: str
    kenya_mode: str
    mpesa_configured: bool
    mno_safaricom_configured: bool
    callback_urls: dict[str, str]
