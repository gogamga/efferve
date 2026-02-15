"""Tests for the Ruckus Unleashed WiFi sniffer."""

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

from efferve.sniffer.base import BeaconEvent
from efferve.sniffer.ruckus import RuckusSniffer


def _make_sniffer() -> RuckusSniffer:
    return RuckusSniffer(
        host="192.168.1.1",
        username="admin",
        password="secret",
        poll_interval=1,
    )


def _mock_session(
    clients: list | None = None,
    rogues: list | None = None,
    events: list | None = None,
    rogues_error: bool = False,
    events_error: bool = False,
):
    """Build a mock AjaxSession context manager with configurable API responses."""
    session = MagicMock()
    session.api.get_active_clients = AsyncMock(return_value=clients or [])

    if rogues_error:
        session.api.get_active_rogues = AsyncMock(side_effect=Exception("rogue API unavailable"))
    else:
        session.api.get_active_rogues = AsyncMock(return_value=rogues or [])

    if events_error:
        session.api.get_client_events = AsyncMock(side_effect=Exception("events API unavailable"))
    else:
        session.api.get_client_events = AsyncMock(return_value=events or [])

    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


@pytest.fixture(autouse=True)
def _mock_aioruckus():
    """Inject a mock aioruckus module so the local import inside _poll_loop works."""
    mock_mod = MagicMock()
    sys.modules["aioruckus"] = mock_mod
    yield mock_mod
    del sys.modules["aioruckus"]


async def _run_one_cycle(sniffer, ctx, _mock_aioruckus, sleep: float = 0.2):
    """Start the poll loop with a mocked AjaxSession, run briefly, then stop."""
    _mock_aioruckus.AjaxSession.async_create.return_value = ctx
    sniffer._running = True
    task = asyncio.create_task(sniffer._poll_loop())
    await asyncio.sleep(sleep)
    sniffer._running = False
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


class TestRssiConversion:
    def test_snr_to_dbm(self):
        assert RuckusSniffer._convert_rssi(50) == -50

    def test_snr_high_to_dbm(self):
        assert RuckusSniffer._convert_rssi(100) == 0

    def test_snr_low_to_dbm(self):
        assert RuckusSniffer._convert_rssi(1) == -99

    def test_dbm_passthrough(self):
        assert RuckusSniffer._convert_rssi(-45) == -45

    def test_zero_passthrough(self):
        assert RuckusSniffer._convert_rssi(0) == 0

    def test_none_default(self):
        assert RuckusSniffer._convert_rssi(None) == -100


class TestRogueDetection:
    @pytest.mark.asyncio
    async def test_rogue_events_emitted(self, _mock_aioruckus):
        sniffer = _make_sniffer()
        received: list[BeaconEvent] = []
        sniffer.on_event(received.append)

        rogues = [
            {"mac": "aa:cc:f3:1a:41:6a", "ssid": "EvilTwin", "signal": 60},
            {"mac": "aa:cc:f3:1a:41:6b", "ssid": None, "signal": None},
        ]
        ctx = _mock_session(rogues=rogues)
        await _run_one_cycle(sniffer, ctx, _mock_aioruckus)

        rogue_events = [e for e in received if e.source == "ruckus_rogue"]
        assert len(rogue_events) == 2

        assert rogue_events[0].mac_address == "AA:CC:F3:1A:41:6A"
        assert rogue_events[0].ssid == "EvilTwin"
        assert rogue_events[0].signal_strength == -40  # SNR 60 → -40

        assert rogue_events[1].mac_address == "AA:CC:F3:1A:41:6B"
        assert rogue_events[1].ssid is None
        assert rogue_events[1].signal_strength == -100  # None → -100

    @pytest.mark.asyncio
    async def test_rogue_without_mac_skipped(self, _mock_aioruckus):
        sniffer = _make_sniffer()
        received: list[BeaconEvent] = []
        sniffer.on_event(received.append)

        rogues = [{"ssid": "NoMac", "signal": 50}]
        ctx = _mock_session(rogues=rogues)
        await _run_one_cycle(sniffer, ctx, _mock_aioruckus)

        rogue_events = [e for e in received if e.source == "ruckus_rogue"]
        assert len(rogue_events) == 0


class TestClientEvents:
    @pytest.mark.asyncio
    async def test_disconnect_events_emitted(self, _mock_aioruckus):
        sniffer = _make_sniffer()
        received: list[BeaconEvent] = []
        sniffer.on_event(received.append)

        events = [
            {
                "time": "1700000000",
                "client": "aa:cc:f3:1a:41:6c",
                "event": "client_disassociated",
                "ssid": "HomeNet",
            },
        ]
        ctx = _mock_session(events=events)
        await _run_one_cycle(sniffer, ctx, _mock_aioruckus)

        event_events = [e for e in received if e.source == "ruckus_event"]
        assert len(event_events) == 1
        assert event_events[0].mac_address == "AA:CC:F3:1A:41:6C"
        assert event_events[0].signal_strength == 0
        assert event_events[0].ssid == "HomeNet"
        assert event_events[0].timestamp.year == 2023  # epoch 1700000000

    @pytest.mark.asyncio
    async def test_association_events_filtered(self, _mock_aioruckus):
        """Only disassociation events should be emitted."""
        sniffer = _make_sniffer()
        received: list[BeaconEvent] = []
        sniffer.on_event(received.append)

        events = [
            {
                "time": "1700000000",
                "client": "aa:cc:f3:1a:41:6c",
                "event": "client_associated",
                "ssid": "HomeNet",
            },
        ]
        ctx = _mock_session(events=events)
        await _run_one_cycle(sniffer, ctx, _mock_aioruckus)

        event_events = [e for e in received if e.source == "ruckus_event"]
        assert len(event_events) == 0

    @pytest.mark.asyncio
    async def test_deduplication(self, _mock_aioruckus):
        """Same event across two poll cycles should only emit once."""
        sniffer = _make_sniffer()
        received: list[BeaconEvent] = []
        sniffer.on_event(received.append)

        events = [
            {
                "time": "1700000000",
                "client": "aa:cc:f3:1a:41:6c",
                "event": "client_disassociated",
            },
        ]
        ctx = _mock_session(events=events)
        # Wait long enough for 2 poll cycles (interval=1s)
        await _run_one_cycle(sniffer, ctx, _mock_aioruckus, sleep=1.5)

        event_events = [e for e in received if e.source == "ruckus_event"]
        assert len(event_events) == 1

    @pytest.mark.asyncio
    async def test_bad_timestamp_falls_back_to_now(self, _mock_aioruckus):
        sniffer = _make_sniffer()
        received: list[BeaconEvent] = []
        sniffer.on_event(received.append)

        events = [
            {
                "time": "not_a_number",
                "client": "aa:cc:f3:1a:41:6c",
                "event": "disassoc",
            },
        ]
        ctx = _mock_session(events=events)
        await _run_one_cycle(sniffer, ctx, _mock_aioruckus)

        event_events = [e for e in received if e.source == "ruckus_event"]
        assert len(event_events) == 1
        # Timestamp should be recent (fallback to now), not epoch-based
        assert event_events[0].timestamp.year >= 2026


class TestGracefulDegradation:
    @pytest.mark.asyncio
    async def test_rogue_failure_doesnt_break_clients(self, _mock_aioruckus):
        sniffer = _make_sniffer()
        received: list[BeaconEvent] = []
        sniffer.on_event(received.append)

        clients = [{"mac": "aa:cc:f3:1a:41:79", "signal": -50, "ssid": "Home"}]
        ctx = _mock_session(clients=clients, rogues_error=True)
        await _run_one_cycle(sniffer, ctx, _mock_aioruckus)

        client_events = [e for e in received if e.source == "ruckus"]
        assert len(client_events) == 1
        assert client_events[0].mac_address == "AA:CC:F3:1A:41:79"

    @pytest.mark.asyncio
    async def test_event_failure_doesnt_break_clients(self, _mock_aioruckus):
        sniffer = _make_sniffer()
        received: list[BeaconEvent] = []
        sniffer.on_event(received.append)

        clients = [{"mac": "aa:cc:f3:1a:41:79", "signal": -50, "ssid": "Home"}]
        ctx = _mock_session(clients=clients, events_error=True)
        await _run_one_cycle(sniffer, ctx, _mock_aioruckus)

        client_events = [e for e in received if e.source == "ruckus"]
        assert len(client_events) == 1

    @pytest.mark.asyncio
    async def test_both_failures_still_yield_clients(self, _mock_aioruckus):
        sniffer = _make_sniffer()
        received: list[BeaconEvent] = []
        sniffer.on_event(received.append)

        clients = [{"mac": "aa:cc:f3:1a:41:79", "signal": -50, "ssid": "Home"}]
        ctx = _mock_session(clients=clients, rogues_error=True, events_error=True)
        await _run_one_cycle(sniffer, ctx, _mock_aioruckus)

        client_events = [e for e in received if e.source == "ruckus"]
        assert len(client_events) == 1
