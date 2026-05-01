"""
EIP-712 signing for AsterDEX V3 API.

Implementation follows the canonical Aster v3 spec example exactly:
https://github.com/asterdex/api-docs/blob/master/aster-finance-futures-api-v3.md

Specifically:
  - signature is computed via `encode_typed_data(full_message=typed_data)`
    (real EIP-712, NOT `encode_defunct` over the digest)
  - the signed `msg` is the URL-encoded form of the FULL params dict
    *after* `nonce`, `user`, `signer` have been injected
"""

from __future__ import annotations

import time
import threading
import urllib.parse
from typing import Any

from eth_account import Account
from eth_account.messages import encode_typed_data


# EIP-712 domain — matches the Aster v3 spec exactly
DOMAIN = {
    "name": "AsterSignTransaction",
    "version": "1",
    "chainId": 1666,
    "verifyingContract": "0x0000000000000000000000000000000000000000",
}

# EIP-712 type definitions used by Aster's signing scheme
_TYPES = {
    "EIP712Domain": [
        {"name": "name", "type": "string"},
        {"name": "version", "type": "string"},
        {"name": "chainId", "type": "uint256"},
        {"name": "verifyingContract", "type": "address"},
    ],
    "Message": [{"name": "msg", "type": "string"}],
}

# Strict ordering used when laying out user-supplied params before they get
# url-encoded together with nonce/user/signer. Keeps the signed string
# deterministic regardless of which order the caller passed kwargs in.
FUTURES_STRICT_KEYS = [
    "symbol", "side", "type", "quantity", "price", "timeInForce",
    "leverage", "orderId",
]
SPOT_STRICT_KEYS = [
    "symbol", "side", "type", "quantity", "quoteOrderQty", "price",
    "timeInForce", "orderId",
]


class _NonceGenerator:
    """Thread-safe microsecond nonce with collision avoidance and drift cap.

    Aster rejects nonces that exceed server time by more than 5s
    (error -1021). Cap drift to 4s and fall back to a short sleep if
    exhausted, so a burst can never push us out-of-window.
    """

    _MAX_DRIFT_US = 4_000_000

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_us = 0
        self._seq = 0

    def __call__(self) -> str:
        with self._lock:
            now_us = int(time.time() * 1_000_000)
            if now_us <= self._last_us:
                self._seq += 1
                candidate = self._last_us + self._seq
                if candidate - now_us > self._MAX_DRIFT_US:
                    # Burst would push us out of Aster's 5s window.
                    self._lock.release()
                    try:
                        time.sleep(0.001)
                    finally:
                        self._lock.acquire()
                    now_us = int(time.time() * 1_000_000)
                    self._last_us = now_us
                    self._seq = 0
                else:
                    now_us = candidate
            else:
                self._seq = 0
                self._last_us = now_us
            return str(now_us)


_nonce = _NonceGenerator()


def _ordered_params(
    params: dict[str, Any], strict_keys: list[str] | None
) -> dict[str, Any]:
    """Re-order a params dict so strict keys come first in the given order,
    then any remaining keys in alphabetical order. Returns a new dict that
    preserves insertion order (Python 3.7+ guarantee)."""
    if not strict_keys:
        return {k: params[k] for k in sorted(params.keys())}
    out: dict[str, Any] = {}
    for k in strict_keys:
        if k in params:
            out[k] = params[k]
    for k in sorted(set(params.keys()) - set(strict_keys)):
        out[k] = params[k]
    return out


def build_msg(params: dict[str, Any], strict_keys: list[str] | None = None) -> str:
    """Build the `msg` string from a params dict.

    Uses `urllib.parse.urlencode` to match Aster's reference implementation
    byte-for-byte (the server reconstructs the message the same way).
    """
    ordered = _ordered_params(params, strict_keys)
    return urllib.parse.urlencode(ordered)


def sign_message_string(private_key: str, msg: str) -> str:
    """Sign an already-built `msg` string using EIP-712 typed data.

    Returns a 0x-prefixed hex signature (132 chars).
    """
    typed_data = {
        "types": _TYPES,
        "primaryType": "Message",
        "domain": DOMAIN,
        "message": {"msg": msg},
    }
    signable = encode_typed_data(full_message=typed_data)
    signed = Account.sign_message(signable, private_key=private_key)
    return "0x" + signed.signature.hex()


def sign_request(
    private_key: str,
    params: dict[str, Any],
    strict_keys: list[str] | None = None,
) -> str:
    """Sign a params dict end-to-end. The caller is responsible for having
    already injected `nonce`, `user`, `signer` into `params` if they want
    those covered by the signature — see `inject_auth` for the full flow.
    """
    msg = build_msg(params, strict_keys)
    return sign_message_string(private_key, msg)


def inject_auth(
    params: dict[str, Any],
    user: str,
    signer: str,
    private_key: str,
    strict_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Inject `nonce`, `user`, `signer`, and `signature` into a params dict.

    The signature covers the FULL dict including the auth fields — Aster's
    server reconstructs the signed message from the request body, so any
    field present in the body must also have been present at sign time.
    """
    nonce = _nonce()
    ordered = _ordered_params(params, strict_keys)
    ordered["nonce"] = nonce
    ordered["user"] = user
    ordered["signer"] = signer

    msg = urllib.parse.urlencode(ordered)
    sig = sign_message_string(private_key, msg)

    ordered["signature"] = sig
    return ordered


def generate_agent_wallet() -> dict[str, str]:
    """Generate a fresh agent/signer keypair using `eth_account.Account.create`,
    which derives entropy from `os.urandom` (cryptographically secure).

    Returns {"address": "0x...", "private_key": "0x..."}.
    Use the address as `signer` and approve it via the Aster API-wallet UI.
    """
    acct = Account.create()
    pk = acct.key.hex() if isinstance(acct.key, bytes) else acct.key
    if not pk.startswith("0x"):
        pk = "0x" + pk
    return {
        "address": acct.address,
        "private_key": pk,
    }
