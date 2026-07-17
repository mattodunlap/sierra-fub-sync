# Sierra → FUB Auto-Login URL Sync

Pulls each Sierra lead's auto-login URL into a Follow Up Boss custom field so it can be merged into email and text templates.

## Files

- `sierra_fub_sync.py` — polling script. Runs on a schedule, scans all leads, updates FUB. Use this for the initial backfill and as the steady-state sync.
- `.github/workflows/sync.yml` — GitHub Actions workflow that runs the polling script every 5 minutes for free.
- `webhook_handler.py` — FastAPI app that handles Sierra webhooks for real-time updates on new lead registrations. Runs on Fly.io (`fly.toml` + `Dockerfile`).

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

**Webhook**: deployed on Fly.io. `fly apps create sierra-fub-webhook`, `fly secrets set SIERRA_API_KEY=... FUB_API_KEY=... WEBHOOK_SECRET=...`, then `fly deploy`. In Sierra, point the webhook at `https://sierra-fub-webhook.fly.dev/sierra-webhook` with the `X-Webhook-Secret` header set to your `WEBHOOK_SECRET`. Full runbook (including droplet decommissioning) in `DEPLOY.md`.

## Using the field in FUB templates

In any email or text template, insert the merge field for "Sierra Login URL". For email, wrap it in anchor text. For SMS, run the URL through a branded shortener (Bitly w/ custom domain, Short.io) before sending.
