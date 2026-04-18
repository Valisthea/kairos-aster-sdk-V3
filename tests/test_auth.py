"""
Tests for the auth module — the core of the SDK.

Run: pytest tests/ -v
"""

import pytest
from kairos_aster.auth import (
    build_msg,
    sign_request,
    inject_auth,
    generate_agent_wallet,
    FUTURES_STRICT_KEYS,
    SPOT_STRICT_KEYS,
    DOMAIN,
)


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
        # strict keys first, then extras sorted
        assert "symbol=BTCUSDT&side=BUY&type=LIMIT" in msg
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
    """Verify signature output format."""

    # Deterministic test key (DO NOT use in production)
    _TEST_PK = "0x4c0883a69102937d6231471b5dbb6204fe512961708279f9d92e8e632e85e3a2"

    def test_returns_0x_prefixed(self):
        sig = sign_request(self._TEST_PK, {"symbol": "BTCUSDT"})
        assert sig.startswith("0x")

    def test_signature_length(self):
        sig = sign_request(self._TEST_PK, {"symbol": "BTCUSDT"})
        # 0x + 130 hex chars (65 bytes r+s+v)
        assert len(sig) == 132

    def test_deterministic(self):
        params = {"symbol": "BTCUSDT", "side": "BUY"}
        sig1 = sign_request(self._TEST_PK, params)
        sig2 = sign_request(self._TEST_PK, params)
        assert sig1 == sig2

    def test_different_params_different_sig(self):
        sig1 = sign_request(self._TEST_PK, {"symbol": "BTCUSDT"})
        sig2 = sign_request(self._TEST_PK, {"symbol": "ETHUSDT"})
        assert sig1 != sig2


class TestInjectAuth:
    """Verify the full auth injection flow."""

    _TEST_PK = "0x4c0883a69102937d6231471b5dbb6204fe512961708279f9d92e8e632e85e3a2"
    _USER = "0xMainWallet"
    _SIGNER = "0xAgentWallet"

    def test_injects_all_fields(self):
        result = inject_auth(
            {"symbol": "BTCUSDT"},
            self._USER, self._SIGNER, self._TEST_PK,
        )
        assert result["user"] == self._USER
        assert result["signer"] == self._SIGNER
        assert "nonce" in result
        assert result["signature"].startswith("0x")

    def test_preserves_original_params(self):
        result = inject_auth(
            {"symbol": "BTCUSDT", "side": "BUY"},
            self._USER, self._SIGNER, self._TEST_PK,
        )
        assert result["symbol"] == "BTCUSDT"
        assert result["side"] == "BUY"

    def test_nonce_is_microsecond_precision(self):
        result = inject_auth(
            {}, self._USER, self._SIGNER, self._TEST_PK,
        )
        nonce = int(result["nonce"])
        # Should be in microseconds (> 1e15)
        assert nonce > 1_000_000_000_000_000

    def test_nonce_increments(self):
        r1 = inject_auth({}, self._USER, self._SIGNER, self._TEST_PK)
        r2 = inject_auth({}, self._USER, self._SIGNER, self._TEST_PK)
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
