"""Persistent order store with idempotent event handling."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION
from .models import Order


class OrderStore:
    """Persist order records and a bounded event de-duplication ledger."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
        self.orders: dict[int, Order] = {}
        self.event_ids: dict[str, str] = {}

    async def async_load(self) -> None:
        data = await self._store.async_load() or {}
        self.orders = {int(key): Order.from_dict(value) for key, value in data.get("orders", {}).items()}
        self.event_ids = data.get("event_ids", {})
        self._purge()

    def has_event(self, event_id: str) -> bool:
        return event_id in self.event_ids

    async def async_record_event(self, event_id: str) -> None:
        self.event_ids[event_id] = datetime.now(timezone.utc).isoformat()
        self._purge()
        await self.async_save()

    async def async_save(self) -> None:
        self._purge()
        await self._store.async_save({
            "orders": {str(key): value.to_dict() for key, value in self.orders.items()},
            "event_ids": self.event_ids,
        })

    async def async_upsert(self, order: Order) -> None:
        self.orders[order.order_id] = order
        await self.async_save()

    def get(self, order_id: int) -> Order:
        try:
            return self.orders[order_id]
        except KeyError as err:
            raise ValueError(f"Unknown Cubecraft order {order_id}") from err

    def active_orders(self) -> Iterable[Order]:
        return (order for order in self.orders.values() if order.stage != "done")

    def _purge(self) -> None:
        now = datetime.now(timezone.utc)
        event_cutoff = now - timedelta(days=7)
        self.event_ids = {
            key: value for key, value in self.event_ids.items()
            if _parse_time(value) >= event_cutoff
        }
        done_cutoff = now - timedelta(days=90)
        self.orders = {
            key: order for key, order in self.orders.items()
            if not order.done_at or _parse_time(order.done_at) >= done_cutoff
        }


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
