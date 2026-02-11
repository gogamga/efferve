# Efferve — Handoff

## Goal
Set up the Efferve project from scratch following the Claude Code Implementation Runbook.

## Current State
All runbook setup steps are complete:
- Global `~/.claude/CLAUDE.md` — populated with user preferences
- Project `CLAUDE.md` — full project definition (stack, roles, architecture, conventions)
- `.claude/settings.json` — ruff auto-format hook
- `.claude/commands/` — commit, pr, plan, handoff, review slash commands
- All CLI tools installed (including tmux)
- Git repo initialized

Scaffold code exists from an early premature start (kept intentionally):
- `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `.env.example`, `.gitignore`
- `src/efferve/main.py`, `config.py`, `database.py`
- `src/efferve/sniffer/base.py`, `sniffer/monitor.py`
- Empty dirs: `registry/`, `persona/`, `alerts/`, `api/`, `ui/templates/`, `tests/`, `data/`

No initial git commit yet — all files are unstaged.

## Key Decisions Made
- **Stack**: Python 3.11+, FastAPI, SQLModel, scapy
- **UI**: Jinja2 + HTMX (no JS build system)
- **DB**: SQLite now, designed for Postgres swap later
- **Capture**: Both monitor mode (scapy) and router API polling
- **Deployment**: Docker-first (NET_ADMIN + NET_RAW caps)
- **Workflow**: Collaborative — Claude proposes, human approves. Plan before code.

## Next Steps
1. Restart Claude Code with `--dangerously-skip-permissions`
2. Review the existing scaffold code for correctness against CLAUDE.md
3. Make the initial git commit
4. Plan the first implementation milestone (sniffer + device registry + basic UI)
