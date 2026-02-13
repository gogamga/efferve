"""GL.iNet remote monitor mode sniffer via SSH + tcpdump.

Connects to a GL.iNet router via SSH, creates a monitor mode interface,
runs tcpdump to capture probe requests, and streams pcap output back
for local parsing with scapy.
"""

import asyncio
import logging
import re
import struct
from collections.abc import Callable
from datetime import UTC, datetime

from efferve.sniffer.base import BaseSniffer, BeaconEvent

logger = logging.getLogger(__name__)

_VALID_INTERFACE_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_interface_name(name: str) -> str:
    """Validate WiFi interface name to prevent command injection."""
    if not name or len(name) > 15:
        raise ValueError(f"Invalid interface name: {name!r}")
    if not _VALID_INTERFACE_RE.match(name):
        raise ValueError(f"Interface name contains invalid characters: {name!r}")
    return name

# Pcap global header is 24 bytes; per-packet record header is 16 bytes.
_PCAP_GLOBAL_HEADER_LEN = 24
_PCAP_RECORD_HEADER_LEN = 16


class GlinetSniffer(BaseSniffer):
    """Captures WiFi probe requests from a GL.iNet router via SSH tcpdump."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        wifi_interface: str = "wlan0",
        monitor_interface: str = "wlan0mon",
        poll_interval: int = 30,
    ) -> None:
        self.host = host
        self.username = username
        self.password = password
        self.wifi_interface = _validate_interface_name(wifi_interface)
        self.monitor_interface = _validate_interface_name(monitor_interface)
        self.poll_interval = poll_interval
        self._callbacks: list[Callable[[BeaconEvent], None]] = []
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        logger.info("Starting GL.iNet sniffer on %s", self.host)
        self._running = True
        self._task = asyncio.create_task(self._capture_loop())

    async def stop(self) -> None:
        logger.info("Stopping GL.iNet sniffer")
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def on_event(self, callback: Callable[[BeaconEvent], None]) -> None:
        self._callbacks.append(callback)

    async def _setup_monitor_interface(self, conn) -> bool:  # type: ignore[no-untyped-def]
        """Create monitor mode interface on the remote device."""
        try:
            result = await conn.run(
                f"iw dev {self.monitor_interface} info", check=False
            )
            if result.exit_status == 0:
                logger.info("Monitor interface %s already exists", self.monitor_interface)
                return True

            logger.info("Creating monitor interface %s", self.monitor_interface)
            await conn.run(
                f"iw dev {self.wifi_interface} interface add "
                f"{self.monitor_interface} type monitor",
                check=True,
            )
            await conn.run(
                f"ip link set {self.monitor_interface} up", check=True
            )
            logger.info("Monitor interface %s active", self.monitor_interface)
            return True
        except Exception:
            logger.exception("Failed to setup monitor interface")
            return False

    async def _cleanup_monitor_interface(self, conn) -> None:  # type: ignore[no-untyped-def]
        """Remove monitor mode interface."""
        try:
            await conn.run(
                f"ip link set {self.monitor_interface} down", check=False
            )
            await conn.run(
                f"iw dev {self.monitor_interface} del", check=False
            )
            logger.info("Monitor interface %s removed", self.monitor_interface)
        except Exception:
            logger.exception("Failed to cleanup monitor interface")

    async def _capture_loop(self) -> None:
        """Main loop: SSH → monitor setup → tcpdump → parse packets."""
        try:
            import asyncssh
        except ImportError:
            logger.error("asyncssh not installed — cannot use GL.iNet sniffer")
            return

        while self._running:
            try:
                async with asyncssh.connect(
                    self.host,
                    username=self.username,
                    password=self.password,
                    # TODO: Use known_hosts file for production deployments.
                    # known_hosts=None disables host key verification (MITM risk).
                    known_hosts=None,
                ) as conn:
                    logger.info("SSH connected to %s", self.host)

                    if not await self._setup_monitor_interface(conn):
                        logger.error("Monitor interface setup failed, retrying")
                        await asyncio.sleep(self.poll_interval)
                        continue

                    tcpdump_cmd = (
                        f"tcpdump -i {self.monitor_interface} -U -w - "
                        f"'type mgt subtype probe-req'"
                    )

                    async with conn.create_process(tcpdump_cmd) as process:
                        logger.info("tcpdump streaming on %s", self.monitor_interface)
                        stdout = process.stdout

                        # Discard pcap global header
                        await stdout.readexactly(_PCAP_GLOBAL_HEADER_LEN)  # type: ignore[union-attr]

                        while self._running:
                            try:
                                await self._read_and_process_packet(stdout)  # type: ignore[arg-type]
                            except asyncio.IncompleteReadError:
                                logger.warning("tcpdump stream ended")
                                break
                            except Exception:
                                logger.debug("Packet parse error", exc_info=True)

                    if not self._running:
                        await self._cleanup_monitor_interface(conn)

            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "GL.iNet capture error, reconnecting in %ds", self.poll_interval
                )
                await asyncio.sleep(self.poll_interval)

    async def _read_and_process_packet(self, stream) -> None:  # type: ignore[no-untyped-def]
        """Read one pcap record from the stream and emit a BeaconEvent."""
        record_header = await stream.readexactly(_PCAP_RECORD_HEADER_LEN)
        _ts_sec, _ts_usec, caplen, _wirelen = struct.unpack("=IIII", record_header)

        packet_data = await stream.readexactly(caplen)

        try:
            from scapy.all import Dot11Elt, Dot11ProbeReq, RadioTap

            pkt = RadioTap(packet_data)

            if not pkt.haslayer(Dot11ProbeReq):
                return

            mac = pkt.addr2
            if not mac:
                return

            ssid = None
            if pkt.haslayer(Dot11Elt) and pkt[Dot11Elt].ID == 0:
                raw_ssid = pkt[Dot11Elt].info
                if raw_ssid:
                    ssid = raw_ssid.decode("utf-8", errors="ignore") or None

            signal = (
                pkt[RadioTap].dBm_AntSignal if pkt.haslayer(RadioTap) else -100
            )

            event = BeaconEvent(
                mac_address=mac.upper(),
                signal_strength=signal,
                ssid=ssid,
                timestamp=datetime.now(UTC),
                source="glinet",
            )
            for cb in self._callbacks:
                cb(event)

        except ImportError:
            logger.error("scapy not installed — cannot parse packets")
            raise
