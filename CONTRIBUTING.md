# Contributing

Thanks for your interest in Efferve.

## Development Setup

```bash
cp .env.example .env
uv sync
```

Run the app:

```bash
uv run uvicorn efferve.main:app --reload
```

## Test and Lint Before PRs

```bash
uv run pytest
uv run ruff check src tests
```

## Scope and Style

- Keep changes focused and minimal.
- Preserve strict typing and existing architecture patterns.
- Avoid introducing a frontend build system (UI is Jinja2 + HTMX).
- Do not commit secrets or environment files.

## Security

- Report vulnerabilities privately.
- Follow `SECURITY.md` for secret handling and webhook constraints.
