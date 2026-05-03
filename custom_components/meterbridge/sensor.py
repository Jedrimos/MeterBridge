"""Sensor platform for MeterBridge."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_GROUPS, DOMAIN
from .coordinator import MeterBridgeCoordinator

_DEVICE_CLASS_MAP: dict[str, SensorDeviceClass | None] = {
    "power": SensorDeviceClass.POWER,
    "voltage": SensorDeviceClass.VOLTAGE,
    "current": SensorDeviceClass.CURRENT,
    "energy": SensorDeviceClass.ENERGY,
    "frequency": SensorDeviceClass.FREQUENCY,
    "power_factor": SensorDeviceClass.POWER_FACTOR,
}

_STATE_CLASS_MAP: dict[str, SensorStateClass | None] = {
    "measurement": SensorStateClass.MEASUREMENT,
    "total_increasing": SensorStateClass.TOTAL_INCREASING,
    "total": SensorStateClass.TOTAL,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: MeterBridgeCoordinator = entry_data["coordinator"]
    profile: dict = entry_data["profile"]

    active_groups: list[str] = entry.options.get(
        CONF_GROUPS, entry.data.get(CONF_GROUPS, [])
    )

    entities = [
        MeterBridgeSensor(coordinator, entry, profile, reg)
        for reg in profile.get("registers", [])
        if reg["group"] in active_groups
    ]
    async_add_entities(entities)


class MeterBridgeSensor(CoordinatorEntity[MeterBridgeCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: MeterBridgeCoordinator,
        entry: ConfigEntry,
        profile: dict,
        register: dict,
    ) -> None:
        super().__init__(coordinator)
        self._register = register
        self._attr_unique_id = f"{entry.entry_id}_{register['id']}"
        self._attr_name = register["name"]
        self._attr_native_unit_of_measurement = register.get("unit") or None
        self._attr_icon = register.get("icon")
        self._attr_device_class = _DEVICE_CLASS_MAP.get(register.get("device_class", ""))
        self._attr_state_class = _STATE_CLASS_MAP.get(register.get("state_class", ""))
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=profile["name"],
            manufacturer=profile.get("manufacturer"),
            model=profile.get("model"),
        )

    @property
    def native_value(self) -> float | int | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self._register["id"])
