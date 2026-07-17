# Sierra → FUB Auto-Login URL Sync

Pulls each Sierra lead's auto-login URL into a Follow Up Boss custom field so it can be merged into email and text templates.

## Files

- `sierra_fub_sync.py` — polling script. Runs on a schedule, scans all leads, updates FUB. Use this for the initial backfill and as the steady-state sync.
- `.github/workflows/sync.yml` — GitHub Actions workflow that runs the polling script every 5 minutes for free.
- `url_populator.py` — 60-second FUB poll loop that populates URLs on newly-created leads. Runs on Fly.io (`fly.toml` + `Dockerfile`, deployed by `.github/workflows/fly_deploy.yml`). No public endpoint.
- `webhook_handler.py` — the shared Sierra/FUB helpers, plus an optional FastAPI webhook receiver (not deployed by default — Sierra bans webhook subscriptions too easily; the poller replaces it).

## Required environment variables / GitHub Secrets

| Name | Where it comes from |
|---|---|
| `SIERRA_API_KEY` | Sierra Admin → Integrations → Direct API |
| `FUB_API_KEY` | FUB Admin Settings → API (must be account-owner key) |
| `SIERRA_LOGIN_FIELD` | JSON field name from Sierra's `/leads/get` response — usually `siteLoginUrl` |
| `FUB_CUSTOM_FIELD` | Custom field API name from `GET /v1/customFields` — usually `customSierraSearchURL` |
| `WEBHOOK_SECRET` | (webhook only) Any random string; you set it once in Sierra and here |

## Deployment quick-reference

**Polling**: push this repo to GitHub (private), add the four secrets under Settings → Secrets and variables → Actions, done. The workflow will run every 5 min.

**URL populator**: deployed on Fly.io via the **Deploy URL populator to Fly** GitHub Actions workflow (needs `FLY_API_TOKEN` in Actions secrets), or locally: `fly apps create sierra-fub-sync`, `fly secrets set SIERRA_API_KEY=... FUB_API_KEY=...`, `fly deploy --ha=false`. No Sierra webhook needed. Full runbook and cutover steps in `DEPLOY.md`.

## Using the field in FUB templates

In any email or text template, insert the merge field for "Sierra Login URL". For email, wrap it in anchor text. For SMS, run the URL through a branded shortener (Bitly w/ custom domain, Short.io) before sending.
