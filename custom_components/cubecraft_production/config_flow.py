"""UI configuration for Cubecraft Production."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import OptionsFlowWithReload
from homeassistant.core import callback

from .const import (
    CONF_BRIDGE_URL,
    CONF_ESCALATION_HOURS,
    CONF_NOTIFY_SERVICE,
    CONF_POLL_MINUTES,
    CONF_SHARED_SECRET,
    CONF_USPS_CLIENT_ID,
    CONF_USPS_CLIENT_SECRET,
    CONF_USPS_TRACKING_URL,
    DEFAULT_ESCALATION_HOURS,
    DEFAULT_POLL_MINUTES,
    DEFAULT_USPS_TRACKING_URL,
    DOMAIN,
)

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_BRIDGE_URL): str,
    vol.Required(CONF_SHARED_SECRET): str,
    vol.Required(CONF_USPS_CLIENT_ID): str,
    vol.Required(CONF_USPS_CLIENT_SECRET): str,
})
OPTIONS_SCHEMA = vol.Schema({
    vol.Required(CONF_NOTIFY_SERVICE, default="notify.events"): str,
    vol.Required(CONF_POLL_MINUTES, default=DEFAULT_POLL_MINUTES): vol.All(vol.Coerce(int), vol.Range(min=5, max=1440)),
    vol.Required(CONF_ESCALATION_HOURS, default=DEFAULT_ESCALATION_HOURS): vol.All(vol.Coerce(int), vol.Range(min=1, max=720)),
    vol.Required(CONF_USPS_TRACKING_URL, default=DEFAULT_USPS_TRACKING_URL): str,
})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input:
            if len(user_input[CONF_SHARED_SECRET]) < 32:
                errors[CONF_SHARED_SECRET] = "weak_secret"
            else:
                await self.async_set_unique_id(user_input[CONF_BRIDGE_URL].rstrip("/"))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Cubecraft Production", data=user_input, options={
                    CONF_NOTIFY_SERVICE: "notify.events",
                    CONF_POLL_MINUTES: DEFAULT_POLL_MINUTES,
                    CONF_ESCALATION_HOURS: DEFAULT_ESCALATION_HOURS,
                    CONF_USPS_TRACKING_URL: DEFAULT_USPS_TRACKING_URL,
                })
        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlow()


class OptionsFlow(OptionsFlowWithReload):

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        defaults = {**{
            CONF_NOTIFY_SERVICE: "notify.events",
            CONF_POLL_MINUTES: DEFAULT_POLL_MINUTES,
            CONF_ESCALATION_HOURS: DEFAULT_ESCALATION_HOURS,
            CONF_USPS_TRACKING_URL: DEFAULT_USPS_TRACKING_URL,
        }, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, defaults),
        )
