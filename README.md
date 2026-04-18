<div align="center">

# kairos-aster-sdk

**Community Python SDK for AsterDEX V3 API**
Futures · Spot · WebSocket

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Security: OMEGA Audited](https://img.shields.io/badge/security-OMEGA%20audited-orange.svg)](SECURITY_AUDIT.md)

*Built by [Kairos Lab](https://kairos-lab.org) because the V3 API shouldn't require a PhD in EIP-712.*

[Install](#install) · [Quick start](#quick-start) · [Setup guide](#setup-guide-step-by-step) · [API reference](#api-reference) · [Troubleshooting](#troubleshooting)

</div>

---

## What this solves

The AsterDEX V3 API replaced API keys with **EIP-712 signatures**. Every signed request now needs:

- EIP-712 typed data construction with domain separators
- Keccak-256 hashing of struct data
- Strict parameter ordering per endpoint
- Microsecond-precision nonces with replay protection
- `eth_account` signing with hex-prefixed output

**This SDK reduces all of that to zero configuration.** You provide 3 values, call Python methods, done.

```python
from kairos_aster import FuturesClient

client = FuturesClient(
    user="0xYourMainWallet",
    signer="0xYourAgentWallet",
    private_key="0xAgentPrivateKey",
)

# No EIP-712 knowledge needed. Ever.
order = client.place_order("BTCUSDT", "BUY", "MARKET", quantity=0.01)
```

---

## Install

```bash
pip install git+https://github.com/Valisthea/kairos-aster-sdk.git
```

That's it. Dependencies (`eth-account`, `requests`, `websockets`) install automatically.

**Requirements**: Python 3.10 or higher.

**Optional** (for running examples with `.env` files):
```bash
pip install python-dotenv
```

---

## Setup guide (step by step)

### Step 1 — Understand the 3 values you need

The V3 API uses a **delegation model**: your main wallet authorizes an agent wallet to trade on its behalf. You need 3 things:

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   user         Your main wallet address.                │
│                The one connected to asterdex.com,       │
│                the one you deposited funds with.        │
│                You probably already have this.           │
│                                                         │
│   signer       The agent/API wallet address.            │
│                A separate wallet authorized to           │
│                trade on behalf of your main wallet.      │
│                Created in Step 2 below.                  │
│                                                         │
│   private_key  The agent wallet's private key.          │
│                NOT your main wallet's key.               │
│                Shown once at creation, or you            │
│                generate it yourself.                     │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

> **Common confusion**: a wallet called `@aster-desktop` also appears in the API wallet page. Ignore it — that's the internal agent the AsterDEX web UI uses for its own trading interface. It has nothing to do with your API.

### Step 2 — Create your agent wallet

You have two options:

#### Option A: Via the AsterDEX UI (easiest)

1. Go to **[asterdex.com/en/api-wallet](https://www.asterdex.com/en/api-wallet)**
2. Connect your MetaMask (this is your **user** wallet)
3. Click **"Authorize new API wallet"**
4. Sign the transaction in MetaMask
5. **IMMEDIATELY copy both values** that appear:
   - **API wallet address** → this is your `signer`
   - **Private key** → this is your `private_key`

> ⚠️ The private key is shown **only once**. If you miss it, revoke the agent and create a new one.

#### Option B: Generate your own keypair (recommended for bots)

```python
from kairos_aster import generate_agent_wallet

wallet = generate_agent_wallet()
print(f"Address: {wallet['address']}")
print(f"Private key: {wallet['private_key']}")

# Now go to asterdex.com/en/api-wallet and authorize this address
```

This way you always control the private key from the start. After generating, go to the API wallet page and authorize the address you just created.

### Step 3 — Store your credentials

Create a `.env` file in your project directory:

```bash
# .env — NEVER commit this file

# Your main wallet (MetaMask)
ASTER_USER=0x6b5B34BB0B4Fe40bc38B2460376ADDdD36B30D47

# Agent wallet address (from Step 2)
ASTER_SIGNER=0x2610D3935A008036AF0AE12D014C8904b75fC5E9

# Agent wallet private key (from Step 2)
ASTER_PRIVATE_KEY=0xa1b2c3d4e5f6789...
```

Add `.env` to your `.gitignore`:

```bash
echo ".env" >> .gitignore
```

### Step 4 — Verify your setup

Create a test script:

```python
import os
from dotenv import load_dotenv
from kairos_aster import FuturesClient, AsterAPIError

load_dotenv()

client = FuturesClient(
    user=os.environ["ASTER_USER"],
    signer=os.environ["ASTER_SIGNER"],
    private_key=os.environ["ASTER_PRIVATE_KEY"],
)

# Test 1: Public endpoint (no auth needed)
price = client.ticker_price("BTCUSDT")
print(f"✅ BTC price: {price['price']}")

# Test 2: Signed endpoint (tests your credentials)
try:
    balances = client.balance()
    print("✅ Auth works! Your balances:")
    for b in balances:
        if float(b.get("balance", 0)) > 0:
            print(f"   {b['asset']}: {b['balance']}")
except AsterAPIError as e:
    print(f"❌ Auth failed: {e}")
    if e.is_signature_error:
        print("   → Check that private_key belongs to signer, not to user")
```

Run it:

```bash
python test_setup.py
```

**Expected output:**

```
✅ BTC price: 104832.50
✅ Auth works! Your balances:
   USDT: 1247.83
```

If you see `❌ Auth failed` — jump to the [Troubleshooting](#troubleshooting) section.

### Step 5 — Start building

You're ready. See the [Quick start](#quick-start) and [API reference](#api-reference) below.

---

## Quick start

### Place a futures order

```python
order = client.place_order(
    symbol="BTCUSDT",
    side="BUY",
    type="MARKET",
    quantity=0.001,
)
print(f"Filled at {order['avgPrice']}")
```

### Place a limit order with stop loss

```python
# Entry
entry = client.place_order(
    symbol="ETHUSDT",
    side="BUY",
    type="LIMIT",
    quantity=0.1,
    price=3200,
    time_in_force="GTC",
)

# Stop loss
sl = client.place_order(
    symbol="ETHUSDT",
    side="SELL",
    type="STOP_MARKET",
    quantity=0.1,
    stop_price=3100,
    reduce_only=True,
)
```

### Monitor positions

```python
for pos in client.positions():
    amt = float(pos.get("positionAmt", 0))
    if amt != 0:
        pnl = pos.get("unRealizedProfit", "0")
        print(f"{pos['symbol']}: {amt} | PnL: {pnl}")
```

### Stream trades in real-time

```python
import asyncio
from kairos_aster import AsterWS

async def main():
    ws = AsterWS()
    async for trade in ws.stream("btcusdt@trade"):
        side = "SELL" if trade.get("m") else "BUY"
        print(f"BTC {side} {trade['q']} @ {trade['p']}")

asyncio.run(main())
```

### Transfer between futures and spot

```python
# Spot → Futures
client.transfer("USDT", 500.0, "SPOT_FUTURE", "my-transfer-001")

# Futures → Spot
client.transfer("USDT", 200.0, "FUTURE_SPOT", "my-transfer-002")
```

---

## API reference

### FuturesClient

```python
from kairos_aster import FuturesClient

client = FuturesClient(
    user="0x...",              # Main wallet address
    signer="0x...",            # Agent wallet address
    private_key="0x...",       # Agent private key
    testnet=False,             # Use testnet (default: False)
    timeout=10,                # Request timeout in seconds
    max_retries=3,             # Retry on 429/5xx
    show_weight=False,         # Log rate limit weight usage
)
```

#### Market data (public, no auth required)

| Method | Description |
|--------|-------------|
| `ping()` | Test connectivity |
| `server_time()` | Server timestamp |
| `exchange_info()` | Trading rules, symbols, filters |
| `depth(symbol, limit=500)` | Order book |
| `trades(symbol, limit=500)` | Recent trades |
| `agg_trades(symbol, limit=500)` | Compressed/aggregate trades |
| `klines(symbol, interval, limit=500)` | Candlestick data |
| `ticker_24hr(symbol=None)` | 24h rolling stats |
| `ticker_price(symbol=None)` | Latest price |
| `book_ticker(symbol=None)` | Best bid/ask |
| `mark_price(symbol=None)` | Mark price and funding |
| `funding_rate(symbol, limit=100)` | Funding rate history |

**Kline intervals**: `1m`, `3m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `6h`, `8h`, `12h`, `1d`, `3d`, `1w`, `1M`

#### Orders (signed)

| Method | Description |
|--------|-------------|
| `place_order(symbol, side, type, ...)` | New order |
| `place_batch_orders(orders)` | Up to 5 orders at once |
| `query_order(symbol, order_id=None)` | Get order status |
| `cancel_order(symbol, order_id=None)` | Cancel one order |
| `cancel_all_orders(symbol)` | Cancel all open orders on symbol |
| `cancel_batch_orders(symbol, order_ids=[])` | Cancel multiple orders |
| `auto_cancel(symbol, countdown_time)` | Auto-cancel countdown (ms, 0=disable) |
| `open_order(symbol, order_id=None)` | Query single open order |
| `open_orders(symbol=None)` | All open orders |
| `all_orders(symbol, limit=500)` | Order history |

**Order types**: `LIMIT`, `MARKET`, `STOP`, `STOP_MARKET`, `TAKE_PROFIT`, `TAKE_PROFIT_MARKET`, `TRAILING_STOP_MARKET`

**place_order full signature:**

```python
client.place_order(
    symbol="BTCUSDT",           # Required
    side="BUY",                 # Required: BUY or SELL
    type="LIMIT",               # Required: order type
    quantity=0.01,              # Order quantity
    price=60000,                # Limit price
    time_in_force="GTC",        # GTC, IOC, FOK, GTX
    position_side="LONG",       # BOTH (one-way), LONG/SHORT (hedge)
    reduce_only=True,           # Reduce only
    stop_price=59000,           # For STOP/TAKE_PROFIT orders
    close_position=False,       # Close all (with STOP_MARKET)
    activation_price=61000,     # For TRAILING_STOP_MARKET
    callback_rate=1.0,          # Trailing callback % (0.1-5)
    working_type="CONTRACT_PRICE",  # or MARK_PRICE
    new_client_order_id="my-order", # Custom ID (max 36 chars)
    new_order_resp_type="ACK",  # ACK or RESULT
    price_protect=True,         # Trigger protection
)
```

#### Account & positions (signed)

| Method | Description |
|--------|-------------|
| `balance()` | Account balances |
| `account()` | Full account info |
| `positions(symbol=None)` | Position risk data |
| `trades_history(symbol, limit=500)` | Trade history |
| `income_history()` | Income/PnL history |
| `commission_rate(symbol)` | Current fee rate |

#### Leverage & margin (signed)

| Method | Description |
|--------|-------------|
| `set_leverage(symbol, leverage)` | Change leverage |
| `set_margin_type(symbol, "ISOLATED"/"CROSSED")` | Switch margin mode |
| `modify_isolated_margin(symbol, amount, type)` | Add (1) or reduce (2) margin |
| `leverage_brackets(symbol=None)` | Notional brackets |

#### Position mode (signed)

| Method | Description |
|--------|-------------|
| `set_position_mode(hedge=True/False)` | Hedge or one-way mode |
| `get_position_mode()` | Current mode |
| `set_multi_assets_mode(enabled=True/False)` | Multi-assets mode |
| `get_multi_assets_mode()` | Current multi-assets mode |

#### Transfers (signed)

| Method | Description |
|--------|-------------|
| `transfer(asset, amount, kind_type, client_tran_id)` | Futures ↔ Spot transfer |

`kind_type`: `"SPOT_FUTURE"` or `"FUTURE_SPOT"`

#### Risk (signed)

| Method | Description |
|--------|-------------|
| `adl_quantile(symbol=None)` | ADL quantile estimation |
| `force_orders()` | Liquidation history |

---

### SpotClient

```python
from kairos_aster import SpotClient

client = SpotClient(
    user="0x...", signer="0x...", private_key="0x...",
    testnet=False,
)
```

#### Market data (public)

| Method | Description |
|--------|-------------|
| `ping()` | Test connectivity |
| `server_time()` | Server timestamp |
| `exchange_info()` | Trading rules |
| `depth(symbol, limit=100)` | Order book |
| `trades(symbol, limit=500)` | Recent trades |
| `klines(symbol, interval, limit=500)` | Candlesticks |
| `ticker_24hr(symbol=None)` | 24h stats |
| `ticker_price(symbol=None)` | Latest price |
| `book_ticker(symbol=None)` | Best bid/ask |

#### Orders (signed)

| Method | Description |
|--------|-------------|
| `place_order(symbol, side, type, ...)` | New order |
| `query_order(symbol, order_id=None)` | Order status |
| `cancel_order(symbol, order_id=None)` | Cancel order |
| `cancel_all_orders(symbol)` | Cancel all on symbol |
| `open_orders(symbol=None)` | Open orders |
| `all_orders(symbol, limit=500)` | Order history |

#### Account (signed)

| Method | Description |
|--------|-------------|
| `account()` | Balances and info |
| `trades_history(symbol, limit=500)` | Trade history |
| `withdraw_fees()` | Withdrawal fee schedule (public) |
| `withdraw(asset, amount, destination)` | Withdraw funds |

---

### AsterWS (WebSocket)

```python
from kairos_aster import AsterWS

ws = AsterWS(
    market="futures",      # "futures" or "spot"
    testnet=False,
    reconnect=True,        # Auto-reconnect on disconnect
    max_reconnects=10,
)
```

#### Market streams

```python
import asyncio

async def main():
    ws = AsterWS()

    # Single stream
    async for msg in ws.stream("btcusdt@trade"):
        print(msg)

    # Multiple streams
    async for msg in ws.stream("btcusdt@trade", "ethusdt@kline_1m"):
        print(msg)

asyncio.run(main())
```

**Available streams:**

| Stream | Description | Example |
|--------|-------------|---------|
| `@trade` | Real-time trades | `btcusdt@trade` |
| `@aggTrade` | Aggregate trades | `btcusdt@aggTrade` |
| `@kline_<interval>` | Candlesticks | `btcusdt@kline_1m` |
| `@depth<levels>` | Partial orderbook | `btcusdt@depth5` |
| `@depth<levels>@<speed>` | Orderbook with speed | `btcusdt@depth5@100ms` |
| `@markPrice` | Mark price (3s) | `btcusdt@markPrice` |
| `@markPrice@1s` | Mark price (1s) | `btcusdt@markPrice@1s` |
| `@ticker` | 24h ticker | `btcusdt@ticker` |
| `!miniTicker@arr` | All symbols mini ticker | `!miniTicker@arr` |

> All stream names must be **lowercase**.

#### User data stream

```python
# Step 1: Get a listen key from the REST client
key_resp = client.post_signed("/fapi/v3/listenKey")
listen_key = key_resp["listenKey"]

# Step 2: Stream user events
ws = AsterWS()
async for event in ws.user_stream(listen_key):
    event_type = event.get("e")

    if event_type == "ORDER_TRADE_UPDATE":
        o = event["o"]
        print(f"Order {o['S']} {o['s']}: {o['X']} @ {o['ap']}")

    elif event_type == "ACCOUNT_UPDATE":
        for pos in event["a"]["P"]:
            print(f"Position {pos['s']}: {pos['pa']}")
```

> Listen keys expire after 60 minutes. Send a PUT keepalive to renew.

#### Dynamic subscribe/unsubscribe

```python
async for msg in ws.stream("btcusdt@trade"):
    # Add more streams on the fly
    await ws.subscribe("ethusdt@trade")

    # Remove streams
    await ws.unsubscribe("btcusdt@trade")
```

#### StreamRouter (dispatch pattern)

```python
from kairos_aster import StreamRouter

router = StreamRouter()

def handle_btc(msg):
    print(f"[BTC] {msg['p']}")

def handle_eth(msg):
    print(f"[ETH] {msg['p']}")

router.on("btcusdt@trade", handle_btc)
router.on("ethusdt@trade", handle_eth)

await router.run()   # Dispatches automatically
await router.stop()  # Clean shutdown
```

---

### Error handling

```python
from kairos_aster import AsterAPIError, AsterRequestError

try:
    client.place_order("BTCUSDT", "BUY", "MARKET", quantity=0.001)

except AsterAPIError as e:
    # API-level error (invalid order, insufficient balance, etc.)
    print(e.code)          # -2018
    print(e.message)       # "Balance is insufficient."
    print(e.explanation)   # "BALANCE_NOT_SUFFICIENT"

    # Convenience checks
    e.is_signature_error       # True for -1000, -1022
    e.is_rate_limit            # True for -1003, -1015
    e.is_insufficient_balance  # True for -2018, -2019, -4050, -4051
    e.is_order_rejected        # True for -2010, -2020, -2021, -2022

except AsterRequestError as e:
    # HTTP-level error (timeout, connection, 5xx, IP ban)
    print(e.status_code)   # 418
    print(e.text)          # "IP auto-banned"
```

All [official error codes](https://asterdex.github.io/aster-api-website/futures-v3/error-codes/) are mapped in `kairos_aster.errors.ERRORS`.

---

### Enums

Optional type-safe constants:

```python
from kairos_aster import Side, OrderType, TimeInForce, PositionSide

client.place_order(
    "BTCUSDT",
    Side.BUY,
    OrderType.LIMIT,
    quantity=0.01,
    price=60000,
    time_in_force=TimeInForce.GTC,
    position_side=PositionSide.LONG,
)
```

Available: `Side`, `OrderType`, `TimeInForce`, `PositionSide`, `MarginType`, `WorkingType`, `TransferType`, `KlineInterval`

---

## Troubleshooting

### "Signature check failed" (-1000 or -1022)

This is the most common error. Check these in order:

| # | Check | Fix |
|---|-------|-----|
| 1 | **Wrong private key** | You must use the **agent wallet's** private key, not your main MetaMask key |
| 2 | **Signer mismatch** | The `signer` address must correspond to the private key. The address derived from the key must equal `signer` |
| 3 | **Agent not approved** | Go to [asterdex.com/en/api-wallet](https://www.asterdex.com/en/api-wallet) and verify the agent is listed and active |
| 4 | **Agent expired** | Agent wallets have an expiry. Create a new one if expired |
| 5 | **Clock drift** | Your system clock must be within 10 seconds of Aster's server time. Run `client.server_time()` and compare |

**Quick diagnostic:**

```python
from eth_account import Account

# Verify your key matches your signer
key = "0xYourAgentPrivateKey"
derived = Account.from_key(key).address
print(f"Derived:  {derived}")
print(f"Signer:   {os.environ['ASTER_SIGNER']}")
print(f"Match:    {derived.lower() == os.environ['ASTER_SIGNER'].lower()}")
```

### "Balance is insufficient" (-2018)

Your futures account has no funds. Deposit on [asterdex.com](https://www.asterdex.com) or transfer from spot:

```python
client.transfer("USDT", 100.0, "SPOT_FUTURE", "funding-001")
```

### Rate limiting (429)

The SDK handles 429 automatically with exponential backoff. If you're hitting limits frequently:

```python
client = FuturesClient(..., show_weight=True)  # Log weight usage
```

Use WebSocket streams instead of polling REST endpoints for real-time data.

### WebSocket disconnects

WebSocket connections auto-reconnect up to 10 times with exponential backoff. If connections keep dropping:

- Check your firewall/proxy settings
- Aster limits to 200 streams per connection and 10 messages/second
- Connections auto-close after 24 hours

### IP banned (418)

You've been sending too many requests after receiving 429 errors. The ban auto-expires (2 minutes to 3 days depending on severity). Use WebSocket for live data instead of polling.

---

## Under the hood

### How EIP-712 signing works (for the curious)

When you call `client.place_order(...)`, the SDK:

```
1. Builds the msg string from your params
   → "symbol=BTCUSDT&side=BUY&type=MARKET&quantity=0.01"

2. Constructs EIP-712 typed data
   → domain: {name: "AsterSignTransaction", version: "1", chainId: 1666}
   → message: {msg: "<the string above>"}

3. Hashes with keccak256
   → domainSeparator = keccak256(encode(domainType))
   → messageHash = keccak256(encode(messageType))
   → digest = keccak256("\x19\x01" + domainSeparator + messageHash)

4. Signs with your agent private key
   → signature = sign(digest, private_key)

5. Sends the request
   → POST /fapi/v3/order
   → body: symbol, side, type, quantity, user, signer, nonce, signature
```

You never see steps 2-4. The SDK does them on every signed request.

### Rate limits

The SDK tracks rate limit weight from response headers (`X-MBX-USED-WEIGHT-1m`). Enable logging:

```python
import logging
logging.basicConfig(level=logging.INFO)

client = FuturesClient(..., show_weight=True)
```

### Testnet

Both clients support testnet mode:

```python
client = FuturesClient(..., testnet=True)
# Uses https://fapi.asterdex-testnet.com

spot = SpotClient(..., testnet=True)
# Uses https://sapi.asterdex-testnet.com
```

---

## Project structure

```
kairos-aster-sdk/
├── kairos_aster/
│   ├── __init__.py      # Public exports
│   ├── auth.py          # EIP-712 signing engine
│   ├── client.py        # HTTP client, retry, rate limiting
│   ├── futures.py       # Futures V3 REST (40+ endpoints)
│   ├── spot.py          # Spot V3 REST
│   ├── ws.py            # Async WebSocket with reconnect
│   ├── errors.py        # Complete error code map
│   └── enums.py         # Type-safe constants
├── examples/
│   ├── futures_trading.py
│   ├── spot_trading.py
│   ├── websocket_streams.py
│   └── generate_wallet.py
├── tests/
│   └── test_auth.py     # 21 unit tests
├── SECURITY_AUDIT.md    # OMEGA audit report
├── .env.example         # Credential template
└── README.md
```

---

## Security

This SDK has been audited by [OMEGA](https://kairos-lab.org) (Kairos Lab Security Research). Full report: [`SECURITY_AUDIT.md`](SECURITY_AUDIT.md).

Key security properties:

- **No hardcoded secrets** — all credentials from constructor params or env vars
- **Private key masked** — never exposed in `repr()`, logs, or serialization
- **No web3 dependency** — minimal attack surface (`eth-account` + `requests` + `websockets` only)
- **Stream validation** — WebSocket stream names are sanitized against path injection
- **TLS enforced** — all connections use HTTPS/WSS

**Your responsibilities:**
- Never commit `.env` files or hardcode private keys
- Use IP whitelisting on your agent wallet when possible
- Disable withdrawal permissions on agent wallets used for trading bots
- Rotate agent wallets periodically

---

## Links

| Resource | URL |
|----------|-----|
| AsterDEX V3 API docs | [asterdex.github.io/aster-api-website](https://asterdex.github.io/aster-api-website/futures-v3/general-info/) |
| V3 signing specification | [github.com/asterdex/api-docs](https://github.com/asterdex/api-docs/blob/master/aster-finance-futures-api-v3.md) |
| API wallet management | [asterdex.com/en/api-wallet](https://www.asterdex.com/en/api-wallet) |
| Official Python connector | [github.com/asterdex/aster-connector-python](https://github.com/asterdex/aster-connector-python) |
| AsterDEX MCP server | [github.com/asterdex/aster-mcp](https://github.com/asterdex/aster-mcp) |
| Kairos Lab | [kairos-lab.org](https://kairos-lab.org) |
| AsterScan (block explorer) | [aster-scan.com](https://aster-scan.com) |

---

## Contributing

Issues and PRs welcome at [github.com/Valisthea/kairos-aster-sdk](https://github.com/Valisthea/kairos-aster-sdk).

```bash
git clone https://github.com/Valisthea/kairos-aster-sdk.git
cd kairos-aster-sdk
pip install -e ".[dev]"
pytest tests/ -v
```

---

## License

MIT — [Kairos Lab](https://kairos-lab.org)
