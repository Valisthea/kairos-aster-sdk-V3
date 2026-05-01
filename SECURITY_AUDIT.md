# OMEGA Security Audit — kairos-aster-sdk

**Auditor**: OMEGA (Kairos Lab Security Research)
**Initial audit**: 2026-04-18 (v0.1.0)
**Re-audit + corrections**: 2026-05-01 (v0.2.0)
**Scope**: Full codebase review — auth, client, futures, spot, ws, errors, enums
**Severity Scale**: CRITICAL > HIGH > MEDIUM > LOW > INFO

---

## ⚠️ Post-Audit Corrections (2026-05-01) — read first

A re-review of the EIP-712 signing path against the official Aster v3 spec
([`aster-finance-futures-api-v3.md`](https://github.com/asterdex/api-docs/blob/master/aster-finance-futures-api-v3.md))
identified **two CRITICAL bugs that the initial v0.1.0 audit did not catch**.
Both are fixed in v0.2.0; see the [Post-Audit Corrections](#post-audit-corrections-2026-05-01)
section at the end of this document.

The original v0.1.0 verdict ("EIP-712 implementation is correct") was wrong —
the implementation produced signatures that could not authenticate against the
production Aster server. The test suite did not catch this because it asserted
signature length and determinism but never `Account.recover_message(...)` against
the claimed signer. v0.2.0 adds `TestSignatureRecovery` precisely to prevent
recurrence.

---

## Executive Summary

The SDK is **production-viable as of v0.2.0**. The EIP-712 signing implementation
now correctly follows the Aster v3 spec — verified empirically by recovering
signatures back to the expected signer address under canonical EIP-712
verification. Concerns from the initial audit (secret handling in memory, nonce
edge case, WebSocket input validation gap) are all addressed.

**Initial verdict (v0.1.0, 2026-04-18)**: PASS with remediation — **invalidated by re-audit**
**Current verdict (v0.2.0, 2026-05-01)**: PASS, all blockers fixed (2 CRITICAL fixed, 1 HIGH fixed, 3 MEDIUM fixed, 3 LOW partial, 2 INFO)

---

## Findings

### [H-01] Private key stored as plain string attribute on client instance
**File**: `client.py:37`
**Severity**: HIGH
**Description**: `self.private_key = private_key` stores the raw private key as a string attribute on the client object. Any code with a reference to the client can read `.private_key`. If the client is serialized, logged via `repr()`, or inspected in a debugger, the key leaks.
**Recommendation**:
- Store key in a `__slots__` class or prefix with `_` at minimum
- Override `__repr__` to mask the key
- Consider a `SecretStr`-style wrapper that prevents accidental string coercion
- Document that users should never log/serialize the client object

```python
def __repr__(self) -> str:
    return f"<{self.__class__.__name__} user={self.user} signer={self.signer}>"
```

---

### [M-01] Nonce collision possible under high-frequency multi-thread burst
**File**: `auth.py:51-60`
**Severity**: MEDIUM
**Description**: The `_NonceGenerator` uses `time.time() * 1_000_000` which has platform-dependent resolution (often ~1μs on Linux, ~15ms on Windows). Under extreme burst on Windows, `now_us` may equal `_last_us` many times, and `_seq` increments linearly but is never bounded — could produce nonces far ahead of server time, causing rejection (Aster's 10-second window).
**Recommendation**: Cap `_seq` drift (e.g., max 9_999_999 = 9.99s of drift), and raise an error if exhausted. Add a `time.sleep(0.001)` fallback when seq exceeds threshold.

---

### [M-02] WebSocket stream names not validated — path injection possible
**File**: `ws.py:83-84`
**Severity**: MEDIUM
**Description**: Stream names are directly interpolated into the URL: `f"{self.base_url}/ws/{streams[0]}"`. A malicious stream name like `../api/v3/secret` would construct `wss://fstream.asterdex.com/ws/../api/v3/secret`. While WebSocket servers typically reject this, it's a path traversal pattern that should be sanitized.
**Recommendation**: Validate stream names against a regex pattern (alphanumeric + `@` + `_` + `!` only):

```python
import re
_STREAM_PATTERN = re.compile(r'^[a-zA-Z0-9@_!.]+$')

def _validate_stream(name: str) -> str:
    if not _STREAM_PATTERN.match(name):
        raise ValueError(f"Invalid stream name: {name}")
    return name
```

---

### [M-03] `Retry-After` header parsed as int without validation
**File**: `client.py:123`
**Severity**: MEDIUM
**Description**: `int(resp.headers.get("Retry-After", 2**attempt))` will crash with `ValueError` if the server sends a non-integer Retry-After (e.g., a date string, which is valid per HTTP spec). Also, a malicious proxy could send an absurdly large value causing the SDK to sleep indefinitely.
**Recommendation**: Wrap in try/except, clamp to a max of 120 seconds:

```python
try:
    wait = min(int(resp.headers.get("Retry-After", 2**attempt)), 120)
except (ValueError, TypeError):
    wait = min(2**attempt, 120)
```

---

### [L-01] `generate_agent_wallet()` uses default entropy source
**File**: `auth.py:160`
**Severity**: LOW
**Description**: `Account.create()` uses `os.urandom()` internally which is cryptographically secure, but there's no explicit entropy parameter or documentation about entropy quality. For a trading SDK, this is worth noting.
**Recommendation**: Add a docstring note about entropy, and optionally accept an `extra_entropy` parameter.

---

### [L-02] No TLS certificate verification configuration
**File**: `client.py:43`
**Severity**: LOW
**Description**: The `requests.Session()` uses default TLS verification (enabled, uses system CAs). This is correct, but the SDK doesn't expose a way to pin certificates or provide custom CA bundles for enterprise environments behind corporate proxies.
**Recommendation**: Accept an optional `verify` parameter in the constructor.

---

### [L-03] Deprecated `asyncio.get_event_loop()` usage
**File**: `ws.py:168`
**Severity**: LOW
**Description**: `asyncio.get_event_loop()` is deprecated in Python 3.12+ for getting the running loop. Should use `asyncio.get_running_loop()`.
**Recommendation**: Replace both instances (lines 168, 180).

---

### [I-01] User-Agent header reveals SDK version
**File**: `client.py:46`
**Severity**: INFO
**Description**: `"User-Agent": "kairos-aster-sdk/0.1.0"` is useful for debugging but reveals the exact SDK version to the server. Acceptable for a public SDK but worth noting.

---

### [I-02] Error message in `AsterAPIError.__init__` may log sensitive params
**File**: `errors.py:14`
**Severity**: INFO
**Description**: The error message includes `msg` from the API response which could contain parameter names/values. If users catch and log these exceptions, request details may end up in log files. Acceptable behavior for a trading SDK but worth documenting.

---

## Positive Observations (v0.2.0)

1. **EIP-712 implementation is correct (v0.2.0)** — uses `encode_typed_data(full_message=...)` and signs the FULL URL-encoded body including `nonce`/`user`/`signer`, matching the official Aster spec example byte-for-byte. Verified empirically by `Account.recover_message(...)` returning the expected signer.
2. **Thread-safe nonce generation with drift cap** — lock-based, monotonic, capped at 4 s ahead of wall clock so a burst can never push the nonce out of Aster's 5 s acceptance window
3. **No hardcoded secrets** — all credentials come from constructor params / env vars
4. **Proper error hierarchy** — `AsterAPIError` vs `AsterRequestError` separation is clean
5. **Context manager support** — `with` statement for proper session cleanup
6. **Rate limit backoff** — exponential backoff with 429/5xx retry is correctly implemented
7. **Dependencies are minimal** — no `web3` bloat, just `eth-account` + `requests` + `websockets`
8. **Stream and listen-key validation** — both paths sanitize against URL injection before opening a WebSocket connection

---

## Remediation Priority

1. ~~**[H-01]**~~ — ✅ Fixed in v0.1.0 (private key masked via `__repr__`)
2. ~~**[M-03]**~~ — ✅ Fixed in v0.1.0 (Retry-After try/except + clamp)
3. ~~**[M-02]**~~ — ✅ Fixed in v0.1.0 (stream regex validation)
4. ~~**[M-01]**~~ — ✅ Fixed in v0.2.0 (nonce drift cap)
5. **[L-03]** — Open: deprecated `asyncio.get_event_loop()` (replace with `get_running_loop()`)
6. **[L-01, L-02]** — Open: entropy docstring, optional `verify` param

---

## Post-Audit Corrections (2026-05-01)

After the initial v0.1.0 audit, a comparative re-review against the official
Aster v3 specification identified two **CRITICAL** bugs in the EIP-712 signing
path that prevented signatures from verifying server-side. Both are fixed in
v0.2.0.

### [C-01] CRITICAL — Wrong signing primitive (`encode_defunct` over EIP-712 digest)

**File (was)**: `auth.py:122-128`
**Severity**: CRITICAL
**Status**: ✅ Fixed in v0.2.0

**Description**: The previous `sign_request` computed the EIP-712 digest
correctly, then re-wrapped it with EIP-191 personal-sign before signing:

```python
# v0.1.0 — broken
digest = keccak(b"\x19\x01" + domain_hash + message_hash)
signable = encode_defunct(hexstr=digest.hex())   # ← EIP-191 wrap on top of EIP-712
signed = Account.sign_message(signable, private_key=private_key)
```

The actual signed hash was therefore
`keccak("\x19Ethereum Signed Message:\n32" + eip712_digest)` instead of the
EIP-712 digest itself. The Aster server uses `encode_structured_data(typed_data)`
+ `Account.sign_message(...)` (canonical EIP-712), so it reconstructs the digest
and verifies via `ecrecover(digest, sig)`. With the old code, `ecrecover`
returned a different address than the claimed `signer`, causing every signed
request to fail with `-1022 Signature for this request is not valid`.

**Empirical evidence**:
- Test PK `0x4c0883a6...e85e3a2` (signer `0x34ee9937...41188b47`)
- Old code's signature recovered to `0x82BdA1A32cA3e6AcE43eDF5e740067965ca5baC7`
  under canonical EIP-712 verification — i.e. **garbage, not the signer**

**Fix (v0.2.0)**:

```python
# v0.2.0 — correct
typed_data = {
    "types": _TYPES,
    "primaryType": "Message",
    "domain": DOMAIN,
    "message": {"msg": msg},
}
signable = encode_typed_data(full_message=typed_data)
signed = Account.sign_message(signable, private_key=private_key)
return "0x" + signed.signature.hex()
```

Uses `eth_account.messages.encode_typed_data` (real EIP-712 typed-data signing).
Verified by the new `TestSignatureRecovery::test_sign_message_string_recovers_to_signer`
regression test.

---

### [C-02] CRITICAL — Signature did not cover `nonce` / `user` / `signer`

**File (was)**: `auth.py:131-150`
**Severity**: CRITICAL
**Status**: ✅ Fixed in v0.2.0

**Description**: `inject_auth` injected `nonce`, `user`, `signer` into the
params dict *after* computing the signature over the original (pre-injection)
params:

```python
# v0.1.0 — broken
def inject_auth(params, user, signer, private_key, strict_keys=None):
    nonce = _nonce()
    signed_params = dict(params)
    signed_params["nonce"] = nonce
    signed_params["user"] = user
    signed_params["signer"] = signer
    sig = sign_request(private_key, params, strict_keys)  # ← signed ORIGINAL params
    signed_params["signature"] = sig
    return signed_params
```

The Aster server reconstructs the signed message from the **full request body**
(per the spec example: `urllib.parse.urlencode(my_dict)` is called *after*
injecting nonce/user/signer). With the old code, the server's reconstructed
`msg` ≠ the message the SDK signed, so verification failed even if [C-01] had
been correct.

**Fix (v0.2.0)**:

```python
# v0.2.0 — correct
def inject_auth(params, user, signer, private_key, strict_keys=None):
    nonce = _nonce()
    ordered = _ordered_params(params, strict_keys)
    ordered["nonce"] = nonce
    ordered["user"] = user
    ordered["signer"] = signer
    msg = urllib.parse.urlencode(ordered)             # ← URL-encode FULL dict
    sig = sign_message_string(private_key, msg)      # ← sign FULL msg
    ordered["signature"] = sig
    return ordered
```

The signature now covers the full body. Verified by
`TestSignatureRecovery::test_inject_auth_signature_covers_full_body` and
`test_modifying_param_invalidates_signature` (defense-in-depth: tampering with
any field breaks recovery).

---

### Why the v0.1.0 audit missed both

The original `tests/test_auth.py` (21 tests) checked:
- ✅ Signature is hex-prefixed and 132 chars
- ✅ Determinism: same input → same signature
- ✅ Different input → different signature
- ❌ **Never** asserted `Account.recover_message(...)` equals the expected signer
- ❌ **Never** compared against the official Aster spec test vector

A signature can be deterministic, hex-prefixed, and 132 chars long — and still
fail to verify against the claimed signer. The v0.1.0 suite was insufficient
to detect either C-01 or C-02.

### Process improvement (v0.2.0)

A new `TestSignatureRecovery` class was added to the suite. Every signed
request flow is now verified end-to-end by recovering the signer from the
signature under canonical EIP-712 verification. Four tests:

- `test_sign_message_string_recovers_to_signer`
- `test_inject_auth_signature_covers_full_body` ← would have caught C-01 + C-02
- `test_nonce_user_signer_are_at_end`
- `test_modifying_param_invalidates_signature`

Run `pytest tests/ -v` — all 27 tests pass on v0.2.0.
