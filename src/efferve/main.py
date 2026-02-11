"""Efferve application entrypoint."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import Session

from efferve.config import Settings, load_config, settings
from efferve.database import engine, init_db
from efferve.registry.store import reclassify_device, upsert_device
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


async def _start_sniffer(app: FastAPI) -> None:
    """Start the sniffer with current configuration."""
    cfg = load_config()
    sniffer = _create_sniffer(cfg.sniffer_mode, cfg)
    if sniffer:
        sniffer.on_event(_handle_beacon_event)
        await sniffer.start()
        logger.info("Sniffer started (mode=%s)", cfg.sniffer_mode)
    else:
        logger.info("No sniffer configured (mode=%s)", cfg.sniffer_mode)
    app.state.sniffer = sniffer


async def restart_sniffer(app: FastAPI) -> None:
    """Restart the sniffer with fresh configuration."""
    if hasattr(app.state, "sniffer") and app.state.sniffer:
        await app.state.sniffer.stop()
        logger.info("Stopped existing sniffer")
    await _start_sniffer(app)
    logger.info("Sniffer restarted")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown lifecycle."""
    init_db()
    logger.info("Database initialized")

    await _start_sniffer(app)

    yield

    if hasattr(app.state, "sniffer") and app.state.sniffer:
        await app.state.sniffer.stop()
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
