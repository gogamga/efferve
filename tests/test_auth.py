"""Tests for HTTP Basic Auth middleware."""

import base64

import pytest
from fastapi.testclient import TestClient


def test_no_auth_when_password_not_set(client: TestClient):
    """Requests pass through when auth_password is None (disabled)."""
    # By default, the client fixture patches auth_password to None
    resp = client.get("/")
    assert resp.status_code == 200


def test_health_endpoint_always_exempt(client: TestClient):
    """/health endpoint is always accessible without auth."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.fixture
def auth_client(engine) -> TestClient:
    """Test client with auth enabled."""
    from collections.abc import Generator
    from unittest.mock import patch

    import efferve.database as db_module
    from efferve.database import get_session
    from sqlmodel import Session

    # Patch settings to enable auth BEFORE importing main
    with patch("efferve.config.settings") as mock_settings:
        mock_settings.auth_username = "admin"
        mock_settings.auth_password = "secret"
        mock_settings.log_level = "info"
        mock_settings.host = "0.0.0.0"
        mock_settings.port = 8000
        mock_settings.presence_grace_period = 180

        # Now import main, which will register middleware based on patched settings
        # We need to reload the module to pick up the patched settings
        import importlib
        import efferve.main

        importlib.reload(efferve.main)

        app = efferve.main.app

        # Override DB session
        original_engine = db_module.engine
        db_module.engine = engine

        def _override_session() -> Generator[Session, None, None]:
            with Session(engine) as s:
                yield s

        app.dependency_overrides[get_session] = _override_session

        with TestClient(app) as c:
            yield c

        app.dependency_overrides.clear()
        db_module.engine = original_engine

        # Reload again to restore normal state
        importlib.reload(efferve.main)


def test_auth_required_when_password_set(auth_client: TestClient):
    """401 returned when credentials missing and auth enabled."""
    resp = auth_client.get("/")
    assert resp.status_code == 401
    assert "WWW-Authenticate" in resp.headers
    assert resp.headers["WWW-Authenticate"] == 'Basic realm="Efferve"'


def test_wrong_credentials(auth_client: TestClient):
    """401 returned for wrong credentials."""
    # Wrong username
    wrong_user = base64.b64encode(b"wronguser:secret").decode("utf-8")
    resp = auth_client.get("/", headers={"Authorization": f"Basic {wrong_user}"})
    assert resp.status_code == 401

    # Wrong password
    wrong_pass = base64.b64encode(b"admin:wrongpass").decode("utf-8")
    resp = auth_client.get("/", headers={"Authorization": f"Basic {wrong_pass}"})
    assert resp.status_code == 401


def test_correct_credentials(auth_client: TestClient):
    """200 returned for correct credentials."""
    credentials = base64.b64encode(b"admin:secret").decode("utf-8")
    resp = auth_client.get("/", headers={"Authorization": f"Basic {credentials}"})
    assert resp.status_code == 200


def test_malformed_auth_header(auth_client: TestClient):
    """401 returned for malformed Authorization header."""
    # Missing "Basic " prefix
    resp = auth_client.get("/", headers={"Authorization": "invalid"})
    assert resp.status_code == 401

    # Invalid base64
    resp = auth_client.get("/", headers={"Authorization": "Basic !!!"})
    assert resp.status_code == 401

    # Valid base64 but no colon separator
    bad_format = base64.b64encode(b"adminnocolon").decode("utf-8")
    resp = auth_client.get("/", headers={"Authorization": f"Basic {bad_format}"})
    assert resp.status_code == 401


def test_health_with_auth_enabled(auth_client: TestClient):
    """/health is exempt even when auth is enabled."""
    resp = auth_client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
