"""
EIP-712 signing for AsterDEX V3 API.

This module abstracts away the entire signing flow so you never have to
think about typed data, nonce generation, or param ordering again.

Zero dependency on web3 — uses eth_utils + eth_abi + eth_account only.
"""

from __future__ import annotations

import time
import threading
from typing import Any

from eth_account import Account
from eth_account.messages import encode_defunct
from eth_abi import encode
from eth_utils import keccak


# EIP-712 domain — hardcoded per Aster spec
DOMAIN = {
    "name": "AsterSignTransaction",
    "version": "1",
    "chainId": 1666,
    "verifyingContract": "0x0000000000000000000000000000000000000000",
}

# Strict key ordering for futures (from official test_spot_standalone_cycle.js)
FUTURES_STRICT_KEYS = [
    "symbol", "side", "type", "quantity", "price", "timeInForce",
    "leverage", "orderId",
]

# Spot key ordering
SPOT_STRICT_KEYS = [
    "symbol", "side", "type", "quantity", "quoteOrderQty", "price",
    "timeInForce", "orderId",
]


class _NonceGenerator:
    """Thread-safe microsecond nonce with collision avoidance."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_us = 0
        self._seq = 0

    def __call__(self) -> str:
        with self._lock:
            now_us = int(time.time() * 1_000_000)
            if now_us <= self._last_us:
                self._seq += 1
                now_us = self._last_us + self._seq
            else:
                self._seq = 0
                self._last_us = now_us
            return str(now_us)


_nonce = _NonceGenerator()


def build_msg(params: dict[str, Any], strict_keys: list[str] | None = None) -> str:
    """
    Build the EIP-712 msg string from request params.

    If strict_keys is provided, only those keys are included and in that
    exact order. Otherwise params are sorted alphabetically.
    """
    if strict_keys:
        parts = []
        for k in strict_keys:
            if k in params:
                parts.append(f"{k}={params[k]}")
        extra_keys = set(params.keys()) - set(strict_keys)
        for k in sorted(extra_keys):
            parts.append(f"{k}={params[k]}")
        return "&".join(parts)
    return "&".join(f"{k}={v}" for k, v in sorted(params.items()))


def sign_request(
    private_key: str,
    params: dict[str, Any],
    strict_keys: list[str] | None = None,
) -> str:
    """
    Sign a dict of request params using EIP-712 and return the 0x-prefixed
    hex signature.
    """
    msg = build_msg(params, strict_keys)

    # Domain separator
    domain_type_hash = keccak(
        text="EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
    )
    domain_hash = keccak(
        encode(
            ["bytes32", "bytes32", "bytes32", "uint256", "address"],
            [
                domain_type_hash,
                keccak(text=DOMAIN["name"]),
                keccak(text=DOMAIN["version"]),
                DOMAIN["chainId"],
                bytes.fromhex(DOMAIN["verifyingContract"][2:]),
            ],
        )
    )

    # Message hash
    message_type_hash = keccak(text="Message(string msg)")
    message_hash = keccak(
        encode(
            ["bytes32", "bytes32"],
            [message_type_hash, keccak(text=msg)],
        )
    )

    # Final EIP-712 hash
    digest = keccak(b"\x19\x01" + domain_hash + message_hash)

    # Sign with private key
    signable = encode_defunct(hexstr=digest.hex())
    signed = Account.sign_message(signable, private_key=private_key)
    return "0x" + signed.signature.hex()


def inject_auth(
    params: dict[str, Any],
    user: str,
    signer: str,
    private_key: str,
    strict_keys: list[str] | None = None,
) -> dict[str, Any]:
    """
    Inject user, signer, nonce, and signature into a params dict.
    Returns a new dict ready to send as request body.
    """
    nonce = _nonce()
    signed_params = dict(params)
    signed_params["nonce"] = nonce
    signed_params["user"] = user
    signed_params["signer"] = signer

    sig = sign_request(private_key, params, strict_keys)
    signed_params["signature"] = sig
    return signed_params


def generate_agent_wallet() -> dict[str, str]:
    """
    Generate a fresh agent/signer keypair.

    Returns {"address": "0x...", "private_key": "0x..."}.
    Use the address as signer and approve it via POST /fapi/v3/approveAgent.
    """
    acct = Account.create()
    pk = acct.key.hex() if isinstance(acct.key, bytes) else acct.key
    if not pk.startswith("0x"):
        pk = "0x" + pk
    return {
        "address": acct.address,
        "private_key": pk,
    }
