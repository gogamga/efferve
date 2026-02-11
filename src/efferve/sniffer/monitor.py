"""Monitor mode WiFi sniffer using scapy.

Requires NET_ADMIN + NET_RAW capabilities and a WiFi adapter in monitor mode.
"""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime

from efferve.sniffer.base import BaseSniffer, BeaconEvent

logger = logging.getLogger(__name__)


class MonitorSniffer(BaseSniffer):
    """Captures WiFi probe requests via monitor mode interface."""

    def __init__(self, interface: str) -> None:
        self.interface = interface
        self._callbacks: list[Callable[[BeaconEvent], None]] = []
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        logger.info("Starting monitor mode sniffer on %s", self.interface)
        self._running = True
        self._task = asyncio.create_task(self._capture_loop())

    async def stop(self) -> None:
        logger.info("Stopping monitor mode sniffer")
        self._running = False
        if self._task:
            self._task.cancel()

    def on_event(self, callback: Callable[[BeaconEvent], None]) -> None:
        self._callbacks.append(callback)

    async def _capture_loop(self) -> None:
        """Run scapy sniff in a thread to avoid blocking the event loop."""
        try:
            from scapy.all import AsyncSniffer, Dot11Elt, Dot11ProbeReq, RadioTap

            def _handle_packet(pkt) -> None:
                if pkt.haslayer(Dot11ProbeReq):
                    mac = pkt.addr2
                    if not mac:
                        return

                    ssid = None
                    if pkt.haslayer(Dot11Elt) and pkt[Dot11Elt].ID == 0:
                        raw_ssid = pkt[Dot11Elt].info
                        if raw_ssid:
                            ssid = raw_ssid.decode("utf-8", errors="ignore") or None

                    signal = pkt[RadioTap].dBm_AntSignal if pkt.haslayer(RadioTap) else -100

                    event = BeaconEvent(
                        mac_address=mac.upper(),
                        signal_strength=signal,
                        ssid=ssid,
                        timestamp=datetime.now(UTC),
                        source="monitor",
                    )
                    for cb in self._callbacks:
                        cb(event)

            sniffer = AsyncSniffer(
                iface=self.interface,
                prn=_handle_packet,
                store=False,
            )
            sniffer.start()

            while self._running:
                await asyncio.sleep(0.5)

            sniffer.stop()
        except ImportError:
            logger.error("scapy not available — cannot use monitor mode sniffer")
        except Exception:
            logger.exception("Monitor sniffer error")
