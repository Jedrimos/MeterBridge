"""MeterBridge – Modbus smart meter integration for Home Assistant."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from .const import DOMAIN
from .coordinator import MeterBridgeCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


def load_device_profiles() -> dict[str, dict]:
    """Load all device profiles from the devices/ directory."""
    devices_dir = Path(__file__).parent / "devices"
    profiles: dict[str, dict] = {}
    for path in sorted(devices_dir.glob("*.json")):
        try:
            with path.open(encoding="utf-8") as f:
                profile = json.load(f)
            profiles[profile["id"]] = profile
        except Exception as exc:
            _LOGGER.warning("Failed to load device profile %s: %s", path.name, exc)
    return profiles


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    profiles = await hass.async_add_executor_job(load_device_profiles)
    device_id = entry.data["device_id"]

    if device_id not in profiles:
        _LOGGER.error("Unknown device profile: %s", device_id)
        return False

    coordinator = MeterBridgeCoordinator(hass, entry, profiles[device_id])

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "profile": profiles[device_id],
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator: MeterBridgeCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    await coordinator.async_shutdown()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
