from tawarruq.bsas.base import BSASBackend
from tawarruq.bsas.live import LiveBSASBackend
from tawarruq.bsas.manual_bridge import ManualBridgeBackend
from tawarruq.bsas.mock import MockBSASBackend
from tawarruq.config import get_settings
from tawarruq.enums import TransactionMode
from tawarruq.integrations.eiger.client import EigerTradingBackend


def get_bsas_backend(mode: str) -> BSASBackend:
    if mode in {TransactionMode.MOCK, "mock"}:
        return MockBSASBackend()
    if mode in {TransactionMode.MANUAL_BRIDGE, "manual_bridge"}:
        return ManualBridgeBackend()
    if mode in {TransactionMode.LIVE, "live"}:
        desk = (get_settings().malaysia_commodity_desk or "bsas").lower()
        if desk == "eiger":
            return EigerTradingBackend()
        return LiveBSASBackend()
    raise ValueError(f"Unknown commodity-desk mode: {mode}")
