"""Application configuration via environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "EFFERVE_"}

    # Database
    db_path: Path = Path("./data/efferve.db")

    # Logging
    log_level: str = "info"

    # WiFi Sniffer — Monitor Mode
    wifi_interface: str | None = None

    # WiFi Sniffer — Router API
    router_url: str | None = None
    router_user: str | None = None
    router_password: str | None = None
    router_type: str | None = None  # openwrt, unifi, mikrotik

    # Alerts
    webhook_url: str | None = None

    # Server
    host: str = "0.0.0.0"
    port: int = 8000


settings = Settings()
