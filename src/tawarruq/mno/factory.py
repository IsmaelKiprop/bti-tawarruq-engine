from tawarruq.enums import TransactionMode
from tawarruq.integrations.config import InstitutionIntegrationProfile
from tawarruq.mno.live import LiveMnoBackend
from tawarruq.mno.mock import MockMnoBackend


def get_mno_backend(mode: str, profile: InstitutionIntegrationProfile) -> LiveMnoBackend | MockMnoBackend:
    if mode == TransactionMode.MOCK or profile.kenya_mode == "mock":
        return MockMnoBackend()
    return LiveMnoBackend(profile)
