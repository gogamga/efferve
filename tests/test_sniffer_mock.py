"""Tests for the mock sniffer."""

import asyncio

import pytest

from efferve.sniffer.base import BeaconEvent
from efferve.sniffer.mock import MockSniffer


class TestMockSniffer:
    def test_emits_valid_beacon_events(self):
        sniffer = MockSniffer(poll_interval=1)
        events = sniffer._generate_events(
            __import__("datetime").datetime.now(__import__("datetime").UTC)
        )
        assert len(events) > 0
        for event in events:
            assert isinstance(event, BeaconEvent)
            assert event.mac_address
            assert isinstance(event.signal_strength, int)
            assert event.source == "mock"

    def test_callback_fires(self):
        sniffer = MockSniffer(poll_interval=1)
        received: list[BeaconEvent] = []
        sniffer.on_event(received.append)

        events = sniffer._generate_events(
            __import__("datetime").datetime.now(__import__("datetime").UTC)
        )
        # Simulate what _poll_loop does
        for event in events:
            for cb in sniffer._callbacks:
                cb(event)

        assert len(received) == len(events)

    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self):
        sniffer = MockSniffer(poll_interval=1)
        received: list[BeaconEvent] = []
        sniffer.on_event(received.append)

        await sniffer.start()
        assert sniffer._running is True
        assert sniffer._task is not None

        # Let it run briefly
        await asyncio.sleep(1.5)

        await sniffer.stop()
        assert sniffer._running is False
        assert len(received) > 0
