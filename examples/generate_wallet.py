"""
Generate an agent/signer wallet for AsterDEX V3 API.

This solves the most common confusion: "where do I get the private key?"

Two approaches:
1. Generate your own keypair (recommended for bots)
2. Use the one from the UI (shown once at creation)
"""

from kairos_aster import generate_agent_wallet

# ── Option 1: Generate a fresh keypair ────────────────────────────────
# This gives you full control over the private key from the start.
# You then approve this address on-chain via the Aster UI or API.

wallet = generate_agent_wallet()
print("=== New Agent Wallet ===")
print(f"Address (signer): {wallet['address']}")
print(f"Private key:      {wallet['private_key']}")
print()
print("Next steps:")
print("1. Go to https://www.asterdex.com/en/api-wallet")
print("2. Click 'Authorize new API wallet'")
print("3. Paste the address above as the agent wallet")
print("4. Approve the transaction in MetaMask")
print("5. Use the address as ASTER_SIGNER and the key as ASTER_PRIVATE_KEY")
print()

# ── Option 2: Programmatic approval via API ───────────────────────────
# If you already have a working client, you can approve the agent directly:
#
#   from kairos_aster import FuturesClient
#
#   client = FuturesClient(user=USER, signer=EXISTING_SIGNER, private_key=EXISTING_PK)
#   result = client.post_signed("/fapi/v3/approveAgent", {
#       "agentAddress": wallet["address"],
#       "agentName": "my-bot-v2",
#       "canPerpTrade": True,
#       "canSpotTrade": True,
#       "canRead": True,
#       "canWithdraw": False,
#   })

# ── Terminology cheat sheet ───────────────────────────────────────────
print("=== Quick Reference ===")
print("user         = your main wallet (the one connected to asterdex.com)")
print("signer       = the agent/API wallet address")
print("private_key  = the agent wallet's private key (NOT your main wallet's)")
print("@aster-desktop = auto-created agent for the web UI, ignore it for API")
