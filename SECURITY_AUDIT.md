# OMEGA Security Audit — kairos-aster-sdk v0.1.0

**Auditor**: OMEGA (Kairos Lab Security Research)
**Date**: 2026-04-18
**Scope**: Full codebase review — auth, client, futures, spot, ws, errors, enums
**Severity Scale**: CRITICAL > HIGH > MEDIUM > LOW > INFO

---

## Executive Summary

The SDK is **production-viable with 4 fixes required before public release**. No critical vulnerabilities found. The EIP-712 signing implementation correctly follows the Aster v3 spec. Main concerns are around secret handling in memory, a potential nonce edge case, and one WebSocket input validation gap.

**Verdict**: PASS with remediation (0 CRITICAL, 1 HIGH, 3 MEDIUM, 3 LOW, 2 INFO)

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

## Positive Observations

1. **EIP-712 implementation is correct** — domain separator, message hash, and `\x19\x01` prefix match the Aster spec exactly
2. **Thread-safe nonce generation** — lock-based approach prevents duplicates in multi-threaded contexts
3. **No hardcoded secrets** — all credentials come from constructor params / env vars
4. **Proper error hierarchy** — `AsterAPIError` vs `AsterRequestError` separation is clean
5. **Context manager support** — `with` statement for proper session cleanup
6. **Rate limit backoff** — exponential backoff with 429/5xx retry is correctly implemented
7. **Dependencies are minimal** — no `web3` bloat, just `eth-account` + `requests` + `websockets`

---

## Remediation Priority

1. **[H-01]** — Fix before public release (mask private key in repr)
2. **[M-03]** — Fix before release (Retry-After crash)
3. **[M-02]** — Fix before release (stream validation)
4. **[M-01]** — Fix before v0.2 (nonce drift cap)
5. **[L-03]** — Fix before release (deprecation warning)
6. **[L-01, L-02]** — Nice to have for v0.2

**Estimated fix time**: 30 minutes for all pre-release items.
