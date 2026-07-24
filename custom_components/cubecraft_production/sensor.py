"""Queue summary sensors."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN
from .coordinator import SIGNAL_UPDATED


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data.coordinator
    async_add_entities([
        QueueCountSensor(coordinator, entry.entry_id),
        AwaitingUspsSensor(coordinator, entry.entry_id),
        ExceptionCountSensor(coordinator, entry.entry_id),
        RecentOrdersSensor(coordinator, entry.entry_id),
    ])


class _BaseSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry_id: str) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_{self.key}"

    async def async_added_to_hass(self):
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_UPDATED, self.async_write_ha_state))


class QueueCountSensor(_BaseSensor):
    _attr_name = "Production queue"
    _attr_icon = "mdi:format-list-numbered"
    key = "queue"

    @property
    def native_value(self):
        return sum(1 for order in self.coordinator.store.active_orders() if not order.blocked)

    @property
    def extra_state_attributes(self):
        return {"stages": {stage: sum(1 for order in self.coordinator.store.orders.values() if order.stage == stage) for stage in ("queued", "printing", "qa_assembly", "packed", "awaiting_usps")}}


class AwaitingUspsSensor(_BaseSensor):
    _attr_name = "Awaiting USPS"
    _attr_icon = "mdi:truck-clock"
    key = "awaiting_usps"

    @property
    def native_value(self):
        return sum(1 for order in self.coordinator.store.orders.values() if order.stage == "awaiting_usps" and not order.blocked)


class ExceptionCountSensor(_BaseSensor):
    _attr_name = "Production exceptions"
    _attr_icon = "mdi:alert-circle"
    key = "exceptions"

    @property
    def native_value(self):
        return sum(1 for order in self.coordinator.store.orders.values() if order.blocked)


class RecentOrdersSensor(_BaseSensor):
    _attr_name = "Recent production orders"
    _attr_icon = "mdi:history"
    key = "recent_orders"

    @property
    def native_value(self):
        return min(len(self.coordinator.store.orders), 10)

    @property
    def extra_state_attributes(self):
        recent = sorted(self.coordinator.store.orders.values(), key=lambda item: item.updated_at, reverse=True)[:10]
        return {"orders": [{"order_id": item.order_id, "order_number": item.order_number, "stage": item.stage, "blocked": item.blocked} for item in recent]}
