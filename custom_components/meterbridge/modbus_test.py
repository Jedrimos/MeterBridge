"""Lightweight Modbus connection test used by the config flow."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
_CONNECT_TIMEOUT = 5


async def async_test_connection(
    hass: HomeAssistant, host: str, port: int, slave_id: int
) -> bool:
    """Return True if a basic Modbus TCP connection can be established."""
    try:
        from pymodbus.client import AsyncModbusTcpClient  # noqa: PLC0415

        client = AsyncModbusTcpClient(host=host, port=port, timeout=_CONNECT_TIMEOUT)
        connected = await asyncio.wait_for(client.connect(), timeout=_CONNECT_TIMEOUT)
        if connected:
            await client.close()
        return bool(connected)
    except Exception as exc:
        _LOGGER.debug("Connection test failed for %s:%s – %s", host, port, exc)
        return False
