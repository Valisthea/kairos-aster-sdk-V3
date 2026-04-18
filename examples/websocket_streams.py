"""
WebSocket streaming examples.

No auth needed for market data streams.
"""

import asyncio
from kairos_aster import AsterWS, StreamRouter


async def example_single_stream():
    """Stream BTC trades in real-time."""
    ws = AsterWS()
    count = 0
    async for trade in ws.stream("btcusdt@trade"):
        price = trade.get("p", "?")
        qty = trade.get("q", "?")
        side = "SELL" if trade.get("m") else "BUY"
        print(f"BTC {side} {qty} @ {price}")
        count += 1
        if count >= 20:
            await ws.close()
            break


async def example_multi_stream():
    """Stream multiple symbols at once."""
    ws = AsterWS()
    count = 0
    async for msg in ws.stream("btcusdt@trade", "ethusdt@trade", "asterusdt@trade"):
        symbol = msg.get("s", "?")
        price = msg.get("p", "?")
        print(f"{symbol}: {price}")
        count += 1
        if count >= 30:
            await ws.close()
            break


async def example_orderbook():
    """Stream orderbook depth updates."""
    ws = AsterWS()
    count = 0
    async for snap in ws.stream("btcusdt@depth5@100ms"):
        bids = snap.get("b", [])[:3]
        asks = snap.get("a", [])[:3]
        print(f"BID: {bids[0] if bids else '?'}  ASK: {asks[0] if asks else '?'}")
        count += 1
        if count >= 10:
            await ws.close()
            break


async def example_kline():
    """Stream 1-minute candles."""
    ws = AsterWS()
    count = 0
    async for msg in ws.stream("btcusdt@kline_1m"):
        k = msg.get("k", {})
        if k:
            print(
                f"BTC 1m | O:{k['o']} H:{k['h']} L:{k['l']} C:{k['c']} "
                f"Vol:{k['v']} Closed:{k['x']}"
            )
        count += 1
        if count >= 10:
            await ws.close()
            break


async def example_router():
    """Use StreamRouter to dispatch different handlers."""
    router = StreamRouter()

    def on_btc(msg):
        print(f"[BTC] {msg.get('p')}")

    def on_eth(msg):
        print(f"[ETH] {msg.get('p')}")

    router.on("btcusdt@trade", on_btc)
    router.on("ethusdt@trade", on_eth)

    # Run for 10 seconds then stop
    async def stop_after():
        await asyncio.sleep(10)
        await router.stop()

    asyncio.create_task(stop_after())
    await router.run()


if __name__ == "__main__":
    print("=== Single Stream (BTC trades) ===")
    asyncio.run(example_single_stream())
