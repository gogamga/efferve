"""Ruckus Unleashed WiFi sniffer via aioruckus.

Primary wireless presence source — polls active clients from the
Ruckus Unleashed master AP at a configurable interval.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime

from efferve.sniffer.base import BaseSniffer, BeaconEvent

logger = logging.getLogger(__name__)


class RuckusSniffer(BaseSniffer):
    """Polls Ruckus Unleashed for active wireless clients."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        poll_interval: int = 30,
    ) -> None:
        self.host = host
        self.username = username
        self.password = password
        self.poll_interval = poll_interval
        self._callbacks: list[Callable[[BeaconEvent], None]] = []
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        logger.info("Starting Ruckus sniffer polling %s", self.host)
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())

    async def stop(self) -> None:
        logger.info("Stopping Ruckus sniffer")
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
        from aioruckus import AjaxSession

        while self._running:
            try:
                async with AjaxSession.async_create(
                    self.host, self.username, self.password
                ) as session:
                    while self._running:
                        clients = await session.api.get_active_clients()
                        now = datetime.now(UTC)

                        for client in clients:
                            mac = client.get("mac", "")
                            if not mac:
                                continue

                            event = BeaconEvent(
                                mac_address=mac.upper(),
                                signal_strength=int(client.get("signal", 0)),
                                ssid=client.get("ssid"),
                                timestamp=now,
                                source="ruckus",
                            )
                            for cb in self._callbacks:
                                cb(event)

                        await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Ruckus poll error, reconnecting in %ds", self.poll_interval)
                await asyncio.sleep(self.poll_interval)
