"""Tests for the setup wizard UI routes."""

import re
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

import efferve.config as config_module
from efferve.sniffer.test_connection import ConnectionResult


def _read_env_as_dict(env_path: Path) -> dict[str, str]:
    """Parse .env file into key -> value dict (EFFERVE_* only, simple KEY=VALUE)."""
    result: dict[str, str] = {}
    if not env_path.exists():
        return result
    for line in env_path.read_text().splitlines():
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line.strip())
        if m and m.group(1).startswith("EFFERVE_"):
            result[m.group(1)] = m.group(2).strip().strip('"')
    return result


@pytest.fixture
def env_file(tmp_path: Path) -> Generator[Path, None, None]:
    """Use a temporary .env file instead of the real one."""
    env_path = tmp_path / ".env"
    original = config_module._ENV_FILE
    config_module._ENV_FILE = env_path
    yield env_path
    config_module._ENV_FILE = original


class TestSetupPage:
    def test_setup_page_loads(self, client: TestClient) -> None:
        resp = client.get("/setup")
        assert resp.status_code == 200
        assert "Ruckus" in resp.text
        assert "OPNsense" in resp.text
        assert "Poll Interval" in resp.text

    def test_setup_page_shows_existing_config(self, client: TestClient, env_file: Path) -> None:
        env_file.write_text("EFFERVE_RUCKUS_HOST=10.0.0.1\n")
        resp = client.get("/setup")
        assert resp.status_code == 200
        assert "10.0.0.1" in resp.text


class TestSaveConfig:
    def test_save_writes_env(self, client: TestClient, env_file: Path) -> None:
        with patch("efferve.main.restart_sniffer", new_callable=AsyncMock):
            resp = client.post(
                "/setup/save",
                data={
                    "ruckus_host": "192.168.1.100",
                    "ruckus_username": "admin",
                    "ruckus_password": "secret",
                    "opnsense_url": "",
                    "opnsense_api_key": "",
                    "opnsense_api_secret": "",
                    "glinet_host": "",
                    "glinet_username": "root",
                    "glinet_password": "",
                    "glinet_wifi_interface": "wlan0",
                    "glinet_monitor_interface": "wlan0mon",
                    "poll_interval": "15",
                    "presence_grace_period": "120",
                },
            )
        assert resp.status_code == 200
        assert resp.headers.get("HX-Redirect") == "/"
        saved = _read_env_as_dict(env_file)
        assert saved.get("EFFERVE_RUCKUS_HOST") == "192.168.1.100"
        assert saved.get("EFFERVE_SNIFFER_MODES") == "ruckus"
        assert saved.get("EFFERVE_POLL_INTERVAL") == "15"

    def test_save_partial_merge(self, client: TestClient, env_file: Path) -> None:
        """Save Ruckus first, then OPNsense — both should be preserved."""
        env_file.write_text(
            "EFFERVE_RUCKUS_HOST=10.0.0.1\n"
            "EFFERVE_RUCKUS_USERNAME=admin\n"
            "EFFERVE_RUCKUS_PASSWORD=pass\n"
        )
        with patch("efferve.main.restart_sniffer", new_callable=AsyncMock):
            client.post(
                "/setup/save",
                data={
                    "ruckus_host": "",
                    "ruckus_username": "",
                    "ruckus_password": "",
                    "opnsense_url": "https://fw.local",
                    "opnsense_api_key": "key123",
                    "opnsense_api_secret": "secret456",
                    "glinet_host": "",
                    "glinet_username": "root",
                    "glinet_password": "",
                    "glinet_wifi_interface": "wlan0",
                    "glinet_monitor_interface": "wlan0mon",
                    "poll_interval": "30",
                    "presence_grace_period": "180",
                },
            )
        saved = _read_env_as_dict(env_file)
        assert saved.get("EFFERVE_OPNSENSE_URL") == "https://fw.local"
        assert saved.get("EFFERVE_SNIFFER_MODES") == "opnsense"

    def test_save_restarts_sniffer(self, client: TestClient, env_file: Path) -> None:
        with patch("efferve.main.restart_sniffer", new_callable=AsyncMock) as mock_restart:
            client.post(
                "/setup/save",
                data={
                    "ruckus_host": "",
                    "ruckus_username": "",
                    "ruckus_password": "",
                    "opnsense_url": "",
                    "opnsense_api_key": "",
                    "opnsense_api_secret": "",
                    "glinet_host": "",
                    "glinet_username": "root",
                    "glinet_password": "",
                    "glinet_wifi_interface": "wlan0",
                    "glinet_monitor_interface": "wlan0mon",
                    "poll_interval": "30",
                    "presence_grace_period": "180",
                },
            )
            mock_restart.assert_called_once()


class TestConnectionTestEndpoints:
    def test_ruckus_test_returns_fragment(self, client: TestClient) -> None:
        with patch(
            "efferve.ui.routes.test_ruckus",
            new_callable=AsyncMock,
            return_value=ConnectionResult(
                success=True, message="Connected — 5 active clients", device_count=5
            ),
        ):
            resp = client.post(
                "/setup/test/ruckus",
                data={
                    "ruckus_host": "10.0.0.1",
                    "ruckus_username": "admin",
                    "ruckus_password": "pass",
                },
            )
        assert resp.status_code == 200
        assert "test-success" in resp.text
        assert "5 active clients" in resp.text

    def test_ruckus_test_failure_fragment(self, client: TestClient) -> None:
        with patch(
            "efferve.ui.routes.test_ruckus",
            new_callable=AsyncMock,
            return_value=ConnectionResult(success=False, message="Connection refused"),
        ):
            resp = client.post(
                "/setup/test/ruckus",
                data={
                    "ruckus_host": "10.0.0.1",
                    "ruckus_username": "admin",
                    "ruckus_password": "pass",
                },
            )
        assert resp.status_code == 200
        assert "test-failure" in resp.text
        assert "Connection refused" in resp.text

    def test_opnsense_test_returns_fragment(self, client: TestClient) -> None:
        with patch(
            "efferve.ui.routes.test_opnsense",
            new_callable=AsyncMock,
            return_value=ConnectionResult(
                success=True, message="Connected — 12 DHCP leases", device_count=12
            ),
        ):
            resp = client.post(
                "/setup/test/opnsense",
                data={
                    "opnsense_url": "https://fw.local",
                    "opnsense_api_key": "key",
                    "opnsense_api_secret": "secret",
                },
            )
        assert resp.status_code == 200
        assert "test-success" in resp.text
        assert "12 DHCP leases" in resp.text
