"""Application configuration via environment variables and .env file."""

import re
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings
from pydantic_settings.sources import DotEnvSettingsSource, PydanticBaseSettingsSource

# Path to .env file (patch in tests to use tmp_path / ".env")
_ENV_FILE: Path = Path(".env")


def _field_to_env_key(name: str) -> str:
    """Convert Settings field name to EFFERVE_ env var name."""
    return "EFFERVE_" + name.upper()


def _parse_env_line(line: str) -> tuple[str, str] | None:
    """Parse a single KEY=VALUE or KEY="VALUE" line. Returns (key, value) or None."""
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
    if not m:
        return None
    key, raw = m.group(1), m.group(2).strip()
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        raw = raw[1:-1].replace('\\"', '"').replace("\\n", "\n")
    return (key, raw)


def _format_env_value(value: str) -> str:
    """Format a value for .env: quote if it contains special chars."""
    if not value:
        return ""
    if re.search(r'[\s#"\\\n]', value):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    return value


def _config_value_to_env_str(v: str | list[str] | int | None) -> str:
    """Convert a config value to .env string."""
    if isinstance(v, list):
        return ",".join(str(x) for x in v)
    if v is None:
        return ""
    return str(v)


class Settings(BaseSettings):
    model_config = {
        "env_prefix": "EFFERVE_",
        "env_file_encoding": "utf-8",
    }

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Load .env from _ENV_FILE (patchable in tests)
        return (
            init_settings,
            env_settings,
            DotEnvSettingsSource(
                settings_cls,
                env_file=_ENV_FILE,
                env_file_encoding="utf-8",
            ),
            file_secret_settings,
        )

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

    # Authentication (optional — omit to disable)
    auth_username: str = "admin"
    auth_password: str | None = None

    # Server
    host: str = "0.0.0.0"
    port: int = 8000


def save_config(values: dict[str, str | list[str] | int | None]) -> None:
    """Save configuration to .env file.

    Only stores keys that correspond to valid Settings fields.
    Merges with existing .env (preserves non-EFFERVE_* lines and other vars).
    """
    valid_fields = set(Settings.model_fields.keys())
    filtered = {k: v for k, v in values.items() if k in valid_fields}

    # Read existing .env: keep non-EFFERVE lines as-is, collect EFFERVE_* into dict
    other_lines: list[str] = []
    efferve_vars: dict[str, str] = {}
    if _ENV_FILE.exists():
        with open(_ENV_FILE, encoding="utf-8") as f:
            for line in f:
                parsed = _parse_env_line(line)
                if parsed is None:
                    other_lines.append(line.rstrip("\n"))
                else:
                    key, val = parsed
                    if key.startswith("EFFERVE_"):
                        efferve_vars[key] = val
                    else:
                        other_lines.append(line.rstrip("\n"))

    # Update EFFERVE_* from filtered values
    for name, val in filtered.items():  # type: ignore[assignment]
        env_key = _field_to_env_key(name)
        efferve_vars[env_key] = _config_value_to_env_str(val)

    # Write: other lines first, then EFFERVE_* in stable order
    efferve_keys_sorted = sorted(efferve_vars.keys())
    with open(_ENV_FILE, "w", encoding="utf-8") as f:
        for line in other_lines:
            f.write(line + "\n")
        if other_lines:
            f.write("\n")
        for key in efferve_keys_sorted:
            raw = efferve_vars[key]
            f.write(f"{key}={_format_env_value(raw)}\n")


def load_config() -> Settings:
    """Load configuration from .env and environment (env overrides .env)."""
    return Settings()


settings = Settings()
