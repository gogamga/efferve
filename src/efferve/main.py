"""Efferve application entrypoint."""

import base64
import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from efferve.alerts.manager import dispatch_webhooks, evaluate_presence_change
from efferve.config import Settings, load_config, settings
from efferve.database import engine, init_db
from efferve.registry.store import detect_presence_changes, reclassify_device, upsert_device
from efferve.sniffer.base import BaseSniffer, BeaconEvent

logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger(__name__)


def _create_sniffer(mode: str, cfg: Settings) -> BaseSniffer | None:
    """Factory: instantiate the configured sniffer backend."""
    if mode == "ruckus":
        from efferve.sniffer.ruckus import RuckusSniffer

        if not cfg.ruckus_host or not cfg.ruckus_username or not cfg.ruckus_password:
            logger.warning("Ruckus mode selected but credentials not configured")
            return None
        return RuckusSniffer(
            host=cfg.ruckus_host,
            username=cfg.ruckus_username,
            password=cfg.ruckus_password,
            poll_interval=cfg.poll_interval,
        )
    if mode == "opnsense":
        from efferve.sniffer.opnsense import OpnsenseSniffer

        if not cfg.opnsense_url or not cfg.opnsense_api_key or not cfg.opnsense_api_secret:
            logger.warning("OPNsense mode selected but credentials not configured")
            return None
        return OpnsenseSniffer(
            url=cfg.opnsense_url,
            api_key=cfg.opnsense_api_key,
            api_secret=cfg.opnsense_api_secret,
            poll_interval=cfg.poll_interval,
        )
    if mode == "monitor":
        from efferve.sniffer.monitor import MonitorSniffer

        if not cfg.wifi_interface:
            logger.warning("Monitor mode selected but wifi_interface not configured")
            return None
        return MonitorSniffer(interface=cfg.wifi_interface)
    if mode == "glinet":
        from efferve.sniffer.glinet import GlinetSniffer

        if not cfg.glinet_host or not cfg.glinet_password:
            logger.warning("GL.iNet mode selected but credentials not configured")
            return None
        return GlinetSniffer(
            host=cfg.glinet_host,
            username=cfg.glinet_username,
            password=cfg.glinet_password,
            wifi_interface=cfg.glinet_wifi_interface,
            monitor_interface=cfg.glinet_monitor_interface,
            poll_interval=cfg.poll_interval,
        )
    if mode == "mock":
        from efferve.sniffer.mock import MockSniffer

        return MockSniffer(poll_interval=5)
    if mode == "none":
        return None
    logger.warning("Unknown sniffer mode '%s', skipping", mode)
    return None


def _handle_beacon_event(event: BeaconEvent) -> None:
    """Callback: persist a beacon event to the device registry."""
    try:
        with Session(engine) as session:
            device = upsert_device(session, event)
            reclassify_device(session, device)

            # Detect presence changes and trigger alerts
            try:
                grace = settings.presence_grace_period
                changes = detect_presence_changes(session, grace_seconds=grace)
                all_payloads = []
                for mac, event_type in changes:
                    logger.info("Presence change: %s %s", mac, event_type)
                    device_name = device.display_name or device.hostname or device.vendor
                    payloads = evaluate_presence_change(
                        session, mac, event_type, device_name=device_name
                    )
                    all_payloads.extend(payloads)

                if all_payloads:
                    dispatch_webhooks(all_payloads)
            except Exception:
                logger.exception("Error detecting presence changes or dispatching alerts")
    except Exception:
        logger.exception("Error handling beacon event for %s", event.mac_address)


async def _start_sniffers(app: FastAPI) -> None:
    """Start all configured sniffers."""
    cfg = load_config()
    modes = cfg.get_active_sniffer_modes()

    sniffers: list[BaseSniffer] = []
    for mode in modes:
        sniffer = _create_sniffer(mode, cfg)
        if sniffer:
            sniffer.on_event(_handle_beacon_event)
            await sniffer.start()
            sniffers.append(sniffer)
            logger.info("Sniffer started: %s", mode)

    if not sniffers:
        logger.info("No sniffers configured")
    else:
        logger.info("Running %d sniffer(s): %s", len(sniffers), modes)

    app.state.sniffers = sniffers


async def restart_sniffer(app: FastAPI) -> None:
    """Restart all sniffers with fresh configuration."""
    if hasattr(app.state, "sniffers"):
        for sniffer in app.state.sniffers:
            await sniffer.stop()
        logger.info("Stopped %d existing sniffer(s)", len(app.state.sniffers))
    await _start_sniffers(app)
    logger.info("Sniffers restarted")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown lifecycle."""
    # Import models to register them with SQLModel before init_db()
    import efferve.alerts.models  # noqa: F401
    import efferve.persona.models  # noqa: F401
    import efferve.registry.models  # noqa: F401

    init_db()
    logger.info("Database initialized")

    await _start_sniffers(app)

    yield

    if hasattr(app.state, "sniffers"):
        for sniffer in app.state.sniffers:
            await sniffer.stop()
        logger.info("All sniffers stopped")


app = FastAPI(
    title="Efferve",
    description="WiFi presence detection and home automation",
    version="0.1.0",
    lifespan=lifespan,
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://unpkg.com; "
            "style-src 'self' 'unsafe-inline'"
        )
        return response


class BasicAuthMiddleware(BaseHTTPMiddleware):
    """HTTP Basic Authentication middleware.

    Protects all routes except /health. Requires valid username/password
    provided via Authorization header.
    """

    def __init__(self, app, username: str, password: str):
        super().__init__(app)
        self.username = username
        self.password = password

    async def dispatch(self, request, call_next):
        # Exempt health check endpoint
        if request.url.path == "/health":
            return await call_next(request)

        # Check Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Basic "):
            return self._unauthorized_response()

        # Decode credentials
        try:
            encoded = auth_header[6:]  # Strip "Basic "
            decoded = base64.b64decode(encoded).decode("utf-8")
            provided_username, provided_password = decoded.split(":", 1)
        except Exception:
            return self._unauthorized_response()

        # Timing-safe comparison
        username_match = secrets.compare_digest(provided_username, self.username)
        password_match = secrets.compare_digest(provided_password, self.password)

        if not (username_match and password_match):
            return self._unauthorized_response()

        return await call_next(request)

    def _unauthorized_response(self) -> Response:
        return Response(
            content="Unauthorized",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Efferve"'},
        )


app.add_middleware(SecurityHeadersMiddleware)

# Conditionally add BasicAuth if password is configured
if settings.auth_password:
    app.add_middleware(
        BasicAuthMiddleware, username=settings.auth_username, password=settings.auth_password
    )
    logger.info("HTTP Basic Auth enabled")


# Register routers
from efferve.api.routes import router as api_router  # noqa: E402
from efferve.ui.routes import router as ui_router  # noqa: E402

app.include_router(api_router)
app.include_router(ui_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def main() -> None:
    import uvicorn

    logger.info("Starting Efferve on %s:%d", settings.host, settings.port)
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
