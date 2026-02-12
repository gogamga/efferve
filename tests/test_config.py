"""Tests for multi-sniffer configuration."""

from efferve.config import Settings


class TestSnifferModesParsing:
    def test_comma_separated_string(self):
        s = Settings(sniffer_modes="ruckus,glinet")
        assert s.sniffer_modes == ["ruckus", "glinet"]

    def test_comma_separated_with_spaces(self):
        s = Settings(sniffer_modes=" ruckus , glinet ")
        assert s.sniffer_modes == ["ruckus", "glinet"]

    def test_single_value_string(self):
        s = Settings(sniffer_modes="ruckus")
        assert s.sniffer_modes == ["ruckus"]

    def test_empty_string(self):
        s = Settings(sniffer_modes="")
        assert s.sniffer_modes == []

    def test_list_input(self):
        s = Settings(sniffer_modes=["ruckus", "glinet"])
        assert s.sniffer_modes == ["ruckus", "glinet"]

    def test_list_filters_empty_strings(self):
        s = Settings(sniffer_modes=["ruckus", "", "glinet"])
        assert s.sniffer_modes == ["ruckus", "glinet"]


class TestGetActiveSnifferModes:
    def test_returns_sniffer_modes_when_set(self):
        s = Settings(sniffer_modes=["ruckus", "glinet"])
        assert s.get_active_sniffer_modes() == ["ruckus", "glinet"]

    def test_falls_back_to_sniffer_mode(self):
        s = Settings(sniffer_mode="ruckus", sniffer_modes=[])
        assert s.get_active_sniffer_modes() == ["ruckus"]

    def test_returns_empty_when_mode_is_none(self):
        s = Settings(sniffer_mode="none", sniffer_modes=[])
        assert s.get_active_sniffer_modes() == []

    def test_sniffer_modes_takes_precedence(self):
        s = Settings(sniffer_mode="ruckus", sniffer_modes=["glinet"])
        assert s.get_active_sniffer_modes() == ["glinet"]

    def test_default_returns_empty(self):
        s = Settings(sniffer_mode="none", sniffer_modes=[])
        assert s.get_active_sniffer_modes() == []
