from tawarruq.integrations.config import InstitutionIntegrationProfile
from tawarruq.integrations.mno.airtime import get_airtime_client
from tawarruq.mno.base import (
    MnoPurchaseRequest,
    MnoPurchaseResponse,
    PossessionVerifyRequest,
    PossessionVerifyResponse,
)


class LiveMnoBackend:
    """Live Safaricom / Airtel airtime partner APIs (per institution)."""

    def __init__(self, profile: InstitutionIntegrationProfile) -> None:
        self.profile = profile

    def purchase_airtime(self, request: MnoPurchaseRequest) -> MnoPurchaseResponse:
        client = get_airtime_client(request.mno_code, self.profile)
        return client.purchase_airtime(request)

    def verify_possession(self, request: PossessionVerifyRequest) -> PossessionVerifyResponse:
        client = get_airtime_client(request.mno_code, self.profile)
        return client.verify_possession(request)
