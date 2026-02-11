# Project: Efferve

## Quick Context
WiFi presence detection and home automation system. Sniffs WiFi probe requests
and router client lists to detect personal devices, associate them with people,
and trigger alerts/automations based on presence.

- Language: Python 3.11+
- Framework: FastAPI (backend) + Jinja2/HTMX (UI)
- Package Manager: pip (pyproject.toml with hatchling)
- Database: SQLite via SQLModel (designed for future Postgres swap)
- Deployment: Docker-first (requires NET_ADMIN + NET_RAW capabilities)

## Roles
- **Human**: Architecture decisions, requirement definition, approval of plans.
- **Claude**: Propose approaches, implement approved plans, write tests, flag risks.
- **Workflow**: Plan → Approve → Execute → Verify → Commit. No code without a plan.

## Build & Test Commands
- `pip install -e ".[dev]"` — Install for development
- `pytest` — Run all tests
- `pytest tests/test_foo.py` — Run single test file
- `ruff check src/` — Lint
- `ruff format src/ tests/` — Format
- `mypy src/` — Type checking
- `docker compose up --build` — Build and run in Docker
- `uvicorn efferve.main:app --reload` — Dev server

## Architecture
```
src/efferve/
├── main.py           # FastAPI app entrypoint
├── config.py         # pydantic-settings configuration
├── database.py       # SQLModel engine and session management
├── sniffer/          # WiFi capture backends
│   ├── base.py       # BaseSniffer ABC + BeaconEvent dataclass
│   ├── monitor.py    # Monitor mode via scapy (raw packet capture)
│   └── router_api.py # Router API polling (OpenWrt, UniFi, Mikrotik)
├── registry/         # Device detection, fingerprinting, household filtering
│   ├── models.py     # Device SQLModel
│   └── store.py      # CRUD operations
├── persona/          # Device-to-person association and profile building
│   └── engine.py     # Persona logic
├── alerts/           # Presence-based notifications and automation triggers
│   └── manager.py    # Alert rules and dispatch
├── api/              # FastAPI route handlers (JSON API)
│   └── routes.py     # REST endpoints
└── ui/               # Server-rendered dashboard
    └── templates/    # Jinja2 + HTMX templates
tests/                # Mirrors src/ structure
data/                 # SQLite database (gitignored)
```

## Key Patterns & Conventions
- All sniffer backends implement `BaseSniffer` ABC from `sniffer/base.py`.
- `BeaconEvent` is the universal data structure for any WiFi observation.
- Database models use SQLModel (Pydantic + SQLAlchemy hybrid).
- Config via environment variables with `EFFERVE_` prefix (pydantic-settings).
- UI uses Jinja2 templates with HTMX for interactivity — no JS build step.
- API routes go under `/api/`, UI routes under `/`.
- Type hints everywhere. mypy strict mode.

## Household Filtering Logic (Core Feature)
Devices are classified by signal strength patterns and visit frequency:
- **Resident**: Seen consistently over multiple days, strong signal.
- **Frequent visitor**: Seen regularly but not always present.
- **Passerby**: Seen briefly, weak signal, no repeat pattern.
Only Resident and Frequent visitor devices surface in the UI by default.

## Database Design Principle
SQLite now, Postgres later. Use SQLModel throughout. Avoid raw SQL.
Keep the engine creation in `database.py` so swapping the connection
string is the only change needed for Postgres migration.

## Gotchas & Warnings
- Monitor mode sniffing requires root/NET_ADMIN — won't work in normal dev.
  Use router API mode or mock data for local development.
- MAC address randomization (iOS/Android) means probe requests may use
  random MACs. The registry must handle this (OUI filtering, behavior correlation).
- scapy import is heavy and optional — only import when monitor mode is active.
- Docker must run with `--cap-add=NET_ADMIN --cap-add=NET_RAW --network=host`
  for monitor mode to work.

## Verification
- Before marking any task complete, run: `pytest && ruff check src/`
- For UI changes, visually verify in the browser at http://localhost:8000
- For sniffer changes, verify with mock beacon events (don't require live WiFi)

## Don'ts (Project-Specific)
- Don't add a JS build system. HTMX + Jinja2 is the UI strategy.
- Don't use async SQLAlchemy unless we hit a concrete performance wall.
- Don't hardcode WiFi interface names or router credentials anywhere.
- Don't store raw packet captures in the database — only parsed BeaconEvents.
