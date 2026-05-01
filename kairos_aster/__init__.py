"""
kairos-aster-sdk — Community Python SDK for AsterDEX V3 API.

Quick start:
    from kairos_aster import FuturesClient

    client = FuturesClient(
        user="0xYourMainWallet",
        signer="0xYourAgentWallet",
        private_key="0xAgentPrivateKey",
    )
    print(client.ticker_price("BTCUSDT"))
    order = client.place_order("BTCUSDT", "BUY", "MARKET", quantity=0.01)

Built by Kairos Lab — https://kairos-lab.org
"""

__version__ = "0.2.0"

from .futures import FuturesClient
from .spot import SpotClient
from .ws import AsterWS, StreamRouter
from .auth import generate_agent_wallet, sign_request
from .errors import AsterAPIError, AsterRequestError
from .enums import (
    Side, OrderType, TimeInForce, PositionSide,
    MarginType, WorkingType, TransferType, KlineInterval,
)

__all__ = [
    "FuturesClient",
    "SpotClient",
    "AsterWS",
    "StreamRouter",
    "generate_agent_wallet",
    "sign_request",
    "AsterAPIError",
    "AsterRequestError",
    "Side",
    "OrderType",
    "TimeInForce",
    "PositionSide",
    "MarginType",
    "WorkingType",
    "TransferType",
    "KlineInterval",
]
