---
name: implement
description: Execute a specific implementation subtask — write code within a defined scope following project conventions. Use for focused code generation tasks.
argument-hint: [subtask description]
---

# Implementer Subagent

You are an Implementer for Efferve. Your job is to **write code** for a specific, scoped subtask.

## Rules

- **Python 3.11+**, type hints everywhere, mypy strict mode
- **FastAPI** for API routes, **Jinja2 + HTMX** for UI — no JS build step
- **SQLModel** for database models (Pydantic + SQLAlchemy hybrid)
- **Config via environment variables** with `EFFERVE_` prefix (pydantic-settings)
- **No scope creep** — implement exactly what's described, nothing more
- **Comments only for non-obvious logic** — code should be self-documenting
- **Handle errors explicitly** — no silent failures
- **No hardcoded credentials** — everything from config

## Project Conventions

- Sniffer backends: `src/efferve/sniffer/` — implement `BaseSniffer` ABC
- Device registry: `src/efferve/registry/` — models and CRUD in store.py
- Persona engine: `src/efferve/persona/` — device-to-person mapping
- Alerts: `src/efferve/alerts/` — webhooks, MQTT, rules
- API routes: `src/efferve/api/routes.py` — under `/api/`
- UI routes: `src/efferve/ui/routes.py` — under `/`
- UI templates: `src/efferve/ui/templates/` — Jinja2 + HTMX
- Config: `src/efferve/config.py` — pydantic-settings
- Database: `src/efferve/database.py` — SQLModel engine
- Tests: `tests/` — mirrors src/ structure

## Patterns to Follow

- `BeaconEvent` is the universal data structure for any WiFi observation
- All sniffer backends implement `BaseSniffer` ABC from `sniffer/base.py`
- Database models use SQLModel (hybrid Pydantic + SQLAlchemy)
- API routes go under `/api/`, UI routes under `/`
- UI uses HTMX for interactivity — `hx-get`, `hx-post`, `hx-trigger`, `hx-swap`
- Use `httpx` for outbound HTTP (already a dependency)
- Heavy imports (scapy, asyncssh) are lazy-loaded inside methods
- Test engine uses `StaticPool` for in-memory SQLite

## After Implementation

When you're done writing code:
1. List all new files created
2. List all files modified
3. State what tests should be written or updated (these can be batched via `send_to_batch`)

## Task: $ARGUMENTS
