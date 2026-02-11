"""Efferve application entrypoint."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Session

from efferve.config import settings
from efferve.database import engine, init_db
from efferve.registry.store import reclassify_device, upsert_device
from efferve.sniffer.base import BaseSniffer, BeaconEvent

logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger(__name__)


def _create_sniffer(mode: str) -> BaseSniffer | None:
    """Factory: instantiate the configured sniffer backend."""
    if mode == "ruckus":
        from efferve.sniffer.ruckus import RuckusSniffer

        assert settings.ruckus_host, "EFFERVE_RUCKUS_HOST is required"
        assert settings.ruckus_username, "EFFERVE_RUCKUS_USERNAME is required"
        assert settings.ruckus_password, "EFFERVE_RUCKUS_PASSWORD is required"
        return RuckusSniffer(
            host=settings.ruckus_host,
            username=settings.ruckus_username,
            password=settings.ruckus_password,
            poll_interval=settings.poll_interval,
        )
    if mode == "opnsense":
        from efferve.sniffer.opnsense import OpnsenseSniffer

        assert settings.opnsense_url, "EFFERVE_OPNSENSE_URL is required"
        assert settings.opnsense_api_key, "EFFERVE_OPNSENSE_API_KEY is required"
        assert settings.opnsense_api_secret, "EFFERVE_OPNSENSE_API_SECRET is required"
        return OpnsenseSniffer(
            url=settings.opnsense_url,
            api_key=settings.opnsense_api_key,
            api_secret=settings.opnsense_api_secret,
            poll_interval=settings.poll_interval,
        )
    if mode == "monitor":
        from efferve.sniffer.monitor import MonitorSniffer

        assert settings.wifi_interface, "EFFERVE_WIFI_INTERFACE is required"
        return MonitorSniffer(interface=settings.wifi_interface)
    if mode == "mock":
        from efferve.sniffer.mock import MockSniffer

        return MockSniffer(poll_interval=5)
    if mode == "none":
        return None
    logger.warning("Unknown sniffer mode '%s', running without sniffer", mode)
    return None


def _handle_beacon_event(event: BeaconEvent) -> None:
    """Callback: persist a beacon event to the device registry."""
    try:
        with Session(engine) as session:
            device = upsert_device(session, event)
            reclassify_device(session, device)
    except Exception:
        logger.exception("Error handling beacon event for %s", event.mac_address)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown lifecycle."""
    init_db()
    logger.info("Database initialized")

    sniffer = _create_sniffer(settings.sniffer_mode)
    if sniffer:
        sniffer.on_event(_handle_beacon_event)
        await sniffer.start()
        logger.info("Sniffer started (mode=%s)", settings.sniffer_mode)
    else:
        logger.info("No sniffer configured (mode=%s)", settings.sniffer_mode)

    yield

    if sniffer:
        await sniffer.stop()
        logger.info("Sniffer stopped")


app = FastAPI(
    title="Efferve",
    description="WiFi presence detection and home automation",
    version="0.1.0",
    lifespan=lifespan,
)

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
