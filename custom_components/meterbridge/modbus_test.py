"""Lightweight TCP reachability test used by the config flow."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
_CONNECT_TIMEOUT = 5


async def async_test_connection(
    hass: HomeAssistant, host: str, port: int, slave_id: int
) -> bool:
    """Return True if the host:port is reachable via TCP.

    A plain TCP handshake is used intentionally: many Modbus devices (e.g.
    Kostal KSEM, TQ300) only allow a single Modbus connection at a time.
    If HA's built-in modbus integration already holds that slot, a full
    pymodbus connect() would be rejected even though the device is fine.
    A raw TCP connect just checks reachability without consuming a slot.
    """
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=_CONNECT_TIMEOUT,
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return True
    except Exception as exc:
        _LOGGER.debug("TCP reachability test failed for %s:%s – %s", host, port, exc)
        return False
