import uuid

from tawarruq.bsas.base import BSASBackend, LegContext, LegExecutionResponse, LegExecutionResult
from tawarruq.enums import LegNumber


class MockBSASBackend(BSASBackend):
    """Instant confirmation for development and demos."""

    def execute_leg(self, context: LegContext) -> LegExecutionResponse:
        external_ref = f"MOCK-{context.transaction_id[:8]}-L{context.leg_number}-{uuid.uuid4().hex[:6].upper()}"
        cert_number = f"CERT-MOCK-{external_ref}"
        bsas_fee = 25.0 if context.leg_number == LegNumber.PURCHASE else None
        return LegExecutionResponse(
            result=LegExecutionResult.CONFIRMED,
            external_ref=external_ref,
            certificate_number=cert_number,
            issuer="BSAS-MOCK",
            bsas_fee=bsas_fee,
        )

    def get_certificate(self, external_ref: str) -> LegExecutionResponse | None:
        return LegExecutionResponse(
            result=LegExecutionResult.CONFIRMED,
            external_ref=external_ref,
            certificate_number=f"CERT-MOCK-{external_ref}",
            issuer="BSAS-MOCK",
        )
