"""Integration health status."""

from homeassistant.components.binary_sensor import BinarySensorEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([BridgeHealthSensor(entry.runtime_data.coordinator, entry.entry_id)])


class BridgeHealthSensor(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Bridge connected"
    _attr_device_class = "connectivity"

    def __init__(self, coordinator, entry_id):
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry_id}_bridge_health"

    @property
    def is_on(self):
        return self.coordinator.bridge_connected
