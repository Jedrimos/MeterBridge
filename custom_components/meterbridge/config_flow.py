"""Config flow for MeterBridge."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from . import load_device_profiles
from .const import (
    CONF_DEVICE_ID,
    CONF_GROUPS,
    CONF_POLL_INTERVAL,
    CONF_SLAVE_ID,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SLAVE_ID,
    DOMAIN,
    REGISTER_GROUPS,
)
from .modbus_test import async_test_connection

_LOGGER = logging.getLogger(__name__)


def _group_field(group_id: str) -> str:
    return f"group_{group_id}"


def _build_sensor_schema(available_groups: list[str], selected: list[str]) -> vol.Schema:
    fields: dict = {}
    for g in available_groups:
        fields[vol.Optional(_group_field(g), default=(g in selected))] = bool
    return vol.Schema(fields)


class MeterBridgeConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._profiles: dict[str, dict] = {}
        self._data: dict[str, Any] = {}

    async def _load_profiles(self) -> None:
        if not self._profiles:
            self._profiles = await self.hass.async_add_executor_job(load_device_profiles)

    # ------------------------------------------------------------------
    # Step 1 – device selection
    # ------------------------------------------------------------------
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        await self._load_profiles()

        if user_input is not None:
            self._data[CONF_DEVICE_ID] = user_input[CONF_DEVICE_ID]
            return await self.async_step_connection()

        device_options = {dev_id: dev["name"] for dev_id, dev in self._profiles.items()}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_DEVICE_ID): vol.In(device_options)}
            ),
        )

    # ------------------------------------------------------------------
    # Step 2 – connection settings
    # ------------------------------------------------------------------
    async def async_step_connection(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        profile = self._profiles[self._data[CONF_DEVICE_ID]]

        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_sensors()

        return self.async_show_form(
            step_id="connection",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(
                        CONF_PORT, default=profile.get("default_port", DEFAULT_PORT)
                    ): int,
                    vol.Required(
                        CONF_SLAVE_ID,
                        default=profile.get("default_slave_id", DEFAULT_SLAVE_ID),
                    ): int,
                    vol.Required(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): int,
                }
            ),
        )

    # ------------------------------------------------------------------
    # Step 3 – sensor group selection + connection test
    # ------------------------------------------------------------------
    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        profile = self._profiles[self._data[CONF_DEVICE_ID]]
        available_groups = _available_groups(profile)
        errors: dict[str, str] = {}

        if user_input is not None:
            selected = [g for g in available_groups if user_input.get(_group_field(g))]
            if not selected:
                errors["base"] = "no_groups_selected"
            else:
                ok = await async_test_connection(
                    self.hass,
                    self._data[CONF_HOST],
                    self._data[CONF_PORT],
                    self._data[CONF_SLAVE_ID],
                )
                if not ok:
                    errors["base"] = "cannot_connect"
                else:
                    self._data[CONF_GROUPS] = selected
                    await self.async_set_unique_id(
                        f"{self._data[CONF_HOST]}:{self._data[CONF_PORT]}:{self._data[CONF_SLAVE_ID]}"
                    )
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=profile["name"], data=self._data
                    )

        return self.async_show_form(
            step_id="sensors",
            data_schema=_build_sensor_schema(available_groups, ["basic"]),
            errors=errors,
            description_placeholders={"device_name": profile["name"]},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> MeterBridgeOptionsFlow:
        return MeterBridgeOptionsFlow(config_entry)


# ------------------------------------------------------------------
# Options flow – change sensor groups / poll interval after setup
# ------------------------------------------------------------------
class MeterBridgeOptionsFlow(OptionsFlow):
    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        profiles: dict[str, dict] = await self.hass.async_add_executor_job(
            load_device_profiles
        )
        profile = profiles.get(self._entry.data[CONF_DEVICE_ID], {})
        available_groups = _available_groups(profile)
        current_groups: list[str] = self._entry.options.get(
            CONF_GROUPS, self._entry.data.get(CONF_GROUPS, ["basic"])
        )
        current_interval: int = self._entry.options.get(
            CONF_POLL_INTERVAL, self._entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        )

        if user_input is not None:
            selected = [g for g in available_groups if user_input.get(_group_field(g))]
            new_interval = user_input.get(CONF_POLL_INTERVAL, current_interval)
            return self.async_create_entry(
                title="",
                data={CONF_GROUPS: selected, CONF_POLL_INTERVAL: new_interval},
            )

        schema_fields: dict = {
            vol.Required(CONF_POLL_INTERVAL, default=current_interval): int,
        }
        for g in available_groups:
            schema_fields[vol.Optional(_group_field(g), default=(g in current_groups))] = bool

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_fields),
        )


def _available_groups(profile: dict) -> list[str]:
    """Return group IDs that have at least one register in this profile."""
    seen: set[str] = {r["group"] for r in profile.get("registers", [])}
    return [g for g in REGISTER_GROUPS if g in seen]
