"""Application configuration via environment variables."""

import json
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, JsonConfigSettingsSource

_CONFIG_FILE = Path("./data/config.json")


class Settings(BaseSettings):
    model_config = {
        "env_prefix": "EFFERVE_",
        "json_file": _CONFIG_FILE,
    }

    # Database
    db_path: Path = Path("./data/efferve.db")

    # Logging
    log_level: str = "info"

    # Sniffer mode (deprecated, use sniffer_modes)
    sniffer_mode: str = "none"

    # Multiple sniffer backends to run simultaneously
    # Env: EFFERVE_SNIFFER_MODES="ruckus,glinet"
    sniffer_modes: list[str] = []

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

    # GL.iNet Remote Monitor (Peek)
    glinet_host: str | None = None
    glinet_username: str = "root"
    glinet_password: str | None = None
    glinet_wifi_interface: str = "wlan0"
    glinet_monitor_interface: str = "wlan0mon"

    @field_validator("sniffer_modes", mode="before")
    @classmethod
    def parse_sniffer_modes(cls, v: object) -> list[str]:
        """Parse comma-separated string or list."""
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        if isinstance(v, list):
            return [s for s in v if s]
        return []

    def get_active_sniffer_modes(self) -> list[str]:
        """Return list of sniffer modes, with backwards compat for sniffer_mode."""
        if self.sniffer_modes:
            return self.sniffer_modes
        if self.sniffer_mode and self.sniffer_mode != "none":
            return [self.sniffer_mode]
        return []

    # Polling
    poll_interval: int = 30  # seconds between polls
    presence_grace_period: int = 180  # seconds before marking device "away"

    # Alerts
    webhook_url: str | None = None

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
        **kwargs,
    ):
        return (
            init_settings,
            env_settings,
            JsonConfigSettingsSource(settings_cls, json_file=_CONFIG_FILE),
            file_secret_settings,
        )


def save_config(values: dict) -> None:
    """Save configuration values to JSON file.

    Only stores keys that correspond to valid Settings fields.
    Merges with existing config if the file already exists.
    """
    # Read existing config or start with empty dict
    existing = {}
    if _CONFIG_FILE.exists():
        with open(_CONFIG_FILE) as f:
            existing = json.load(f)

    # Filter to only valid Settings fields
    valid_fields = set(Settings.model_fields.keys())
    filtered_values = {k: v for k, v in values.items() if k in valid_fields}

    # Merge new values into existing
    existing.update(filtered_values)

    # Ensure parent directory exists
    _CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Write back to file
    with open(_CONFIG_FILE, "w") as f:
        json.dump(existing, f, indent=2)


def load_config() -> Settings:
    """Load configuration from all sources (JSON, env, defaults).

    Returns a fresh Settings instance that re-reads the JSON file and environment.
    """
    return Settings()


settings = Settings()
