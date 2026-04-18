"""
AsterDEX Futures V3 client.

Usage:
    from kairos_aster import FuturesClient

    client = FuturesClient(
        user="0xYourMainWallet",
        signer="0xYourAgentWallet",
        private_key="0xYourAgentPrivateKey",
    )

    # Market data (public, no auth)
    depth = client.depth("BTCUSDT")
    klines = client.klines("BTCUSDT", "1h")

    # Trading (signed)
    order = client.place_order("BTCUSDT", "BUY", "MARKET", quantity=0.01)
    client.cancel_order("BTCUSDT", order_id=order["orderId"])
"""

from __future__ import annotations

from typing import Any

from .client import BaseClient
from .auth import FUTURES_STRICT_KEYS

_BASE = "https://fapi.asterdex.com"
_TESTNET = "https://fapi.asterdex-testnet.com"


class FuturesClient(BaseClient):
    """Full Futures V3 REST client."""

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
    #  PUBLIC — Market Data (no auth)
    # ═══════════════════════════════════════════════════════════════════

    def ping(self) -> dict:
        return self.get_public("/fapi/v3/ping")

    def server_time(self) -> dict:
        return self.get_public("/fapi/v3/time")

    def exchange_info(self) -> dict:
        return self.get_public("/fapi/v3/exchangeInfo")

    def depth(self, symbol: str, limit: int = 500) -> dict:
        return self.get_public("/fapi/v3/depth", {"symbol": symbol, "limit": limit})

    def trades(self, symbol: str, limit: int = 500) -> list:
        return self.get_public("/fapi/v3/trades", {"symbol": symbol, "limit": limit})

    def klines(
        self, symbol: str, interval: str, limit: int = 500, **kw: Any
    ) -> list:
        params: dict[str, Any] = {
            "symbol": symbol, "interval": interval, "limit": limit, **kw
        }
        return self.get_public("/fapi/v3/klines", params)

    def ticker_24hr(self, symbol: str | None = None) -> Any:
        params = {"symbol": symbol} if symbol else {}
        return self.get_public("/fapi/v3/ticker/24hr", params)

    def ticker_price(self, symbol: str | None = None) -> Any:
        params = {"symbol": symbol} if symbol else {}
        return self.get_public("/fapi/v3/ticker/price", params)

    def book_ticker(self, symbol: str | None = None) -> Any:
        params = {"symbol": symbol} if symbol else {}
        return self.get_public("/fapi/v3/ticker/bookTicker", params)

    def mark_price(self, symbol: str | None = None) -> Any:
        params = {"symbol": symbol} if symbol else {}
        return self.get_public("/fapi/v3/premiumIndex", params)

    def funding_rate(self, symbol: str, limit: int = 100, **kw: Any) -> list:
        return self.get_public(
            "/fapi/v3/fundingRate", {"symbol": symbol, "limit": limit, **kw}
        )

    def agg_trades(self, symbol: str, limit: int = 500, **kw: Any) -> list:
        return self.get_public(
            "/fapi/v3/aggTrades", {"symbol": symbol, "limit": limit, **kw}
        )

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
        price: float | str | None = None,
        time_in_force: str | None = None,
        position_side: str | None = None,
        reduce_only: bool | None = None,
        stop_price: float | str | None = None,
        close_position: bool | None = None,
        activation_price: float | str | None = None,
        callback_rate: float | str | None = None,
        working_type: str | None = None,
        new_client_order_id: str | None = None,
        new_order_resp_type: str | None = None,
        price_protect: bool | None = None,
    ) -> dict:
        """Place a new futures order."""
        params: dict[str, Any] = {"symbol": symbol, "side": side, "type": type}
        if quantity is not None:
            params["quantity"] = str(quantity)
        if price is not None:
            params["price"] = str(price)
        if time_in_force:
            params["timeInForce"] = time_in_force
        if position_side:
            params["positionSide"] = position_side
        if reduce_only is not None:
            params["reduceOnly"] = str(reduce_only).lower()
        if stop_price is not None:
            params["stopPrice"] = str(stop_price)
        if close_position is not None:
            params["closePosition"] = str(close_position).lower()
        if activation_price is not None:
            params["activationPrice"] = str(activation_price)
        if callback_rate is not None:
            params["callbackRate"] = str(callback_rate)
        if working_type:
            params["workingType"] = working_type
        if new_client_order_id:
            params["newClientOrderId"] = new_client_order_id
        if new_order_resp_type:
            params["newOrderRespType"] = new_order_resp_type
        if price_protect is not None:
            params["priceProtect"] = str(price_protect).upper()
        return self.post_signed("/fapi/v3/order", params, FUTURES_STRICT_KEYS)

    def place_batch_orders(self, orders: list[dict]) -> list:
        """Place up to 5 orders in a single request."""
        import json
        return self.post_signed(
            "/fapi/v3/batchOrders",
            {"batchOrders": json.dumps(orders)},
        )

    def query_order(self, symbol: str, order_id: int | None = None, **kw) -> dict:
        params: dict[str, Any] = {"symbol": symbol, **kw}
        if order_id:
            params["orderId"] = order_id
        return self.get_signed("/fapi/v3/order", params)

    def cancel_order(self, symbol: str, order_id: int | None = None, **kw) -> dict:
        params: dict[str, Any] = {"symbol": symbol, **kw}
        if order_id:
            params["orderId"] = order_id
        return self.delete_signed("/fapi/v3/order", params)

    def cancel_all_orders(self, symbol: str) -> dict:
        return self.delete_signed("/fapi/v3/allOpenOrders", {"symbol": symbol})

    def cancel_batch_orders(
        self, symbol: str, order_ids: list[int] | None = None, **kw
    ) -> list:
        import json
        params: dict[str, Any] = {"symbol": symbol, **kw}
        if order_ids:
            params["orderIdList"] = json.dumps(order_ids)
        return self.delete_signed("/fapi/v3/batchOrders", params)

    def auto_cancel(self, symbol: str, countdown_time: int) -> dict:
        """Set auto-cancel countdown (ms). 0 = disable."""
        return self.post_signed(
            "/fapi/v3/countdownCancelAll",
            {"symbol": symbol, "countdownTime": countdown_time},
        )

    def open_order(self, symbol: str, order_id: int | None = None, **kw) -> dict:
        params: dict[str, Any] = {"symbol": symbol, **kw}
        if order_id:
            params["orderId"] = order_id
        return self.get_signed("/fapi/v3/openOrder", params)

    def open_orders(self, symbol: str | None = None) -> list:
        params = {"symbol": symbol} if symbol else {}
        return self.get_signed("/fapi/v3/openOrders", params)

    def all_orders(self, symbol: str, limit: int = 500, **kw) -> list:
        return self.get_signed(
            "/fapi/v3/allOrders", {"symbol": symbol, "limit": limit, **kw}
        )

    # ═══════════════════════════════════════════════════════════════════
    #  SIGNED — Account & Position
    # ═══════════════════════════════════════════════════════════════════

    def balance(self) -> list:
        return self.get_signed("/fapi/v3/balance")

    def account(self) -> dict:
        return self.get_signed("/fapi/v3/account")

    def positions(self, symbol: str | None = None) -> list:
        params = {"symbol": symbol} if symbol else {}
        return self.get_signed("/fapi/v3/positionRisk", params)

    def trades_history(self, symbol: str, limit: int = 500, **kw) -> list:
        return self.get_signed(
            "/fapi/v3/userTrades", {"symbol": symbol, "limit": limit, **kw}
        )

    def income_history(self, **kw) -> list:
        return self.get_signed("/fapi/v3/income", kw)

    def commission_rate(self, symbol: str) -> dict:
        return self.get_signed("/fapi/v3/commissionRate", {"symbol": symbol})

    # ═══════════════════════════════════════════════════════════════════
    #  SIGNED — Leverage & Margin
    # ═══════════════════════════════════════════════════════════════════

    def set_leverage(self, symbol: str, leverage: int) -> dict:
        return self.post_signed(
            "/fapi/v3/leverage", {"symbol": symbol, "leverage": leverage}
        )

    def set_margin_type(self, symbol: str, margin_type: str) -> dict:
        return self.post_signed(
            "/fapi/v3/marginType", {"symbol": symbol, "marginType": margin_type}
        )

    def modify_isolated_margin(
        self, symbol: str, amount: float, type: int, **kw
    ) -> dict:
        """type: 1 = add, 2 = reduce"""
        return self.post_signed(
            "/fapi/v3/positionMargin",
            {"symbol": symbol, "amount": str(amount), "type": type, **kw},
        )

    def leverage_brackets(self, symbol: str | None = None) -> Any:
        params = {"symbol": symbol} if symbol else {}
        return self.get_signed("/fapi/v3/leverageBracket", params)

    # ═══════════════════════════════════════════════════════════════════
    #  SIGNED — Position Mode
    # ═══════════════════════════════════════════════════════════════════

    def set_position_mode(self, hedge: bool) -> dict:
        return self.post_signed(
            "/fapi/v3/positionSide/dual",
            {"dualSidePosition": str(hedge).lower()},
        )

    def get_position_mode(self) -> dict:
        return self.get_signed("/fapi/v3/positionSide/dual")

    def set_multi_assets_mode(self, enabled: bool) -> dict:
        return self.post_signed(
            "/fapi/v3/multiAssetsMargin",
            {"multiAssetsMargin": str(enabled).lower()},
        )

    def get_multi_assets_mode(self) -> dict:
        return self.get_signed("/fapi/v3/multiAssetsMargin")

    # ═══════════════════════════════════════════════════════════════════
    #  SIGNED — Transfers
    # ═══════════════════════════════════════════════════════════════════

    def transfer(
        self, asset: str, amount: float, kind_type: str, client_tran_id: str
    ) -> dict:
        """Transfer between futures and spot."""
        return self.post_signed(
            "/fapi/v3/asset/wallet/transfer",
            {
                "asset": asset,
                "amount": str(amount),
                "kindType": kind_type,
                "clientTranId": client_tran_id,
            },
        )

    # ═══════════════════════════════════════════════════════════════════
    #  SIGNED — Risk & Liquidation
    # ═══════════════════════════════════════════════════════════════════

    def adl_quantile(self, symbol: str | None = None) -> Any:
        params = {"symbol": symbol} if symbol else {}
        return self.get_signed("/fapi/v3/adlQuantile", params)

    def force_orders(self, **kw) -> list:
        return self.get_signed("/fapi/v3/forceOrders", kw)
