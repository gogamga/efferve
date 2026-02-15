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

## Skills (Slash Commands)

All agent roles are implemented as Claude Code skills in `.claude/skills/`.

| Command                | Purpose                                   | When to Use                                 |
| ---------------------- | ----------------------------------------- | ------------------------------------------- |
| `/orchestrate [task]`  | Plan, delegate, coordinate                | Starting any non-trivial task               |
| `/plan [feature]`      | Research and generate implementation plan | Architecture decisions, feature scoping     |
| `/implement [subtask]` | Write code in a focused scope             | Executing a specific subtask from a plan    |
| `/verify [scope]`      | Run tests, lint, quality checks           | After implementation to confirm correctness |
| `/debug [bug]`         | Reproduce, root-cause, fix a bug          | Encountering crashes or incorrect behavior  |
| `/batch`               | Send work to Batch API (built-in)         | Non-priority work (docs, tests, reviews)    |

## Batch API Routing (MANDATORY)

This project uses the MCP `claude-batch` server (`send_to_batch`) for non-priority work at 50% cost. **Default to batching** unless the task is blocking current implementation.

### Always Batch (never interactive)

| Task Type         | Example                                          |
| ----------------- | ------------------------------------------------ |
| Code review       | "Review these 5 files for quality issues"        |
| Test authoring    | "Write unit tests for AlertManager"              |
| Documentation     | "Update HANDOFF.md with Phase 2 summary"         |
| Refactor analysis | "Identify dead code in src/efferve/"             |
| Debug research    | "Analyze this error log and suggest root causes" |
| Lint/style audit  | "Check these files against our style rules"      |

### Always Interactive (never batch)

| Task Type             | Example                                  |
| --------------------- | ---------------------------------------- |
| Active implementation | Writing code for the current task        |
| Test execution        | Running existing tests to verify changes |
| Blocking bug fixes    | Fix needed before work can continue      |
| Git operations        | Commit, push, branch, merge              |
| User Q&A              | Answering questions, making decisions    |

### Session Protocol

1. **Start**: Run `batch_list` to check for completed jobs from prior sessions; fetch and integrate results
2. **During**: As non-priority tasks surface, `send_to_batch` immediately instead of deferring
3. **End**: Batch any remaining non-priority tasks; note pending jobs in HANDOFF.md

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
├── main.py              # FastAPI app entrypoint, multi-sniffer lifecycle
├── config.py            # pydantic-settings configuration
├── database.py          # SQLModel engine and session management
├── sniffer/             # WiFi capture backends
│   ├── base.py          # BaseSniffer ABC + BeaconEvent dataclass
│   ├── mock.py          # Mock sniffer for dev/testing
│   ├── monitor.py       # Monitor mode via scapy (raw packet capture)
│   ├── ruckus.py        # Ruckus Unleashed polling (aioruckus)
│   ├── glinet.py        # GL.iNet remote monitor (SSH + tcpdump + scapy)
│   ├── opnsense.py      # OPNsense DHCP lease polling
│   └── test_connection.py # Connection testing for all backends
├── registry/            # Device detection, fingerprinting, household filtering
│   ├── models.py        # Device SQLModel
│   └── store.py         # CRUD operations + classification
├── persona/             # Device-to-person association (stub)
│   └── engine.py        # Persona logic (not yet implemented)
├── alerts/              # Presence-based notifications (stub)
│   └── manager.py       # Alert rules and dispatch (not yet implemented)
├── api/                 # FastAPI route handlers (JSON API)
│   └── routes.py        # REST endpoints
└── ui/                  # Server-rendered dashboard
    ├── routes.py        # UI route handlers
    └── templates/       # Jinja2 + HTMX templates
tests/                   # Mirrors src/ structure (86 tests)
data/                    # SQLite database (gitignored); config is .env only
.claude/skills/          # Agent skill definitions (orchestrate, plan, implement, verify, debug)
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
- Don’t push any code to a public repository.
