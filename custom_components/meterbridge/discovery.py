"""Network discovery: scan local /24 subnet for open Modbus TCP ports."""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket

_LOGGER = logging.getLogger(__name__)
_SCAN_TIMEOUT = 0.4
_MAX_CONCURRENT = 80


def _local_ip() -> str:
    """Return the host's primary LAN IP address."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.254.254.254", 1))
            return s.getsockname()[0]
        except Exception:
            return "127.0.0.1"


async def _check_port(host: str, port: int, sem: asyncio.Semaphore) -> str | None:
    async with sem:
        try:
            _, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=_SCAN_TIMEOUT,
            )
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            return host
        except Exception:
            return None


async def scan_modbus_hosts(hass, port: int = 502) -> list[str]:
    """Scan the local /24 subnet and return hosts with the given port open."""
    local = await hass.async_add_executor_job(_local_ip)
    try:
        network = ipaddress.IPv4Network(f"{local}/24", strict=False)
    except ValueError:
        _LOGGER.warning("Cannot determine local subnet from %s", local)
        return []

    sem = asyncio.Semaphore(_MAX_CONCURRENT)
    tasks = [_check_port(str(ip), port, sem) for ip in network.hosts()]
    results = await asyncio.gather(*tasks)
    found = sorted(r for r in results if r is not None)
    _LOGGER.debug("Modbus scan on %s port %s: found %s", network, port, found)
    return found
