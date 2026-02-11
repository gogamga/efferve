"""Application configuration via environment variables."""

import json
from pathlib import Path

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
