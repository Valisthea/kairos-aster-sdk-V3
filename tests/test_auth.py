"""
Tests for the auth module — the core of the SDK.

Run: pytest tests/ -v

The most important test in this file is TestSignatureRecovery — it
proves the signature actually verifies against the claimed signer
under canonical EIP-712 verification. Without this, signature
correctness is unverifiable from the test suite alone (and a prior
bug shipped because the suite only checked length/determinism).
"""

import urllib.parse

import pytest
from eth_account import Account
from eth_account.messages import encode_typed_data

from kairos_aster.auth import (
    DOMAIN,
    FUTURES_STRICT_KEYS,
    SPOT_STRICT_KEYS,
    build_msg,
    generate_agent_wallet,
    inject_auth,
    sign_message_string,
    sign_request,
)


# Deterministic test key (DO NOT use in production)
_TEST_PK = "0x4c0883a69102937d6231471b5dbb6204fe512961708279f9d92e8e632e85e3a2"
_TEST_SIGNER = Account.from_key(_TEST_PK).address
_USER = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

_TYPED_DATA_TEMPLATE = {
    "types": {
        "EIP712Domain": [
            {"name": "name", "type": "string"},
            {"name": "version", "type": "string"},
            {"name": "chainId", "type": "uint256"},
            {"name": "verifyingContract", "type": "address"},
        ],
        "Message": [{"name": "msg", "type": "string"}],
    },
    "primaryType": "Message",
    "domain": DOMAIN,
}


def _server_recover(msg: str, sig: str) -> str:
    """Simulate the Aster server: rebuild EIP-712 typed data from the msg
    string and recover the signer address from the signature."""
    typed = {**_TYPED_DATA_TEMPLATE, "message": {"msg": msg}}
    signable = encode_typed_data(full_message=typed)
    return Account.recover_message(signable, signature=sig)


class TestBuildMsg:
    """Verify msg string construction matches Aster's expected format."""

    def test_alphabetical_sort_default(self):
        params = {"symbol": "BTCUSDT", "side": "BUY", "quantity": "0.01"}
        msg = build_msg(params)
        assert msg == "quantity=0.01&side=BUY&symbol=BTCUSDT"

    def test_futures_strict_order(self):
        params = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "MARKET",
            "quantity": "0.01",
        }
        msg = build_msg(params, FUTURES_STRICT_KEYS)
        assert msg == "symbol=BTCUSDT&side=BUY&type=MARKET&quantity=0.01"

    def test_strict_order_skips_missing(self):
        params = {"symbol": "ETHUSDT", "side": "SELL", "type": "LIMIT"}
        msg = build_msg(params, FUTURES_STRICT_KEYS)
        assert msg == "symbol=ETHUSDT&side=SELL&type=LIMIT"

    def test_strict_order_appends_extras(self):
        params = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "LIMIT",
            "price": "50000",
            "reduceOnly": "false",
        }
        msg = build_msg(params, FUTURES_STRICT_KEYS)
        assert msg.startswith("symbol=BTCUSDT&side=BUY&type=LIMIT")
        assert "price=50000" in msg
        assert "reduceOnly=false" in msg

    def test_spot_strict_order(self):
        params = {
            "symbol": "ASTERUSDT",
            "side": "BUY",
            "type": "MARKET",
            "quantity": "100",
        }
        msg = build_msg(params, SPOT_STRICT_KEYS)
        assert msg == "symbol=ASTERUSDT&side=BUY&type=MARKET&quantity=100"

    def test_empty_params(self):
        assert build_msg({}) == ""

    def test_url_encodes_special_chars(self):
        # Spec uses urllib.parse.urlencode → server reconstructs identically
        msg = build_msg({"clientTranId": "tx-2026 05 01"})
        assert msg == "clientTranId=tx-2026+05+01"


class TestDomain:
    """Verify EIP-712 domain constants."""

    def test_chain_id(self):
        assert DOMAIN["chainId"] == 1666

    def test_name(self):
        assert DOMAIN["name"] == "AsterSignTransaction"

    def test_version(self):
        assert DOMAIN["version"] == "1"

    def test_verifying_contract(self):
        assert DOMAIN["verifyingContract"] == "0x" + "0" * 40


class TestSignRequest:
    """Verify signature output format and stability."""

    def test_returns_0x_prefixed(self):
        sig = sign_request(_TEST_PK, {"symbol": "BTCUSDT"})
        assert sig.startswith("0x")

    def test_signature_length(self):
        sig = sign_request(_TEST_PK, {"symbol": "BTCUSDT"})
        # 0x + 130 hex chars (65 bytes r+s+v)
        assert len(sig) == 132

    def test_deterministic(self):
        params = {"symbol": "BTCUSDT", "side": "BUY"}
        sig1 = sign_request(_TEST_PK, params)
        sig2 = sign_request(_TEST_PK, params)
        assert sig1 == sig2

    def test_different_params_different_sig(self):
        sig1 = sign_request(_TEST_PK, {"symbol": "BTCUSDT"})
        sig2 = sign_request(_TEST_PK, {"symbol": "ETHUSDT"})
        assert sig1 != sig2


class TestSignatureRecovery:
    """The crown-jewel tests — without these, signature correctness is
    unverifiable from the test suite alone. A prior bug
    (`encode_defunct` over the digest instead of `encode_typed_data`)
    shipped because these tests didn't exist."""

    def test_sign_message_string_recovers_to_signer(self):
        msg = "symbol=BTCUSDT&side=BUY&type=MARKET&quantity=0.001"
        sig = sign_message_string(_TEST_PK, msg)
        assert _server_recover(msg, sig).lower() == _TEST_SIGNER.lower()

    def test_inject_auth_signature_covers_full_body(self):
        """Sign-then-strip: rebuild the same urlencoded msg the server sees
        from the returned dict (minus signature) and prove the signature
        recovers to _TEST_SIGNER. This catches:
          - wrong signing primitive (encode_defunct vs encode_typed_data)
          - signing only user params (missing nonce/user/signer)
        """
        signed = inject_auth(
            {"symbol": "BTCUSDT", "side": "BUY", "type": "MARKET", "quantity": "0.001"},
            user=_USER,
            signer=_TEST_SIGNER,
            private_key=_TEST_PK,
            strict_keys=FUTURES_STRICT_KEYS,
        )
        sig = signed.pop("signature")
        rebuilt_msg = urllib.parse.urlencode(signed)
        recovered = _server_recover(rebuilt_msg, sig)
        assert recovered.lower() == _TEST_SIGNER.lower(), (
            f"signature must recover to signer; got {recovered}, expected {_TEST_SIGNER}\n"
            f"rebuilt msg: {rebuilt_msg}"
        )

    def test_nonce_user_signer_are_at_end(self):
        """Auth fields must come after user-provided params so the URL-encoded
        msg matches Aster's reference impl exactly."""
        signed = inject_auth(
            {"symbol": "BTCUSDT", "side": "BUY", "type": "MARKET"},
            user=_USER, signer=_TEST_SIGNER, private_key=_TEST_PK,
            strict_keys=FUTURES_STRICT_KEYS,
        )
        keys = list(signed.keys())
        assert keys[-4:] == ["nonce", "user", "signer", "signature"]

    def test_modifying_param_invalidates_signature(self):
        """Defense-in-depth: tampering with any field in the body breaks
        recovery. Confirms the signature actually binds to the body."""
        signed = inject_auth(
            {"symbol": "BTCUSDT", "side": "BUY", "type": "MARKET"},
            user=_USER, signer=_TEST_SIGNER, private_key=_TEST_PK,
            strict_keys=FUTURES_STRICT_KEYS,
        )
        sig = signed.pop("signature")
        signed["symbol"] = "ETHUSDT"  # tamper
        rebuilt_msg = urllib.parse.urlencode(signed)
        recovered = _server_recover(rebuilt_msg, sig)
        assert recovered.lower() != _TEST_SIGNER.lower()


class TestInjectAuth:
    """Verify the full auth injection flow."""

    def test_injects_all_fields(self):
        result = inject_auth(
            {"symbol": "BTCUSDT"},
            _USER, _TEST_SIGNER, _TEST_PK,
        )
        assert result["user"] == _USER
        assert result["signer"] == _TEST_SIGNER
        assert "nonce" in result
        assert result["signature"].startswith("0x")

    def test_preserves_original_params(self):
        result = inject_auth(
            {"symbol": "BTCUSDT", "side": "BUY"},
            _USER, _TEST_SIGNER, _TEST_PK,
        )
        assert result["symbol"] == "BTCUSDT"
        assert result["side"] == "BUY"

    def test_nonce_is_microsecond_precision(self):
        result = inject_auth({}, _USER, _TEST_SIGNER, _TEST_PK)
        nonce = int(result["nonce"])
        assert nonce > 1_000_000_000_000_000

    def test_nonce_increments(self):
        r1 = inject_auth({}, _USER, _TEST_SIGNER, _TEST_PK)
        r2 = inject_auth({}, _USER, _TEST_SIGNER, _TEST_PK)
        assert int(r2["nonce"]) >= int(r1["nonce"])


class TestGenerateAgentWallet:
    """Verify wallet generation."""

    def test_returns_address_and_key(self):
        wallet = generate_agent_wallet()
        assert "address" in wallet
        assert "private_key" in wallet

    def test_address_format(self):
        wallet = generate_agent_wallet()
        assert wallet["address"].startswith("0x")
        assert len(wallet["address"]) == 42

    def test_unique_each_call(self):
        w1 = generate_agent_wallet()
        w2 = generate_agent_wallet()
        assert w1["address"] != w2["address"]

    def test_generated_key_can_sign_and_recover(self):
        """End-to-end: a freshly generated agent can sign a body whose
        signature recovers to the agent's address."""
        wallet = generate_agent_wallet()
        signed = inject_auth(
            {"symbol": "BTCUSDT"},
            user=_USER,
            signer=wallet["address"],
            private_key=wallet["private_key"],
            strict_keys=FUTURES_STRICT_KEYS,
        )
        sig = signed.pop("signature")
        rebuilt_msg = urllib.parse.urlencode(signed)
        recovered = _server_recover(rebuilt_msg, sig)
        assert recovered.lower() == wallet["address"].lower()
