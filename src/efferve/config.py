"""Application configuration via environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "EFFERVE_"}

    # Database
    db_path: Path = Path("./data/efferve.db")

    # Logging
    log_level: str = "info"

    # Sniffer mode: "ruckus", "opnsense", "monitor", "mock", "none"
    sniffer_mode: str = "none"

    # WiFi Sniffer — Monitor Mode
    wifi_interface: str | None = None

    # Ruckus Unleashed
    ruckus_host: str | None = None
    ruckus_username: str | None = None
    ruckus_password: str | None = None

    # OPNsense
    opnsense_url: str | None = None
    opnsense_api_key: str | None = None
    opnsense_api_secret: str | None = None

    # Polling
    poll_interval: int = 30  # seconds between polls
    presence_grace_period: int = 180  # seconds before marking device "away"

    # Alerts
    webhook_url: str | None = None

    # Server
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
