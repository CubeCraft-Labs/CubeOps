"""UI configuration for Cubecraft Production."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import OptionsFlowWithReload
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_BRIDGE_URL,
    CONF_ESCALATION_HOURS,
    CONF_NOTIFY_SERVICE,
    CONF_POLL_MINUTES,
    CONF_SHARED_SECRET,
    CONF_USPS_CLIENT_ID,
    CONF_USPS_CLIENT_SECRET,
    CONF_USPS_TOKEN_URL,
    CONF_USPS_TRACKING_URL,
    DEFAULT_ESCALATION_HOURS,
    DEFAULT_POLL_MINUTES,
    DEFAULT_USPS_TOKEN_URL,
    DEFAULT_USPS_TRACKING_URL,
    DOMAIN,
)

# Masked inputs. This matters more than it used to: async_step_reconfigure
# prefills the form from the existing entry, so a bare `str` would render the
# live shared secret and USPS secret in clear text every time the dialog is
# opened. The frontend still offers a reveal toggle when someone needs to check
# a value.
_SECRET = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))

DATA_SCHEMA = vol.Schema({
    # The USPS client ID is an identifier rather than a credential, so it stays
    # visible — it is useful to be able to read it back at a glance.
    vol.Required(CONF_BRIDGE_URL): TextSelector(
        TextSelectorConfig(type=TextSelectorType.URL)
    ),
    vol.Required(CONF_SHARED_SECRET): _SECRET,
    vol.Required(CONF_USPS_CLIENT_ID): str,
    vol.Required(CONF_USPS_CLIENT_SECRET): _SECRET,
})
# OPTIONS_SCHEMA deliberately keeps plain `str` for its two URLs: they are
# templates containing {tracking_number}, which an input[type=url] rejects.
OPTIONS_SCHEMA = vol.Schema({
    vol.Required(CONF_NOTIFY_SERVICE, default="notify.events"): str,
    vol.Required(CONF_POLL_MINUTES, default=DEFAULT_POLL_MINUTES): vol.All(vol.Coerce(int), vol.Range(min=5, max=1440)),
    vol.Required(CONF_ESCALATION_HOURS, default=DEFAULT_ESCALATION_HOURS): vol.All(vol.Coerce(int), vol.Range(min=1, max=720)),
    vol.Required(CONF_USPS_TRACKING_URL, default=DEFAULT_USPS_TRACKING_URL): str,
    vol.Required(CONF_USPS_TOKEN_URL, default=DEFAULT_USPS_TOKEN_URL): str,
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
                    CONF_USPS_TOKEN_URL: DEFAULT_USPS_TOKEN_URL,
                })
        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

    # The bridge URL, shared secret and USPS credentials live in entry.data,
    # which OptionsFlow below does not cover — it only edits entry.options.
    # Without this step a typo in the bridge URL can only be corrected by
    # deleting and re-adding the integration, re-entering all four values.
    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input:
            unique_id = user_input[CONF_BRIDGE_URL].rstrip("/")
            if len(user_input[CONF_SHARED_SECRET]) < 32:
                errors[CONF_SHARED_SECRET] = "weak_secret"
            elif any(
                other.entry_id != entry.entry_id and other.unique_id == unique_id
                for other in self._async_current_entries()
            ):
                errors[CONF_BRIDGE_URL] = "already_configured"
            else:
                # The unique id is derived from the bridge URL in
                # async_step_user, so it has to move with it or the entry keeps
                # the old identity and a later re-add of the real URL aborts.
                return self.async_update_reload_and_abort(
                    entry, unique_id=unique_id, data_updates=user_input
                )
        # Prefill from the existing entry so only the field being corrected has
        # to be touched; on an error, keep what was just typed instead.
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA, {**entry.data, **(user_input or {})}
            ),
            errors=errors,
        )

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
            CONF_USPS_TOKEN_URL: DEFAULT_USPS_TOKEN_URL,
        }, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(OPTIONS_SCHEMA, defaults),
        )
