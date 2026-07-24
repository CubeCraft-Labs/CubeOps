"""Client for the narrow Cubecraft WordPress bridge API."""

from __future__ import annotations

import json
import secrets
import time
from typing import Any

import aiohttp

from .auth import signature


class BridgeError(Exception):
    """The WordPress bridge rejected or could not process a request."""


class BridgeClient:
    def __init__(self, session: aiohttp.ClientSession, base_url: str, secret: str) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._secret = secret

    async def async_get_orders(self) -> list[dict[str, Any]]:
        result = await self._request("GET", "/orders")
        return result.get("orders", [])

    async def async_update_stage(self, order_id: int, stage: str, note: str) -> None:
        await self._request("POST", f"/orders/{order_id}/stage", {"stage": stage, "note": note})

    async def async_complete_order(self, order_id: int, note: str) -> None:
        await self._request("POST", f"/orders/{order_id}/complete", {"note": note})

    async def _request(self, method: str, path: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        body = json.dumps(data, separators=(",", ":"), sort_keys=True).encode() if data else b""
        timestamp = str(int(time.time()))
        nonce = secrets.token_urlsafe(18)
        headers = {
            "Content-Type": "application/json",
            "X-Cubecraft-Timestamp": timestamp,
            "X-Cubecraft-Nonce": nonce,
            "X-Cubecraft-Signature": signature(self._secret, timestamp, nonce, body),
        }
        try:
            async with self._session.request(method, f"{self._base_url}{path}", data=body, headers=headers, timeout=20) as response:
                text = await response.text()
                if response.status >= 300:
                    raise BridgeError(f"Bridge HTTP {response.status}: {text[:200]}")
                return json.loads(text) if text else {}
        except aiohttp.ClientError as err:
            raise BridgeError(str(err)) from err
