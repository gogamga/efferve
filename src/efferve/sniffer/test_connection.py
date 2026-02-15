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
    # OPNsense requires HTTPS; upgrade if user entered http://
    if url.startswith("http://"):
        url = "https://" + url[7:]
    try:
        auth = httpx.BasicAuth(api_key, api_secret)
        async with httpx.AsyncClient(
            base_url=url,
            auth=auth,
            # TODO: Support custom CA cert for self-signed OPNsense certificates.
            # verify=False disables SSL verification (MITM risk).
            verify=False,
            timeout=10.0,
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


async def test_glinet(host: str, username: str, password: str) -> ConnectionResult:
    """Test SSH connection to a GL.iNet router.

    Args:
        host: Router hostname or IP (e.g., "192.168.1.47")
        username: SSH username (usually "root")
        password: SSH password

    Returns:
        ConnectionResult with success status and message.
    """
    try:
        import asyncssh

        async with asyncssh.connect(
            host,
            username=username,
            password=password,
            # TODO: Use known_hosts file for production deployments.
            # known_hosts=None disables host key verification (MITM risk).
            known_hosts=None,
            connect_timeout=10,
        ) as conn:
            result = await conn.run("iw dev", check=True)
            output = result.stdout or ""
            if "Interface" not in output:
                return ConnectionResult(
                    success=False, message="Connected but no WiFi interfaces found"
                )
            logger.info("GL.iNet connection test successful")
            return ConnectionResult(success=True, message="Connected — SSH access verified")
    except ImportError:
        return ConnectionResult(success=False, message="asyncssh library not installed")
    except Exception as e:
        logger.warning(f"GL.iNet connection test failed: {e}")
        return ConnectionResult(success=False, message=str(e))
