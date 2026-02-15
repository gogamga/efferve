"""Tests for the GL.iNet remote monitor sniffer."""

import asyncio
import struct
import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from efferve.sniffer.base import BeaconEvent
from efferve.sniffer.glinet import GlinetSniffer


def _make_sniffer() -> GlinetSniffer:
    return GlinetSniffer(
        host="192.168.1.47",
        username="root",
        password="secret",
        wifi_interface="wlan0",
        monitor_interface="wlan0mon",
        poll_interval=1,
    )


@pytest.fixture(autouse=True)
def _mock_asyncssh():
    """Inject a mock asyncssh module."""
    mock_mod = MagicMock()
    sys.modules["asyncssh"] = mock_mod
    yield mock_mod
    sys.modules.pop("asyncssh", None)


@pytest.fixture(autouse=True)
def _mock_scapy():
    """Inject a mock scapy.all module."""
    mock_mod = MagicMock()
    sys.modules["scapy"] = mock_mod
    sys.modules["scapy.all"] = mock_mod
    yield mock_mod
    sys.modules.pop("scapy.all", None)
    sys.modules.pop("scapy", None)


def _make_pcap_record(caplen: int = 64) -> bytes:
    """Build a fake pcap record header + zero-filled packet data."""
    header = struct.pack("=IIII", 0, 0, caplen, caplen)
    return header + b"\x00" * caplen


class TestMonitorInterfaceSetup:
    @pytest.mark.asyncio
    async def test_creates_if_missing(self):
        sniffer = _make_sniffer()
        conn = AsyncMock()
        conn.run = AsyncMock(
            side_effect=[
                Mock(exit_status=1),  # iw dev info → not found
                Mock(exit_status=0),  # iw dev add → success
                Mock(exit_status=0),  # ip link set up → success
            ]
        )
        result = await sniffer._setup_monitor_interface(conn)
        assert result is True
        assert conn.run.call_count == 3

    @pytest.mark.asyncio
    async def test_reuses_existing(self):
        sniffer = _make_sniffer()
        conn = AsyncMock()
        conn.run = AsyncMock(return_value=Mock(exit_status=0))
        result = await sniffer._setup_monitor_interface(conn)
        assert result is True
        assert conn.run.call_count == 1

    @pytest.mark.asyncio
    async def test_returns_false_on_failure(self):
        sniffer = _make_sniffer()
        conn = AsyncMock()
        conn.run = AsyncMock(
            side_effect=[
                Mock(exit_status=1),  # not found
                Exception("iw failed"),  # create fails
            ]
        )
        result = await sniffer._setup_monitor_interface(conn)
        assert result is False


class TestCleanupMonitorInterface:
    @pytest.mark.asyncio
    async def test_cleanup_calls(self):
        sniffer = _make_sniffer()
        conn = AsyncMock()
        conn.run = AsyncMock(return_value=Mock(exit_status=0))
        await sniffer._cleanup_monitor_interface(conn)
        assert conn.run.call_count == 2


class TestPacketParsing:
    @pytest.mark.asyncio
    async def test_emits_beacon_event(self, _mock_scapy):
        sniffer = _make_sniffer()
        received: list[BeaconEvent] = []
        sniffer.on_event(received.append)

        # Configure scapy mock: RadioTap() returns a packet with probe request
        mock_pkt = MagicMock()
        mock_pkt.haslayer.return_value = True
        mock_pkt.addr2 = "aa:bb:cc:dd:ee:ff"

        mock_elt = MagicMock()
        mock_elt.ID = 0
        mock_elt.info = b"TestSSID"

        mock_radiotap = MagicMock()
        mock_radiotap.dBm_AntSignal = -45

        def getitem(layer):
            name = getattr(layer, "_mock_name", "") or str(layer)
            if "Dot11Elt" in name:
                return mock_elt
            if "RadioTap" in name:
                return mock_radiotap
            return MagicMock()

        mock_pkt.__getitem__ = MagicMock(side_effect=getitem)
        _mock_scapy.RadioTap.return_value = mock_pkt

        # Build fake pcap record
        record = _make_pcap_record(64)
        stream = AsyncMock()
        stream.readexactly = AsyncMock(
            side_effect=[
                record[:16],  # record header
                record[16:],  # packet data
            ]
        )

        await sniffer._read_and_process_packet(stream)

        assert len(received) == 1
        assert received[0].mac_address == "AA:BB:CC:DD:EE:FF"
        assert received[0].signal_strength == -45
        assert received[0].source == "glinet"

    @pytest.mark.asyncio
    async def test_skips_non_probe_request(self, _mock_scapy):
        sniffer = _make_sniffer()
        received: list[BeaconEvent] = []
        sniffer.on_event(received.append)

        mock_pkt = MagicMock()
        # haslayer(Dot11ProbeReq) returns False
        mock_pkt.haslayer.return_value = False
        _mock_scapy.RadioTap.return_value = mock_pkt

        record = _make_pcap_record(64)
        stream = AsyncMock()
        stream.readexactly = AsyncMock(side_effect=[record[:16], record[16:]])

        await sniffer._read_and_process_packet(stream)
        assert len(received) == 0


class TestCaptureLoopReconnection:
    @pytest.mark.asyncio
    async def test_reconnects_on_ssh_failure(self, _mock_asyncssh):
        sniffer = _make_sniffer()
        call_count = 0

        def mock_connect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("refused")
            # Second call — stop the loop
            sniffer._running = False
            raise ConnectionError("stop")

        _mock_asyncssh.connect = mock_connect
        sniffer._running = True

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await sniffer._capture_loop()
        assert call_count == 2  # Retried after failure


class TestGracefulDegradation:
    @pytest.mark.asyncio
    async def test_stream_end_triggers_reconnect(self, _mock_asyncssh):
        """IncompleteReadError in packet read should break inner loop."""
        sniffer = _make_sniffer()

        conn = AsyncMock()
        conn.run = AsyncMock(return_value=Mock(exit_status=0))

        process = AsyncMock()
        stdout = AsyncMock()
        # First call: global header; second: IncompleteReadError
        stdout.readexactly = AsyncMock(
            side_effect=[
                b"\x00" * 24,  # pcap global header
                asyncio.IncompleteReadError(b"", 16),  # stream ends
            ]
        )
        process.stdout = stdout
        process.__aenter__ = AsyncMock(return_value=process)
        process.__aexit__ = AsyncMock(return_value=False)
        conn.create_process = MagicMock(return_value=process)

        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=conn)
        ctx.__aexit__ = AsyncMock(return_value=False)

        connect_count = 0

        def mock_connect(*args, **kwargs):
            nonlocal connect_count
            connect_count += 1
            if connect_count == 1:
                return ctx
            sniffer._running = False
            raise ConnectionError("stop")

        _mock_asyncssh.connect = mock_connect
        sniffer._running = True

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await sniffer._capture_loop()
        assert connect_count == 2  # Reconnected after stream ended
