"""DataUpdateCoordinator for MeterBridge – polls Modbus registers."""
from __future__ import annotations

import logging
import struct
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_GROUPS,
    CONF_POLL_INTERVAL,
    CONF_SLAVE_ID,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_SLAVE_ID,
    DOMAIN,
    REGISTER_COUNT,
    REGISTER_TYPE_INPUT,
)

_LOGGER = logging.getLogger(__name__)


def _decode(registers: list[int], data_type: str) -> float | int:
    if data_type == "uint16":
        return registers[0]
    if data_type == "int16":
        return struct.unpack(">h", struct.pack(">H", registers[0]))[0]
    if data_type == "uint32":
        return (registers[0] << 16) | registers[1]
    if data_type == "int32":
        raw = (registers[0] << 16) | registers[1]
        return struct.unpack(">i", struct.pack(">I", raw))[0]
    if data_type == "float32":
        return struct.unpack(">f", struct.pack(">HH", registers[0], registers[1]))[0]
    raise ValueError(f"Unknown data_type: {data_type}")


class MeterBridgeCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, profile: dict
    ) -> None:
        self._entry = entry
        self._profile = profile
        self._client: Any = None

        poll_interval = entry.options.get(
            CONF_POLL_INTERVAL,
            entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=poll_interval),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _active_registers(self) -> list[dict]:
        groups: list[str] = self._entry.options.get(
            CONF_GROUPS, self._entry.data.get(CONF_GROUPS, [])
        )
        return [r for r in self._profile.get("registers", []) if r["group"] in groups]

    async def _get_client(self):
        from pymodbus.client import AsyncModbusTcpClient  # noqa: PLC0415

        if self._client is None or not self._client.connected:
            host = self._entry.data[CONF_HOST]
            port = self._entry.data[CONF_PORT]
            self._client = AsyncModbusTcpClient(host=host, port=port, timeout=10)
            connected = await self._client.connect()
            if not connected:
                self._client = None
                raise ConfigEntryNotReady(f"Cannot connect to {host}:{port}")
        return self._client

    async def _read_register(self, reg: dict) -> float | int | None:
        from pymodbus.exceptions import ModbusException  # noqa: PLC0415

        client = await self._get_client()
        slave_id: int = self._entry.data.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)
        address: int = reg["register"]
        data_type: str = reg["data_type"]
        count: int = REGISTER_COUNT.get(data_type, 1)

        try:
            if reg.get("register_type") == REGISTER_TYPE_INPUT:
                result = await client.read_input_registers(address, count, slave=slave_id)
            else:
                result = await client.read_holding_registers(address, count, slave=slave_id)

            if result.isError():
                _LOGGER.warning(
                    "Modbus error reading register %s (%s): %s",
                    reg["id"],
                    address,
                    result,
                )
                return None

            raw = _decode(result.registers, data_type)
            scale: float = reg.get("scale", 1)
            return round(raw * scale, 4) if scale != 1 else raw

        except ModbusException as exc:
            _LOGGER.warning("ModbusException for register %s: %s", reg["id"], exc)
            self._client = None
            return None

    # ------------------------------------------------------------------
    # DataUpdateCoordinator contract
    # ------------------------------------------------------------------
    async def _async_update_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        failed = 0
        registers = self._active_registers()

        for reg in registers:
            value = await self._read_register(reg)
            data[reg["id"]] = value
            if value is None:
                failed += 1

        if failed == len(registers) and registers:
            raise UpdateFailed("All Modbus reads failed – device unreachable")

        return data

    async def async_shutdown(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
