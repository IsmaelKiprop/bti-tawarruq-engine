from pydantic import BaseModel, Field


class MobileRegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=2, max_length=255)


class MobileVerifyEmailRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    code: str = Field(min_length=6, max_length=8)


class MobileResendVerificationRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)


class MobileLoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class MobileMfaVerifyRequest(BaseModel):
    mfa_token: str
    code: str = Field(min_length=6, max_length=8)


class MobileRefreshRequest(BaseModel):
    refresh_token: str


class MobileProfileRequest(BaseModel):
    phone: str = Field(min_length=12, max_length=32)
    wallet_provider: str = "mpesa"
    wallet_number: str | None = None


class MobileForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)


class MobileResetPasswordRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    code: str = Field(min_length=6, max_length=8)
    new_password: str = Field(min_length=12, max_length=128)


class MobileChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)


class MobileClaimInviteRequest(BaseModel):
    invite_code: str = Field(min_length=4, max_length=32)


class MobileAccountRead(BaseModel):
    id: str
    email: str
    full_name: str
    email_verified: bool
    customer_id: str | None = None
    institution_id: str | None = None
    institution_name: str | None = None
    agent_dealer_name: str | None = None
    agent_float_available: str | None = None
    kyc_status: str | None = None
    national_id: str | None = None
    unread_notifications: int = 0
    has_customer_profile: bool = False
    approval_status: str = "pending"
    phone: str | None = None
    credit_limit: str | None = None
    credit_utilized: str | None = None
    available_limit: str | None = None
    can_borrow: bool = False
    approval_message: str | None = None
    rejection_reason: str | None = None
    has_invite: bool = False


class MobileInviteCreate(BaseModel):
    institution_id: str
    email: str = Field(min_length=5, max_length=255)
    phone: str | None = None
    full_name: str | None = None
    credit_limit: str = "100000"
    activate_on_claim: bool = False
    expires_days: int = 14


class MobileApproveRequest(BaseModel):
    institution_id: str | None = None
    phone: str = Field(min_length=12, max_length=32)
    credit_limit: str = "100000"
    credit_score: int = 680


class MobileRejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=512)


class MobileAuthDelivery(BaseModel):
    smtp_sent: bool = False
    mail_path: str | None = None
    dev_code: str | None = None
    status: str | None = None


class MobileRegisterResponse(MobileAuthDelivery):
    email: str
    message: str


class MobileLoginChallengeResponse(MobileAuthDelivery):
    mfa_required: bool = True
    mfa_token: str
    email: str
    expires_in: int


class MobileTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    account: MobileAccountRead


class MobileKycSubmitRequest(BaseModel):
    national_id: str = Field(min_length=5, max_length=64)
    id_document_b64: str | None = None
    selfie_b64: str | None = None


class MobilePushTokenRequest(BaseModel):
    push_token: str = Field(min_length=8, max_length=512)
