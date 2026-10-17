import hashlib
import uuid

from tawarruq.mno.base import (
    MnoPurchaseRequest,
    MnoPurchaseResponse,
    MnoPurchaseResult,
    PossessionVerifyRequest,
    PossessionVerifyResponse,
)


class MockMnoBackend:
    """Instant MNO airtime purchase with auto possession verification."""

    def purchase_airtime(self, request: MnoPurchaseRequest) -> MnoPurchaseResponse:
        batch_id = f"BATCH-{request.mno_code}-{uuid.uuid4().hex[:10].upper()}"
        receipt_id = f"RCPT-{uuid.uuid4().hex[:12].upper()}"
        asset_hash = hashlib.sha256(f"{batch_id}:{receipt_id}:{request.amount}".encode()).hexdigest()
        return MnoPurchaseResponse(
            result=MnoPurchaseResult.CONFIRMED,
            batch_id=batch_id,
            mno_receipt_id=receipt_id,
            asset_ref_hash=asset_hash,
        )

    def verify_possession(self, request: PossessionVerifyRequest) -> PossessionVerifyResponse:
        asset_hash = hashlib.sha256(f"{request.batch_id}:{request.mno_receipt_id}".encode()).hexdigest()
        return PossessionVerifyResponse(verified=True, asset_ref_hash=asset_hash)
