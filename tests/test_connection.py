"""Tests for connection test utilities."""

import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest

from efferve.sniffer import test_connection as tc


class TestRuckusConnection:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        mock_session = AsyncMock()
        mock_session.api.get_active_clients.return_value = [
            {"mac": "AA:BB:CC:DD:EE:FF"},
            {"mac": "11:22:33:44:55:66"},
        ]

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_session

        with patch("aioruckus.AjaxSession.async_create", return_value=mock_ctx):
            result = await tc.test_ruckus("192.168.1.1", "admin", "password")

        assert result.success is True
        assert result.device_count == 2
        assert "2 active clients" in result.message

    @pytest.mark.asyncio
    async def test_failure(self) -> None:
        with patch(
            "aioruckus.AjaxSession.async_create",
            side_effect=ConnectionError("refused"),
        ):
            result = await tc.test_ruckus("192.168.1.1", "admin", "wrong")

        assert result.success is False
        assert "refused" in result.message
        assert result.device_count is None


class TestOPNsenseConnection:
    @pytest.mark.asyncio
    async def test_success(self) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rows": [{"mac": "AA:BB:CC:DD:EE:FF"}, {"mac": "11:22:33:44:55:66"}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("efferve.sniffer.test_connection.httpx.AsyncClient", return_value=mock_client):
            result = await tc.test_opnsense("https://192.168.1.1", "key", "secret")

        assert result.success is True
        assert result.device_count == 2
        assert "2 DHCP leases" in result.message

    @pytest.mark.asyncio
    async def test_failure(self) -> None:
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("efferve.sniffer.test_connection.httpx.AsyncClient", return_value=mock_client):
            result = await tc.test_opnsense("https://192.168.1.1", "key", "secret")

        assert result.success is False
        assert "Connection refused" in result.message
        assert result.device_count is None


class TestGlinetConnection:
    @pytest.fixture(autouse=True)
    def _mock_asyncssh(self):
        mock_mod = MagicMock()
        sys.modules["asyncssh"] = mock_mod
        yield mock_mod
        sys.modules.pop("asyncssh", None)

    @pytest.mark.asyncio
    async def test_success(self, _mock_asyncssh) -> None:
        conn = AsyncMock()
        conn.run = AsyncMock(
            return_value=Mock(
                stdout="Interface wlan0\n\tifindex 3\n\ttype managed",
                exit_status=0,
            )
        )
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=None)

        _mock_asyncssh.connect = MagicMock(return_value=conn)

        result = await tc.test_glinet("192.168.1.47", "root", "password")
        assert result.success is True
        assert "SSH access verified" in result.message

    @pytest.mark.asyncio
    async def test_failure(self, _mock_asyncssh) -> None:
        _mock_asyncssh.connect = MagicMock(side_effect=ConnectionError("Connection refused"))

        result = await tc.test_glinet("192.168.1.47", "root", "wrong")
        assert result.success is False
        assert "Connection refused" in result.message

    @pytest.mark.asyncio
    async def test_no_wifi_interfaces(self, _mock_asyncssh) -> None:
        conn = AsyncMock()
        conn.run = AsyncMock(return_value=Mock(stdout="", exit_status=0))
        conn.__aenter__ = AsyncMock(return_value=conn)
        conn.__aexit__ = AsyncMock(return_value=None)

        _mock_asyncssh.connect = MagicMock(return_value=conn)

        result = await tc.test_glinet("192.168.1.47", "root", "password")
        assert result.success is False
        assert "no WiFi interfaces" in result.message
