"""
AsterDEX Spot V3 client.

Usage:
    from kairos_aster import SpotClient

    client = SpotClient(
        user="0xYourMainWallet",
        signer="0xYourAgentWallet",
        private_key="0xYourAgentPrivateKey",
    )
    order = client.place_order("ASTERUSDT", "BUY", "MARKET", quantity=100)

Spot V3 rollout status (as of 2026-04-19):
    Some endpoints listed in the official docs are not yet active server-side.
    Confirmed non-functional: account(), commission_rate().
    Confirmed working: all public endpoints, place_order(), cancel_order(),
    open_orders(), all_orders(), trades_history(), transfer(), withdraw().
    Ref: Aster support ticket + Discord #api-discussion 2026-04-19.
"""

from __future__ import annotations

import warnings
from typing import Any

from .client import BaseClient
from .auth import SPOT_STRICT_KEYS

# Endpoints confirmed non-functional server-side during Spot v3 rollout.
# The SDK code is correct (EIP-712); the limitation is on Aster's backend.
_SERVER_UNIMPLEMENTED = frozenset(["/api/v3/account", "/api/v3/commissionRate"])

_BASE = "https://sapi.asterdex.com"
_TESTNET = "https://sapi.asterdex-testnet.com"


class SpotClient(BaseClient):
    """Full Spot V3 REST client."""

    def __init__(
        self,
        user: str,
        signer: str,
        private_key: str,
        *,
        testnet: bool = False,
        timeout: int = 10,
        max_retries: int = 3,
        show_weight: bool = False,
    ) -> None:
        base = _TESTNET if testnet else _BASE
        super().__init__(
            user, signer, private_key, base,
            timeout=timeout, max_retries=max_retries, show_weight=show_weight,
        )

    # ═══════════════════════════════════════════════════════════════════
    #  PUBLIC — Market Data
    # ═══════════════════════════════════════════════════════════════════

    def ping(self) -> dict:
        return self.get_public("/api/v3/ping")

    def server_time(self) -> dict:
        return self.get_public("/api/v3/time")

    def exchange_info(self) -> dict:
        return self.get_public("/api/v3/exchangeInfo")

    def depth(self, symbol: str, limit: int = 100) -> dict:
        return self.get_public("/api/v3/depth", {"symbol": symbol, "limit": limit})

    def trades(self, symbol: str, limit: int = 500) -> list:
        return self.get_public("/api/v3/trades", {"symbol": symbol, "limit": limit})

    def klines(self, symbol: str, interval: str, limit: int = 500, **kw) -> list:
        return self.get_public(
            "/api/v3/klines",
            {"symbol": symbol, "interval": interval, "limit": limit, **kw},
        )

    def ticker_24hr(self, symbol: str | None = None) -> Any:
        params = {"symbol": symbol} if symbol else {}
        return self.get_public("/api/v3/ticker/24hr", params)

    def ticker_price(self, symbol: str | None = None) -> Any:
        params = {"symbol": symbol} if symbol else {}
        return self.get_public("/api/v3/ticker/price", params)

    def book_ticker(self, symbol: str | None = None) -> Any:
        params = {"symbol": symbol} if symbol else {}
        return self.get_public("/api/v3/ticker/bookTicker", params)

    # ═══════════════════════════════════════════════════════════════════
    #  SIGNED — Orders
    # ═══════════════════════════════════════════════════════════════════

    def place_order(
        self,
        symbol: str,
        side: str,
        type: str,
        *,
        quantity: float | str | None = None,
        quote_order_qty: float | str | None = None,
        price: float | str | None = None,
        time_in_force: str | None = None,
        new_client_order_id: str | None = None,
    ) -> dict:
        params: dict[str, Any] = {"symbol": symbol, "side": side, "type": type}
        if quantity is not None:
            params["quantity"] = str(quantity)
        if quote_order_qty is not None:
            params["quoteOrderQty"] = str(quote_order_qty)
        if price is not None:
            params["price"] = str(price)
        if time_in_force:
            params["timeInForce"] = time_in_force
        if new_client_order_id:
            params["newClientOrderId"] = new_client_order_id
        return self.post_signed("/api/v3/order", params, SPOT_STRICT_KEYS)

    def query_order(self, symbol: str, order_id: int | None = None, **kw) -> dict:
        params: dict[str, Any] = {"symbol": symbol, **kw}
        if order_id:
            params["orderId"] = order_id
        return self.get_signed("/api/v3/order", params)

    def cancel_order(self, symbol: str, order_id: int | None = None, **kw) -> dict:
        params: dict[str, Any] = {"symbol": symbol, **kw}
        if order_id:
            params["orderId"] = order_id
        return self.delete_signed("/api/v3/order", params)

    def cancel_all_orders(self, symbol: str) -> dict:
        return self.delete_signed("/api/v3/openOrders", {"symbol": symbol})

    def open_order(self, symbol: str, order_id: int | None = None, **kw) -> dict:
        params: dict[str, Any] = {"symbol": symbol, **kw}
        if order_id:
            params["orderId"] = order_id
        return self.get_signed("/api/v3/openOrder", params)

    def open_orders(self, symbol: str | None = None) -> list:
        params = {"symbol": symbol} if symbol else {}
        return self.get_signed("/api/v3/openOrders", params)

    def all_orders(self, symbol: str, limit: int = 500, **kw) -> list:
        return self.get_signed(
            "/api/v3/allOrders", {"symbol": symbol, "limit": limit, **kw}
        )

    # ═══════════════════════════════════════════════════════════════════
    #  SIGNED — Account
    # ═══════════════════════════════════════════════════════════════════

    def account(self) -> dict:
        # Not yet implemented server-side during Spot v3 rollout (confirmed 2026-04-19).
        warnings.warn(
            "SpotClient.account() is not yet functional on sapi.asterdex.com "
            "(Aster backend limitation, not an SDK issue). "
            "Use FuturesClient.account() for futures account data.",
            stacklevel=2,
        )
        return self.get_signed("/api/v3/account")

    def commission_rate(self, symbol: str) -> dict:
        # Listed in official docs but not yet implemented server-side (confirmed 2026-04-19).
        warnings.warn(
            "SpotClient.commission_rate() is not yet functional on sapi.asterdex.com "
            "(Aster backend limitation, not an SDK issue).",
            stacklevel=2,
        )
        return self.get_signed("/api/v3/commissionRate", {"symbol": symbol})

    def trades_history(self, symbol: str, limit: int = 500, **kw) -> list:
        return self.get_signed(
            "/api/v3/myTrades", {"symbol": symbol, "limit": limit, **kw}
        )

    # ═══════════════════════════════════════════════════════════════════
    #  SIGNED — Transfer & Withdraw
    # ═══════════════════════════════════════════════════════════════════

    def transfer(
        self, asset: str, amount: float, kind_type: str, client_tran_id: str
    ) -> dict:
        return self.post_signed(
            "/api/v3/asset/wallet/transfer",
            {
                "asset": asset,
                "amount": str(amount),
                "kindType": kind_type,
                "clientTranId": client_tran_id,
            },
        )

    def withdraw_fees(self) -> list:
        """Get withdraw fees (public)."""
        return self.get_public("/api/v3/withdrawFee")

    def withdraw(self, asset: str, amount: float, destination: str, **kw) -> dict:
        return self.post_signed(
            "/api/v3/withdraw",
            {"asset": asset, "amount": str(amount), "destination": destination, **kw},
        )
