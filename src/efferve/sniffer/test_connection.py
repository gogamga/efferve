"""Connection test utilities for router/AP sniffer backends.

Used by the setup wizard to validate credentials and connectivity before
saving configuration.
"""

import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ConnectionResult:
    """Result of a connection test attempt."""

    success: bool
    message: str
    device_count: int | None = None


async def test_ruckus(host: str, username: str, password: str) -> ConnectionResult:
    """Test connection to a Ruckus Unleashed AP.

    Args:
        host: AP hostname or IP (e.g., "192.168.1.1")
        username: Admin username
        password: Admin password

    Returns:
        ConnectionResult with success status, message, and device count.
    """
    try:
        # Import here to avoid heavy dependency load unless needed
        from aioruckus import AjaxSession

        async with AjaxSession.async_create(host, username, password) as session:
            clients = await session.api.get_active_clients()
            count = len(clients)
            logger.info(f"Ruckus connection test successful: {count} active clients")
            return ConnectionResult(
                success=True,
                message=f"Connected — {count} active clients",
                device_count=count,
            )
    except Exception as e:
        logger.warning(f"Ruckus connection test failed: {e}")
        return ConnectionResult(success=False, message=str(e))


async def test_opnsense(url: str, api_key: str, api_secret: str) -> ConnectionResult:
    """Test connection to an OPNsense router API.

    Args:
        url: Base URL (e.g., "https://192.168.1.1")
        api_key: API key
        api_secret: API secret

    Returns:
        ConnectionResult with success status, message, and device count.
    """
    try:
        auth = httpx.BasicAuth(api_key, api_secret)
        async with httpx.AsyncClient(
            base_url=url, auth=auth, verify=False, timeout=10.0
        ) as client:
            resp = await client.get("/api/dhcpv4/leases/search_lease")
            resp.raise_for_status()
            data = resp.json()
            rows = data.get("rows", [])
            count = len(rows)
            logger.info(f"OPNsense connection test successful: {count} leases")
            return ConnectionResult(
                success=True,
                message=f"Connected — {count} DHCP leases",
                device_count=count,
            )
    except Exception as e:
        logger.warning(f"OPNsense connection test failed: {e}")
        return ConnectionResult(success=False, message=str(e))
