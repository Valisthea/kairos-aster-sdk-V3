"""
AsterDEX WebSocket client.

Usage:
    import asyncio
    from kairos_aster import AsterWS

    async def main():
        ws = AsterWS()

        # Market streams
        async for msg in ws.stream("btcusdt@trade"):
            print(msg)

        # Multiple streams
        async for msg in ws.stream("btcusdt@depth5", "ethusdt@kline_1m"):
            print(msg)

        # User data stream (requires listen key)
        async for msg in ws.user_stream(listen_key):
            print(msg)

    asyncio.run(main())
"""

from __future__ import annotations

import json
import re
import asyncio
import logging
from typing import Any, AsyncIterator, Callable

import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger("kairos_aster.ws")

_FUTURES_WS = "wss://fstream.asterdex.com"
_SPOT_WS = "wss://sstream.asterdex.com"
_FUTURES_WS_TESTNET = "wss://fstream.asterdex-testnet.com"
_SPOT_WS_TESTNET = "wss://sstream.asterdex-testnet.com"

_STREAM_PATTERN = re.compile(r"^[a-zA-Z0-9@_!.]+$")
_LISTEN_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{8,256}$")


def _validate_stream(name: str) -> str:
    """Validate stream name to prevent path injection."""
    if not _STREAM_PATTERN.match(name):
        raise ValueError(f"Invalid stream name: {name!r}")
    return name


def _validate_listen_key(key: str) -> str:
    """Validate listen key shape before interpolating into the WebSocket URL.

    The key originates from Aster's REST API but a poisoned proxy or
    a misuse path could feed something containing `/` or `..` and pivot
    the URL — sanitize defensively.
    """
    if not isinstance(key, str) or not _LISTEN_KEY_PATTERN.match(key):
        raise ValueError(f"Invalid listen key: {key!r}")
    return key


class AsterWS:
    """
    Async WebSocket client for AsterDEX streams.

    Handles reconnection, ping/pong, and multi-stream subscriptions.
    """

    def __init__(
        self,
        *,
        market: str = "futures",
        testnet: bool = False,
        reconnect: bool = True,
        max_reconnects: int = 10,
    ) -> None:
        if market == "futures":
            self.base_url = _FUTURES_WS_TESTNET if testnet else _FUTURES_WS
        else:
            self.base_url = _SPOT_WS_TESTNET if testnet else _SPOT_WS
        self.reconnect = reconnect
        self.max_reconnects = max_reconnects
        self._ws = None
        self._running = False

    async def stream(self, *streams: str) -> AsyncIterator[dict]:
        """
        Subscribe to one or more market data streams.

        Stream names must be lowercase. Examples:
            "btcusdt@trade"
            "btcusdt@depth5"
            "btcusdt@kline_1m"
            "btcusdt@aggTrade"
            "btcusdt@markPrice@1s"
            "!miniTicker@arr"

        For a single stream:  ws://base/ws/streamName
        For combined streams: ws://base/stream?streams=s1/s2/s3
        """
        if len(streams) == 1:
            url = f"{self.base_url}/ws/{_validate_stream(streams[0])}"
        else:
            combined = "/".join(_validate_stream(s) for s in streams)
            url = f"{self.base_url}/stream?streams={combined}"

        async for msg in self._connect_and_iterate(url):
            yield msg

    async def user_stream(self, listen_key: str) -> AsyncIterator[dict]:
        """
        Subscribe to user data stream (account updates, order fills, etc).

        Get a listen_key via FuturesClient or SpotClient:
            key = client.post_signed("/fapi/v3/listenKey")["listenKey"]

        The key expires after 60 min — send keepalive PUTs.
        """
        url = f"{self.base_url}/ws/{_validate_listen_key(listen_key)}"
        async for msg in self._connect_and_iterate(url):
            yield msg

    async def _connect_and_iterate(self, url: str) -> AsyncIterator[dict]:
        """Connect with auto-reconnect and yield parsed messages."""
        attempts = 0

        while True:
            try:
                async with websockets.connect(
                    url,
                    ping_interval=60,
                    ping_timeout=300,
                    close_timeout=5,
                    max_size=10 * 1024 * 1024,
                ) as ws:
                    self._ws = ws
                    self._running = True
                    attempts = 0
                    logger.info("Connected to %s", url)

                    async for raw in ws:
                        try:
                            data = json.loads(raw)
                            # Combined stream wraps data in {"stream": ..., "data": ...}
                            if "stream" in data and "data" in data:
                                yield data["data"]
                            else:
                                yield data
                        except json.JSONDecodeError:
                            logger.warning("Non-JSON message: %s", raw[:200])

            except ConnectionClosed as e:
                logger.warning("Connection closed: %s", e)
            except Exception as e:
                logger.error("WebSocket error: %s", e)

            self._running = False
            self._ws = None

            if not self.reconnect:
                break

            attempts += 1
            if attempts > self.max_reconnects:
                logger.error("Max reconnects (%d) reached", self.max_reconnects)
                break

            wait = min(2**attempts, 30)
            logger.info("Reconnecting in %ds (attempt %d)…", wait, attempts)
            await asyncio.sleep(wait)

    async def close(self) -> None:
        """Gracefully close the WebSocket."""
        self._running = False
        if self._ws:
            await self._ws.close()
            self._ws = None

    async def subscribe(self, *streams: str) -> None:
        """Dynamically subscribe to additional streams on an open connection."""
        if not self._ws:
            raise RuntimeError("Not connected")
        payload = {
            "method": "SUBSCRIBE",
            "params": list(streams),
            "id": int(asyncio.get_running_loop().time() * 1000),
        }
        await self._ws.send(json.dumps(payload))

    async def unsubscribe(self, *streams: str) -> None:
        """Unsubscribe from streams on an open connection."""
        if not self._ws:
            raise RuntimeError("Not connected")
        payload = {
            "method": "UNSUBSCRIBE",
            "params": list(streams),
            "id": int(asyncio.get_running_loop().time() * 1000),
        }
        await self._ws.send(json.dumps(payload))


class StreamRouter:
    """
    Route messages from multiple streams to different callbacks.

    Usage:
        router = StreamRouter()
        router.on("btcusdt@trade", handle_btc_trade)
        router.on("ethusdt@trade", handle_eth_trade)
        await router.run()
    """

    def __init__(self, *, market: str = "futures", testnet: bool = False) -> None:
        self._ws = AsterWS(market=market, testnet=testnet)
        self._handlers: dict[str, Callable] = {}

    def on(self, stream: str, handler: Callable[[dict], Any]) -> None:
        """Register a callback for a stream."""
        self._handlers[stream] = handler

    async def run(self) -> None:
        """Start streaming and dispatch to handlers."""
        streams = list(self._handlers.keys())
        if not streams:
            raise ValueError("No streams registered")

        async for msg in self._ws.stream(*streams):
            # Try to match by event type or stream name
            stream_name = msg.get("s", "").lower()
            event = msg.get("e", "")

            for pattern, handler in self._handlers.items():
                symbol_part = pattern.split("@")[0] if "@" in pattern else ""
                if symbol_part and stream_name and symbol_part in stream_name:
                    result = handler(msg)
                    if asyncio.iscoroutine(result):
                        await result
                    break

    async def stop(self) -> None:
        await self._ws.close()
