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

_LOGGER = logging.getLogger(__name__)


def _group_field(group_id: str) -> str:
    return f"group_{group_id}"


def _build_sensor_schema(available_groups: list[str], selected: list[str]) -> vol.Schema:
    fields: dict = {}
    for g in available_groups:
        fields[vol.Optional(_group_field(g), default=(g in selected))] = bool
    return vol.Schema(fields)


def _connection_schema(profile: dict, defaults: dict | None = None) -> vol.Schema:
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=d.get(CONF_HOST, "")): str,
            vol.Required(CONF_PORT, default=d.get(CONF_PORT, profile.get("default_port", DEFAULT_PORT))): int,
            vol.Required(CONF_SLAVE_ID, default=d.get(CONF_SLAVE_ID, profile.get("default_slave_id", DEFAULT_SLAVE_ID))): int,
            vol.Required(CONF_POLL_INTERVAL, default=d.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)): int,
        }
    )


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
            data_schema=vol.Schema({vol.Required(CONF_DEVICE_ID): vol.In(device_options)}),
        )

    # ------------------------------------------------------------------
    # Step 2 – menu: manual or discover
    # ------------------------------------------------------------------
    async def async_step_connection(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return self.async_show_menu(
            step_id="connection",
            menu_options=["manual", "discover"],
        )

    # ------------------------------------------------------------------
    # Step 2a – manual IP entry
    # ------------------------------------------------------------------
    async def async_step_manual(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        profile = self._profiles[self._data[CONF_DEVICE_ID]]

        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_sensors()

        return self.async_show_form(
            step_id="manual",
            data_schema=_connection_schema(profile),
        )

    # ------------------------------------------------------------------
    # Step 2b – network discovery
    # ------------------------------------------------------------------
    async def async_step_discover(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        from .discovery import scan_modbus_hosts  # noqa: PLC0415

        profile = self._profiles[self._data[CONF_DEVICE_ID]]
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)
            self._data.pop("_discovered_hosts", None)
            return await self.async_step_sensors()

        # Run scan once; cache result so Back doesn't re-scan
        if "_discovered_hosts" not in self._data:
            found = await scan_modbus_hosts(self.hass)
            self._data["_discovered_hosts"] = found
        else:
            found = self._data["_discovered_hosts"]

        if not found:
            errors["base"] = "no_devices_found"
            # Fall back to a free-text host field so the user isn't stuck
            return self.async_show_form(
                step_id="discover",
                data_schema=_connection_schema(profile),
                errors=errors,
            )

        host_options = {h: h for h in found}
        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): vol.In(host_options),
                vol.Required(CONF_PORT, default=profile.get("default_port", DEFAULT_PORT)): int,
                vol.Required(CONF_SLAVE_ID, default=profile.get("default_slave_id", DEFAULT_SLAVE_ID)): int,
                vol.Required(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): int,
            }
        )
        return self.async_show_form(
            step_id="discover",
            data_schema=schema,
            errors=errors,
            description_placeholders={"count": str(len(found))},
        )

    # ------------------------------------------------------------------
    # Step 3 – sensor group selection
    # ------------------------------------------------------------------
    async def async_step_sensors(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        profile = self._profiles[self._data[CONF_DEVICE_ID]]
        available_groups = _available_groups(profile)
        errors: dict[str, str] = {}
        selected_in_form = self._data.get("_selected_groups", ["basic"])

        if user_input is not None:
            selected = [g for g in available_groups if user_input.get(_group_field(g))]
            self._data["_selected_groups"] = selected
            selected_in_form = selected

            if not selected:
                errors["base"] = "no_groups_selected"
            else:
                self._data[CONF_GROUPS] = selected
                self._data.pop("_selected_groups", None)
                await self.async_set_unique_id(
                    f"{self._data[CONF_HOST]}:{self._data[CONF_PORT]}:{self._data[CONF_SLAVE_ID]}"
                )
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=profile["name"], data=self._data)

        return self.async_show_form(
            step_id="sensors",
            data_schema=_build_sensor_schema(available_groups, selected_in_form),
            errors=errors,
            description_placeholders={"device_name": profile["name"]},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> MeterBridgeOptionsFlow:
        return MeterBridgeOptionsFlow()


# ------------------------------------------------------------------
# Options flow
# ------------------------------------------------------------------
class MeterBridgeOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        profiles: dict[str, dict] = await self.hass.async_add_executor_job(load_device_profiles)
        profile = profiles.get(self.config_entry.data[CONF_DEVICE_ID], {})
        available_groups = _available_groups(profile)
        current_groups: list[str] = self.config_entry.options.get(
            CONF_GROUPS, self.config_entry.data.get(CONF_GROUPS, ["basic"])
        )
        current_interval: int = self.config_entry.options.get(
            CONF_POLL_INTERVAL,
            self.config_entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        )

        if user_input is not None:
            selected = [g for g in available_groups if user_input.get(_group_field(g))]
            return self.async_create_entry(
                title="",
                data={
                    CONF_GROUPS: selected,
                    CONF_POLL_INTERVAL: user_input.get(CONF_POLL_INTERVAL, current_interval),
                },
            )

        schema_fields: dict = {vol.Required(CONF_POLL_INTERVAL, default=current_interval): int}
        for g in available_groups:
            schema_fields[vol.Optional(_group_field(g), default=(g in current_groups))] = bool

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema_fields),
        )


def _available_groups(profile: dict) -> list[str]:
    seen: set[str] = {r["group"] for r in profile.get("registers", [])}
    return [g for g in REGISTER_GROUPS if g in seen]
