"""
Base HTTP client for AsterDEX V3 API.

Handles request signing, rate-limit backoff, and error parsing so
the Futures/Spot clients stay clean.
"""

from __future__ import annotations

import time
import logging
from typing import Any

import requests

from .auth import inject_auth, FUTURES_STRICT_KEYS, SPOT_STRICT_KEYS
from .errors import AsterAPIError, AsterRequestError

logger = logging.getLogger("kairos_aster")


class BaseClient:
    """Shared HTTP logic for Futures and Spot V3 clients."""

    def __init__(
        self,
        user: str,
        signer: str,
        private_key: str,
        base_url: str,
        *,
        timeout: int = 10,
        max_retries: int = 3,
        show_weight: bool = False,
    ) -> None:
        self.user = user
        self.signer = signer
        self._private_key = private_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.show_weight = show_weight
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "kairos-aster-sdk/0.1.0",
        })

    # ── Public (unsigned) requests ────────────────────────────────────

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} user={self.user} signer={self.signer}>"

    def get_public(self, path: str, params: dict | None = None) -> Any:
        """GET request to a public endpoint (no auth)."""
        url = f"{self.base_url}{path}"
        return self._do("GET", url, params=params)

    # ── Signed requests ───────────────────────────────────────────────

    def get_signed(
        self,
        path: str,
        params: dict | None = None,
        strict_keys: list[str] | None = None,
    ) -> Any:
        """Signed GET — auth params appended to query string."""
        params = params or {}
        signed = inject_auth(
            params, self.user, self.signer, self._private_key, strict_keys
        )
        url = f"{self.base_url}{path}"
        return self._do("GET", url, params=signed)

    def post_signed(
        self,
        path: str,
        params: dict | None = None,
        strict_keys: list[str] | None = None,
    ) -> Any:
        """Signed POST — auth params in request body."""
        params = params or {}
        signed = inject_auth(
            params, self.user, self.signer, self._private_key, strict_keys
        )
        url = f"{self.base_url}{path}"
        return self._do("POST", url, data=signed,
                        headers={"Content-Type": "application/x-www-form-urlencoded"})

    def delete_signed(
        self,
        path: str,
        params: dict | None = None,
        strict_keys: list[str] | None = None,
    ) -> Any:
        """Signed DELETE."""
        params = params or {}
        signed = inject_auth(
            params, self.user, self.signer, self._private_key, strict_keys
        )
        url = f"{self.base_url}{path}"
        return self._do("DELETE", url, params=signed)

    # ── Internal ──────────────────────────────────────────────────────

    def _do(self, method: str, url: str, **kwargs: Any) -> Any:
        """Execute HTTP request with retry on 429/5xx."""
        kwargs.setdefault("timeout", self.timeout)
        last_err: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._session.request(method, url, **kwargs)
            except requests.RequestException as e:
                last_err = AsterRequestError(0, str(e))
                logger.warning("Request failed (attempt %d): %s", attempt, e)
                time.sleep(min(2**attempt, 10))
                continue

            # Log weight usage
            if self.show_weight:
                w = resp.headers.get("X-MBX-USED-WEIGHT-1m", "?")
                logger.info("Weight used: %s | %s %s", w, method, url)

            # Rate limit — back off
            if resp.status_code == 429:
                try:
                    wait = min(int(resp.headers.get("Retry-After", 2**attempt)), 120)
                except (ValueError, TypeError):
                    wait = min(2**attempt, 120)
                logger.warning("Rate limited, waiting %ds", wait)
                time.sleep(wait)
                continue

            # IP ban
            if resp.status_code == 418:
                raise AsterRequestError(418, "IP auto-banned — stop requests")

            # Server error — retry
            if resp.status_code >= 500:
                last_err = AsterRequestError(resp.status_code, resp.text)
                logger.warning("Server error %d, retrying…", resp.status_code)
                time.sleep(min(2**attempt, 10))
                continue

            # Parse response
            try:
                data = resp.json()
            except ValueError:
                raise AsterRequestError(resp.status_code, resp.text)

            # API-level error
            if isinstance(data, dict) and "code" in data and data["code"] < 0:
                raise AsterAPIError(data["code"], data.get("msg", ""))

            return data

        if last_err:
            raise last_err
        raise AsterRequestError(0, "Max retries exceeded")

    def close(self) -> None:
        """Close the underlying session."""
        self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
