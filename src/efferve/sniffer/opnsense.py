"""OPNsense supplementary sniffer via REST API.

Polls DHCP leases and ARP tables to enrich device data with
hostnames and catch wired devices that Ruckus cannot see.
Uses HTTP basic auth with API key/secret.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from efferve.sniffer.base import BaseSniffer, BeaconEvent

logger = logging.getLogger(__name__)


class OpnsenseSniffer(BaseSniffer):
    """Polls OPNsense DHCP leases for device presence."""

    def __init__(
        self,
        url: str,
        api_key: str,
        api_secret: str,
        poll_interval: int = 30,
    ) -> None:
        # OPNsense requires HTTPS; upgrade if user entered http://
        if url.startswith("http://"):
            url = "https://" + url[7:]
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.poll_interval = poll_interval
        self._callbacks: list[Callable[[BeaconEvent], None]] = []
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        logger.info("Starting OPNsense sniffer polling %s", self.url)
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        logger.info("Stopping OPNsense sniffer")
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def on_event(self, callback: Callable[[BeaconEvent], None]) -> None:
        self._callbacks.append(callback)

    async def _poll_loop(self) -> None:
        auth = httpx.BasicAuth(self.api_key, self.api_secret)

        async with httpx.AsyncClient(
            base_url=self.url,
            auth=auth,
            # TODO: Support custom CA cert for self-signed OPNsense certificates.
            # verify=False disables SSL verification (MITM risk).
            verify=False,
            timeout=15.0,
        ) as client:
            while self._running:
                try:
                    resp = await client.get("/api/dhcpv4/leases/search_lease")
                    resp.raise_for_status()
                    data = resp.json()

                    now = datetime.now(UTC)
                    rows = data.get("rows", [])

                    for lease in rows:
                        mac = lease.get("mac", "")
                        if not mac:
                            continue

                        # Only emit for active leases
                        if lease.get("state") not in ("active", ""):
                            continue

                        event = BeaconEvent(
                            mac_address=mac.upper(),
                            signal_strength=0,  # sentinel: no RF data from OPNsense
                            ssid=None,
                            timestamp=now,
                            source="opnsense",
                        )
                        for cb in self._callbacks:
                            cb(event)

                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("OPNsense poll error")

                await asyncio.sleep(self.poll_interval)
