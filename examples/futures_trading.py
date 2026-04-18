"""
Futures V3 trading example.

Before running:
1. Create an API wallet at https://www.asterdex.com/en/api-wallet
2. Save your agent address and private key
3. Set environment variables:
   export ASTER_USER="0xYourMainWallet"
   export ASTER_SIGNER="0xYourAgentWallet"
   export ASTER_PRIVATE_KEY="0xYourAgentPrivateKey"
"""

import os
from kairos_aster import FuturesClient, AsterAPIError

user = os.environ["ASTER_USER"]
signer = os.environ["ASTER_SIGNER"]
pk = os.environ["ASTER_PRIVATE_KEY"]

client = FuturesClient(user=user, signer=signer, private_key=pk)

# ── Public endpoints (no auth needed) ────────────────────────────────

print("=== Server Time ===")
print(client.server_time())

print("\n=== BTC Price ===")
print(client.ticker_price("BTCUSDT"))

print("\n=== BTC 1h Klines (last 5) ===")
for k in client.klines("BTCUSDT", "1h", limit=5):
    open_, high, low, close = k[1], k[2], k[3], k[4]
    print(f"  O:{open_} H:{high} L:{low} C:{close}")

# ── Signed endpoints ─────────────────────────────────────────────────

print("\n=== Account Balance ===")
for b in client.balance():
    if float(b.get("balance", 0)) > 0:
        print(f"  {b['asset']}: {b['balance']}")

print("\n=== Open Positions ===")
for p in client.positions():
    amt = float(p.get("positionAmt", 0))
    if amt != 0:
        print(f"  {p['symbol']}: {amt} @ entry {p['entryPrice']}")

# ── Place a market order ─────────────────────────────────────────────

try:
    print("\n=== Placing BTC MARKET BUY 0.001 ===")
    order = client.place_order(
        symbol="BTCUSDT",
        side="BUY",
        type="MARKET",
        quantity=0.001,
    )
    print(f"  Order ID: {order['orderId']}, Status: {order['status']}")

except AsterAPIError as e:
    print(f"  Order failed: {e}")
    if e.is_insufficient_balance:
        print("  → Deposit more funds")
    elif e.is_signature_error:
        print("  → Check your signer/private_key match")
