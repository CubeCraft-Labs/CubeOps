"""Home Assistant entry point for Cubecraft Production."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.components import websocket_api
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig

from .bridge import BridgeClient
from .const import CONF_BRIDGE_URL, CONF_POLL_MINUTES, CONF_SHARED_SECRET, DEFAULT_POLL_MINUTES, DOMAIN, PLATFORMS
from .coordinator import ProductionCoordinator
from .store import OrderStore
from .webhook import async_register_webhook, webhook_id


@dataclass(slots=True)
class RuntimeData:
    coordinator: ProductionCoordinator


type CubecraftConfigEntry = Any

STATIC_URL = f"/{DOMAIN}"
CARD_URL = f"{STATIC_URL}/cubecraft-production-card.js"


async def _async_register_frontend(hass: HomeAssistant) -> None:
    """Serve and auto-load the bundled workboard card once per Home Assistant.

    The whole www directory is served so the card can also load its bundled
    Nunito font. Caching stays off so an updated card is picked up on reload
    rather than needing a hard refresh.
    """
    if hass.data.get(f"{DOMAIN}_frontend"):
        return
    www = Path(__file__).parent / "www"
    await hass.http.async_register_static_paths([StaticPathConfig(STATIC_URL, str(www), False)])
    add_extra_js_url(hass, CARD_URL)
    hass.data[f"{DOMAIN}_frontend"] = True


async def async_setup_entry(hass: HomeAssistant, entry: CubecraftConfigEntry) -> bool:
    """Set up a configured Cubecraft pipeline."""
    store = OrderStore(hass)
    await store.async_load()
    bridge = BridgeClient(async_get_clientsession(hass), entry.data[CONF_BRIDGE_URL], entry.data[CONF_SHARED_SECRET])
    coordinator = ProductionCoordinator(hass, entry, bridge, store)
    entry.runtime_data = RuntimeData(coordinator)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await async_register_webhook(hass, entry, coordinator)
    _async_register_services(hass)
    _async_register_websocket_api(hass)
    await _async_register_frontend(hass)
    interval = timedelta(minutes=entry.options.get(CONF_POLL_MINUTES, DEFAULT_POLL_MINUTES))
    entry.async_on_unload(async_track_time_interval(hass, lambda _: hass.async_create_task(coordinator.async_poll_usps()), interval))
    hass.async_create_task(coordinator.async_reconcile())
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CubecraftConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unloaded


def _coordinator(hass: HomeAssistant, call: ServiceCall) -> ProductionCoordinator:
    entry_id = call.data.get("entry_id")
    entries = hass.data.get(DOMAIN, {})
    if entry_id:
        return entries[entry_id]
    if len(entries) != 1:
        raise ValueError("entry_id is required when multiple Cubecraft entries are configured")
    return next(iter(entries.values()))


async def _author(hass: HomeAssistant, call: ServiceCall) -> str:
    """Resolve the calling user's display name. async_get_user is a coroutine."""
    if call.context.user_id and (user := await hass.auth.async_get_user(call.context.user_id)):
        return user.name or user.id
    return "Home Assistant"


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, "claim"):
        return
    base = {vol.Required("order_id"): vol.Coerce(int), vol.Optional("entry_id"): str}

    async def claim(call: ServiceCall) -> None:
        await _coordinator(hass, call).async_claim(call.data["order_id"], await _author(hass, call))

    async def release(call: ServiceCall) -> None:
        await _coordinator(hass, call).async_release(call.data["order_id"], await _author(hass, call))

    async def set_stage(call: ServiceCall) -> None:
        await _coordinator(hass, call).async_set_stage(call.data["order_id"], call.data["stage"], await _author(hass, call), call.data.get("note"))

    async def add_note(call: ServiceCall) -> None:
        await _coordinator(hass, call).async_add_note(call.data["order_id"], await _author(hass, call), call.data["message"])

    async def resolve(call: ServiceCall) -> None:
        await _coordinator(hass, call).async_resolve_exception(call.data["order_id"], await _author(hass, call), call.data.get("note", ""))

    async def reconcile(call: ServiceCall) -> None:
        await _coordinator(hass, call).async_reconcile()

    async def poll(call: ServiceCall) -> None:
        await _coordinator(hass, call).async_poll_usps()

    hass.services.async_register(DOMAIN, "claim", claim, schema=vol.Schema(base))
    hass.services.async_register(DOMAIN, "release", release, schema=vol.Schema(base))
    hass.services.async_register(DOMAIN, "set_stage", set_stage, schema=vol.Schema({**base, vol.Required("stage"): str, vol.Optional("note"): str}))
    hass.services.async_register(DOMAIN, "add_note", add_note, schema=vol.Schema({**base, vol.Required("message"): str}))
    hass.services.async_register(DOMAIN, "resolve_exception", resolve, schema=vol.Schema({**base, vol.Optional("note"): str}))
    hass.services.async_register(DOMAIN, "reconcile", reconcile, schema=vol.Schema({vol.Optional("entry_id"): str}))
    hass.services.async_register(DOMAIN, "poll_usps", poll, schema=vol.Schema({vol.Optional("entry_id"): str}))


def _async_register_websocket_api(hass: HomeAssistant) -> None:
    """Return order details only to authenticated Home Assistant sessions."""
    if hass.data.get(f"{DOMAIN}_ws_registered"):
        return

    @websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/orders", vol.Optional("entry_id"): str})
    @websocket_api.async_response
    async def websocket_orders(hass: HomeAssistant, connection, msg: dict[str, Any]) -> None:
        try:
            entries = hass.data.get(DOMAIN, {})
            entry_id = msg.get("entry_id")
            if entry_id:
                coordinator = entries[entry_id]
            elif len(entries) == 1:
                coordinator = next(iter(entries.values()))
            else:
                raise ValueError("entry_id is required when multiple pipelines are configured")
            orders = [order.to_dict() for order in coordinator.store.orders.values()]
            connection.send_result(msg["id"], {"orders": orders})
        except (KeyError, ValueError) as err:
            connection.send_error(msg["id"], "not_found", str(err))

    websocket_api.async_register_command(hass, websocket_orders)
    hass.data[f"{DOMAIN}_ws_registered"] = True
