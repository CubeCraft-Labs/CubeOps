"""Cubecraft pipeline orchestration and USPS tracking."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .bridge import BridgeClient, BridgeError
from .const import (
    CONF_ESCALATION_HOURS,
    CONF_NOTIFY_SERVICE,
    CONF_USPS_CLIENT_ID,
    CONF_USPS_CLIENT_SECRET,
    CONF_USPS_TRACKING_URL,
    DEFAULT_ESCALATION_HOURS,
    DEFAULT_USPS_TRACKING_URL,
    DOMAIN,
    EVENT_ORDER_CANCELLED,
    EVENT_ORDER_CHANGED,
    EVENT_ORDER_PROCESSING,
    EVENT_SHIPMENT_LABEL,
)
from .models import Order, Shipment, utcnow
from .store import OrderStore
from .usps import _is_accepted, _tracking_status

SIGNAL_UPDATED = f"{DOMAIN}_updated"


class ProductionCoordinator:
    """Own the order queue, bridge synchronization, and carrier polling."""

    def __init__(self, hass: HomeAssistant, entry, bridge: BridgeClient, store: OrderStore) -> None:
        self.hass = hass
        self.entry = entry
        self.bridge = bridge
        self.store = store
        self.lock = asyncio.Lock()
        self._usps_token: str | None = None
        self._usps_token_expires = datetime.min.replace(tzinfo=timezone.utc)
        self.bridge_connected = False

    async def async_process_event(self, payload: dict[str, Any]) -> bool:
        """Apply one signed bridge event exactly once. Return true when newly applied."""
        event_id = str(payload.get("event_id", ""))
        event_type = payload.get("type")
        if not event_id or not event_type:
            raise ValueError("Bridge event needs event_id and type")
        async with self.lock:
            if self.store.has_event(event_id):
                return False
            await self._apply_event(event_type, payload)
            await self.store.async_record_event(event_id)
        async_dispatcher_send(self.hass, SIGNAL_UPDATED)
        return True

    async def _apply_event(self, event_type: str, payload: dict[str, Any]) -> None:
        data = payload.get("order") or {}
        order_id = int(data.get("id") or payload.get("order_id"))
        if event_type == EVENT_ORDER_PROCESSING:
            existing = self.store.orders.get(order_id)
            if existing:
                self._merge_order(existing, data)
                await self.store.async_save()
                return
            order = self._order_from_bridge(data)
            await self.store.async_upsert(order)
            await self.async_notify("New paid production order", f"Order #{order.order_number} has entered the production queue.")
            self.hass.bus.async_fire(f"{DOMAIN}_order_created", {"order_id": order.order_id, "order_number": order.order_number})
            return
        if event_type == EVENT_ORDER_CHANGED:
            status = data.get("status")
            if status in {"cancelled", "refunded", "failed"}:
                await self._handle_cancelled(order_id, status)
                return
            if order := self.store.orders.get(order_id):
                self._merge_order(order, data)
                await self.store.async_save()
            return
        if event_type == EVENT_ORDER_CANCELLED:
            await self._handle_cancelled(order_id, str(data.get("status", "cancelled")))
            return
        if event_type == EVENT_SHIPMENT_LABEL:
            order = self.store.orders.get(order_id)
            if not order:
                order = self._order_from_bridge(data)
            self._merge_order(order, data)
            for shipment_data in payload.get("shipments", data.get("shipments", [])):
                self._merge_shipment(order, shipment_data)
            order.add_note("WooCommerce Shipping", "Shipping label purchased and tracking recorded")
            await self.store.async_upsert(order)
            return
        raise ValueError(f"Unsupported bridge event type: {event_type}")

    async def _handle_cancelled(self, order_id: int, status: str) -> None:
        order = self.store.orders.get(order_id)
        if not order:
            return
        if order.stage == "queued" and not order.assigned_to:
            del self.store.orders[order_id]
            await self.store.async_save()
            return
        order.blocked = True
        order.exception = f"WooCommerce order is {status}; operator decision required"
        order.add_note("WooCommerce", order.exception)
        await self.store.async_upsert(order)
        await self.async_notify("Production exception", f"Order #{order.order_number} is {status} and has been blocked.")

    def _order_from_bridge(self, data: dict[str, Any]) -> Order:
        return Order(
            order_id=int(data["id"]),
            order_number=str(data.get("number", data["id"])),
            created_at=data.get("date_created_gmt") or data.get("created_at") or utcnow(),
            customer=data.get("shipping") or {},
            items=data.get("line_items") or data.get("items") or [],
            shipping_method=data.get("shipping_method") or _shipping_method(data),
            customer_note=data.get("customer_note"),
            order_url=data.get("admin_url"),
            shipments=[Shipment.from_dict(item) for item in data.get("shipments", [])],
        )

    def _merge_order(self, order: Order, data: dict[str, Any]) -> None:
        order.customer = data.get("shipping") or order.customer
        order.items = data.get("line_items") or data.get("items") or order.items
        order.shipping_method = data.get("shipping_method") or _shipping_method(data) or order.shipping_method
        order.customer_note = data.get("customer_note", order.customer_note)
        order.order_url = data.get("admin_url", order.order_url)
        for shipment in data.get("shipments", []):
            self._merge_shipment(order, shipment)
        order.updated_at = utcnow()

    @staticmethod
    def _merge_shipment(order: Order, data: dict[str, Any]) -> None:
        tracking_number = str(data.get("tracking_number", ""))
        shipment_id = str(data.get("shipment_id") or data.get("tracking_id") or tracking_number)
        if not shipment_id or not tracking_number:
            return
        existing = next((item for item in order.shipments if item.shipment_id == shipment_id), None)
        if not existing:
            order.shipments.append(Shipment(
                shipment_id=shipment_id,
                tracking_number=tracking_number,
                carrier=data.get("carrier") or data.get("tracking_provider") or "USPS",
                status=data.get("status", "label_created"),
                ship_date=data.get("ship_date") or data.get("date_shipped"),
                refunded=bool(data.get("refunded", False)),
                tracking_url=data.get("tracking_url") or data.get("tracking_link"),
            ))
            return
        existing.status = data.get("status", existing.status)
        existing.ship_date = data.get("ship_date") or data.get("date_shipped") or existing.ship_date
        existing.refunded = bool(data.get("refunded", existing.refunded))
        existing.tracking_url = data.get("tracking_url") or data.get("tracking_link") or existing.tracking_url

    async def async_set_stage(self, order_id: int, stage: str, author: str, note: str | None = None) -> None:
        async with self.lock:
            order = self.store.get(order_id)
            if stage == "awaiting_usps" and not any(not shipment.refunded for shipment in order.shipments):
                raise ValueError("A purchased USPS label is required before awaiting USPS")
            order.move_to(stage, author, note)
            try:
                await self.bridge.async_update_stage(order_id, stage, order.notes[-1]["message"])
                self.bridge_connected = True
            except BridgeError as err:
                order.blocked = True
                order.exception = f"WooCommerce stage sync failed: {err}"
                order.add_note("Cubecraft", order.exception)
                await self.store.async_upsert(order)
                raise
            await self.store.async_upsert(order)
        async_dispatcher_send(self.hass, SIGNAL_UPDATED)
        self.hass.bus.async_fire(f"{DOMAIN}_stage_changed", {"order_id": order_id, "stage": stage})

    async def async_claim(self, order_id: int, author: str) -> None:
        async with self.lock:
            order = self.store.get(order_id)
            if order.blocked:
                raise ValueError(order.exception or "Order is blocked")
            if order.assigned_to and order.assigned_to != author:
                raise ValueError(f"Order is already claimed by {order.assigned_to}")
            order.assigned_to = author
            order.add_note(author, "Claimed production work")
            await self.store.async_upsert(order)
        async_dispatcher_send(self.hass, SIGNAL_UPDATED)

    async def async_release(self, order_id: int, author: str) -> None:
        async with self.lock:
            order = self.store.get(order_id)
            if order.assigned_to not in {None, author}:
                raise ValueError(f"Only {order.assigned_to} can release this order")
            order.assigned_to = None
            order.add_note(author, "Released production work")
            await self.store.async_upsert(order)
        async_dispatcher_send(self.hass, SIGNAL_UPDATED)

    async def async_add_note(self, order_id: int, author: str, message: str) -> None:
        async with self.lock:
            order = self.store.get(order_id)
            order.add_note(author, message)
            try:
                await self.bridge.async_update_stage(order_id, order.stage, message)
                self.bridge_connected = True
            except BridgeError as err:
                order.blocked = True
                order.exception = f"WooCommerce note sync failed: {err}"
                order.add_note("Cubecraft", order.exception)
                await self.store.async_upsert(order)
                raise
            await self.store.async_upsert(order)
        async_dispatcher_send(self.hass, SIGNAL_UPDATED)

    async def async_resolve_exception(self, order_id: int, author: str, note: str) -> None:
        async with self.lock:
            order = self.store.get(order_id)
            order.blocked = False
            order.exception = None
            order.add_note(author, note or "Exception resolved")
            await self.store.async_upsert(order)
        async_dispatcher_send(self.hass, SIGNAL_UPDATED)

    async def async_reconcile(self) -> None:
        orders = await self.bridge.async_get_orders()
        self.bridge_connected = True
        for raw in orders:
            event_type = EVENT_ORDER_PROCESSING if int(raw["id"]) not in self.store.orders else EVENT_ORDER_CHANGED
            payload = {"event_id": f"reconcile:{raw['id']}:{raw.get('date_modified_gmt', '')}", "type": event_type, "order": raw}
            await self.async_process_event(payload)

    async def async_poll_usps(self) -> None:
        """Poll every active USPS label and complete only fully accepted orders."""
        changed = False
        async with self.lock:
            for order in list(self.store.active_orders()):
                for shipment in order.shipments:
                    if shipment.refunded or shipment.accepted_at or shipment.carrier.upper() != "USPS":
                        continue
                    try:
                        status = await self._async_track_usps(shipment.tracking_number)
                    except (BridgeError, aiohttp.ClientError) as err:
                        order.exception = f"USPS tracking unavailable: {err}"
                        continue
                    shipment.status = status
                    if _is_accepted(status):
                        shipment.accepted_at = utcnow()
                        order.add_note("USPS", f"USPS accepted {shipment.tracking_number}")
                        changed = True
                if order.stage == "awaiting_usps" and order.all_active_shipments_accepted():
                    order.move_to("done", "USPS", "All active USPS labels accepted", automated=True)
                    try:
                        await self.bridge.async_complete_order(order.order_id, order.notes[-1]["message"])
                        self.bridge_connected = True
                        order.completion_synced = True
                        await self.async_notify("Order shipped", f"Order #{order.order_number} is now complete.")
                        self.hass.bus.async_fire(f"{DOMAIN}_order_shipped", {"order_id": order.order_id, "order_number": order.order_number})
                    except BridgeError as err:
                        order.blocked = True
                        order.exception = f"WooCommerce completion sync failed: {err}"
                    changed = True
                elif self._is_late(order):
                    order.blocked = True
                    order.exception = "USPS has not reported acceptance within the configured threshold"
                    order.add_note("Cubecraft", order.exception)
                    await self.async_notify("USPS acceptance overdue", f"Order #{order.order_number} needs review.")
                    self.hass.bus.async_fire(f"{DOMAIN}_exception", {"order_id": order.order_id, "reason": "usps_acceptance_overdue"})
                    changed = True
                await self.store.async_upsert(order)
        if changed:
            async_dispatcher_send(self.hass, SIGNAL_UPDATED)

    def _is_late(self, order: Order) -> bool:
        if order.stage != "awaiting_usps" or order.all_active_shipments_accepted() or order.blocked:
            return False
        dates = [shipment.ship_date for shipment in order.shipments if shipment.ship_date and not shipment.refunded]
        if not dates:
            return False
        threshold = self.entry.options.get(CONF_ESCALATION_HOURS, DEFAULT_ESCALATION_HOURS)
        latest = max(_parse_date(value) for value in dates)
        return datetime.now(timezone.utc) >= latest + timedelta(hours=int(threshold))

    async def _async_track_usps(self, tracking_number: str) -> str:
        token = await self._async_usps_token()
        url = self.entry.options.get(CONF_USPS_TRACKING_URL, DEFAULT_USPS_TRACKING_URL).format(tracking_number=tracking_number)
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        async with async_get_clientsession(self.hass).get(url, headers=headers, timeout=20) as response:
            if response.status >= 300:
                raise BridgeError(f"USPS HTTP {response.status}")
            payload = await response.json()
        return _tracking_status(payload)

    async def _async_usps_token(self) -> str:
        if self._usps_token and self._usps_token_expires > datetime.now(timezone.utc) + timedelta(minutes=1):
            return self._usps_token
        values = self.entry.data
        async with async_get_clientsession(self.hass).post(
            "https://api.usps.com/oauth2/v3/token",
            data={"grant_type": "client_credentials", "client_id": values[CONF_USPS_CLIENT_ID], "client_secret": values[CONF_USPS_CLIENT_SECRET]},
            timeout=20,
        ) as response:
            if response.status >= 300:
                raise BridgeError(f"USPS authentication HTTP {response.status}")
            payload = await response.json()
        self._usps_token = payload["access_token"]
        self._usps_token_expires = datetime.now(timezone.utc) + timedelta(seconds=int(payload.get("expires_in", 900)))
        return self._usps_token

    async def async_notify(self, title: str, message: str) -> None:
        service = self.entry.options.get(CONF_NOTIFY_SERVICE)
        if not service or "." not in service:
            return
        domain, name = service.split(".", 1)
        await self.hass.services.async_call(domain, name, {"title": title, "message": message}, blocking=False)


def _shipping_method(data: dict[str, Any]) -> str | None:
    methods = data.get("shipping_lines") or []
    return ", ".join(item.get("method_title", "") for item in methods if item.get("method_title")) or None


def _parse_date(value: str) -> datetime:
    value = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
