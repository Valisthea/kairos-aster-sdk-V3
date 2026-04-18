"""
Spot V3 trading example.

Setup: same env vars as futures_trading.py
"""

import os
from kairos_aster import SpotClient, AsterAPIError

client = SpotClient(
    user=os.environ["ASTER_USER"],
    signer=os.environ["ASTER_SIGNER"],
    private_key=os.environ["ASTER_PRIVATE_KEY"],
)

# Public
print("=== ASTER/USDT Price ===")
print(client.ticker_price("ASTERUSDT"))

# Account
print("\n=== Spot Balances ===")
info = client.account()
for b in info.get("balances", []):
    free = float(b.get("free", 0))
    if free > 0:
        print(f"  {b['asset']}: {free}")

# Place a limit buy
try:
    order = client.place_order(
        symbol="ASTERUSDT",
        side="BUY",
        type="LIMIT",
        quantity=10,
        price="0.50",
        time_in_force="GTC",
    )
    print(f"\nOrder placed: {order['orderId']}")
except AsterAPIError as e:
    print(f"\nOrder failed: {e}")
