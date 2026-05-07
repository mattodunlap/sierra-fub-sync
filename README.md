# Sierra → FUB Auto-Login URL Sync

Pulls each Sierra lead's auto-login URL into a Follow Up Boss custom field so it can be merged into email and text templates.

## Files

- `sierra_fub_sync.py` — polling script. Runs on a schedule, scans all leads, updates FUB. Use this for the initial backfill and as the steady-state sync.
- `.github/workflows/sync.yml` — GitHub Actions workflow that runs the polling script every 30 minutes for free.
- `webhook_handler.py` — FastAPI app that handles Sierra webhooks for real-time updates on new lead registrations. Optional but recommended once polling is stable.

## Required environment variables / GitHub Secrets

| Name | Where it comes from |
|---|---|
| `SIERRA_API_KEY` | Sierra Admin → Integrations → Direct API |
| `FUB_API_KEY` | FUB Admin Settings → API (must be account-owner key) |
| `SIERRA_LOGIN_FIELD` | JSON field name from Sierra's `/leads/get` response — usually `siteLoginUrl` |
| `FUB_CUSTOM_FIELD` | Custom field API name from `GET /v1/customFields` — usually `customSierraLoginUrl` |
| `WEBHOOK_SECRET` | (webhook only) Any random string; you set it once in Sierra and here |

## Deployment quick-reference

**Polling**: push this repo to GitHub (private), add the four secrets under Settings → Secrets and variables → Actions, done. The workflow will run every 30 min.

**Webhook**: deploy `webhook_handler.py` to Render or Railway free tier, set the env vars there, then in Sierra add a webhook pointed at `https://yourapp.onrender.com/sierra-webhook` with the `X-Webhook-Secret` header set to your `WEBHOOK_SECRET`.

## Using the field in FUB templates

In any email or text template, insert the merge field for "Sierra Login URL". For email, wrap it in anchor text. For SMS, run the URL through a branded shortener (Bitly w/ custom domain, Short.io) before sending.
