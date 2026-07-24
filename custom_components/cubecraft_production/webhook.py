"""Authenticated webhook view for events emitted by the WordPress bridge."""

from __future__ import annotations

import json

from aiohttp import web
from homeassistant.components.webhook import async_register, async_unregister
from homeassistant.core import HomeAssistant

from .auth import validate_signature
from .const import CONF_SHARED_SECRET, DOMAIN


def webhook_id(entry_id: str) -> str:
    return f"{DOMAIN}-{entry_id}"


async def async_register_webhook(hass: HomeAssistant, entry, coordinator) -> None:
    """Register one webhook per config entry."""
    identifier = webhook_id(entry.entry_id)

    async def handle(hass: HomeAssistant, webhook_id: str, request: web.Request) -> web.Response:
        body = await request.read()
        secret = entry.data[CONF_SHARED_SECRET]
        if not validate_signature(
            secret,
            request.headers.get("X-Cubecraft-Timestamp", ""),
            request.headers.get("X-Cubecraft-Nonce", ""),
            body,
            request.headers.get("X-Cubecraft-Signature", ""),
        ):
            return web.json_response({"error": "invalid signature"}, status=401)
        nonce = request.headers.get("X-Cubecraft-Nonce", "")
        if coordinator.store.has_event(f"nonce:{nonce}"):
            return web.json_response({"error": "replayed request"}, status=409)
        try:
            payload = json.loads(body)
            applied = await coordinator.async_process_event(payload)
            await coordinator.store.async_record_event(f"nonce:{nonce}")
        except (ValueError, TypeError, json.JSONDecodeError) as err:
            return web.json_response({"error": str(err)}, status=400)
        return web.json_response({"accepted": True, "applied": applied})

    async_register(hass, DOMAIN, "Cubecraft Production", identifier, handle)
    entry.async_on_unload(lambda: async_unregister(hass, identifier))
