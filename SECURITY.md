# Security

## Secrets and credentials

- **Never commit secrets.** Router/AP credentials, API keys, and webhook URLs are sensitive.
- **Where they live:** All secrets and configuration live in the **`.env`** file (and/or process environment). `.env` is gitignored.
- **Setup:** Copy `.env.example` to `.env` and fill in values locally; or use the in-app setup wizard, which writes `EFFERVE_*` variables to `.env`. Do not add `.env` to version control. If you previously used `data/config.json`, copy its values into `.env` (variable names match `.env.example`) and you can remove `config.json`.
- **Before making the repo public:** Ensure `.env` has never been committed. Run `git log -p --all -- .env`; output should be empty. Optional: run a secret scanner (e.g. [gitleaks](https://github.com/gitleaks/gitleaks)) on the repo.

## Webhooks

- Alert webhook URLs are validated to block SSRF: no localhost or private/internal IPs. See `efferve.alerts.manager.validate_webhook_url`.
