# Deployment Guide

Two pieces to deploy:

1. **GitHub Actions polling sync** — the catch-everything backstop, runs every 5 min
2. **Fly.io webhook** — real-time updates for new lead registrations

Both pieces share the same GitHub repo. Set up the repo first.

## 1. Push to a private GitHub repo

If you don't have a GitHub account yet, sign up at https://github.com (free).

```bash
# In your project folder, open Command Prompt and run:
cd "C:\Users\matto\OneDrive\Documents\Claude\Projects\Auto Login Link From Sierra To FUB"
git init
git add .
git commit -m "Initial commit"
```

Then on github.com:

1. Click the **+** in the top right → **New repository**
2. Name it: `sierra-fub-sync`
3. Set it to **Private** (very important — your `.env` is gitignored, but private adds defense in depth)
4. Don't add a README, .gitignore, or license (we already have one)
5. Click **Create repository**
6. On the next page, GitHub shows you commands. Use the **"…or push an existing repository from the command line"** block:

```bash
git remote add origin https://github.com/YOUR_USERNAME/sierra-fub-sync.git
git branch -M main
git push -u origin main
```

If git asks for credentials, use a personal access token (Settings → Developer Settings → Personal Access Tokens → Tokens (classic) → Generate new token, give it `repo` scope).

## 2. Configure GitHub Actions secrets (for polling)

In your new repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.

Add these four:

| Name | Value |
|---|---|
| `SIERRA_API_KEY` | (your Sierra key) |
| `FUB_API_KEY` | (your FUB key) |
| `FUB_CUSTOM_FIELD` | `customSierraSearchURL` |
| `SIERRA_ORIGINATING_SYSTEM` | `FUB-AutoLogin-Sync` |

The workflow will run automatically every 5 min. To run it once manually right now: **Actions** tab → **Sierra-FUB Sync** → **Run workflow**.

## 3. Deploy webhook to Fly.io

The webhook runs as a small always-on machine on Fly.io. Config lives in `fly.toml` and `Dockerfile` — you shouldn't need to touch either.

One-time setup:

1. Sign up at https://fly.io and install flyctl: https://fly.io/docs/flyctl/install/
   - Windows (PowerShell): `pwsh -Command "iwr https://fly.io/install.ps1 -useb | iex"`
2. Log in: `fly auth login`
3. From the project folder, create the app (the name is taken from `fly.toml`):

```bash
fly apps create sierra-fub-webhook
```

   If the name is taken globally, pick another (e.g. `dunlap-sierra-fub-webhook`) and update the `app = ` line in `fly.toml` to match.

4. Set the secrets (one command, all three):

```bash
fly secrets set SIERRA_API_KEY="your-sierra-key" FUB_API_KEY="your-fub-key" WEBHOOK_SECRET="any-random-string"
```

   `WEBHOOK_SECRET` can be any random string (e.g., a UUID — generate at https://www.uuidgenerator.net). Non-secret config (`FUB_CUSTOM_FIELD`, `SIERRA_ORIGINATING_SYSTEM`) is already set in `fly.toml` under `[env]`.

5. Deploy:

```bash
fly deploy --ha=false
```

   (`--ha=false` keeps it to a single machine — one is plenty for webhook volume, and it halves the cost. Only needed the first time; later deploys are just `fly deploy`.)

6. Test it: open `https://sierra-fub-webhook.fly.dev/` in a browser. Should show `{"status":"ok"}`. That confirms the service is up.

To ship changes later: edit `webhook_handler.py`, commit, and run `fly deploy` again. `fly logs` tails live request logs; `fly status` shows machine health.

`fly.toml` keeps `min_machines_running = 1`, so there is no cold start — webhooks are handled within seconds, always.

## 4. Configure Sierra to send webhooks

1. Sierra Admin → **Integrations** → look for **Webhooks** (might be under Direct API)
2. Add a new webhook:
   - **Event:** "New Lead Registration" (or equivalent — pick the event for new lead creation)
   - **URL:** `https://sierra-fub-webhook.fly.dev/sierra-webhook`
   - **Custom Header:** key=`X-Webhook-Secret`, value=(the same `WEBHOOK_SECRET` you set with `fly secrets set`)
3. Save
4. To test: register a fake lead on your IDX site (use a private/incognito browser, fake name, real-looking email you control). Within seconds, the FUB contact should be created with the auto-login URL already populated. Or run `python test_webhook.py` (needs `WEBHOOK_SECRET` in your local `.env`).

If Sierra doesn't show a webhooks UI, email support@sierrainteractive.com:
> "How do I configure outbound webhooks for new lead registrations? I want to send a POST request to my own endpoint when a new lead registers, including the lead ID in the payload."

## 5. Verify the whole stack

After deploying, verify:

- [ ] `run_full_backfill.bat` finished successfully (existing leads have URLs in FUB)
- [ ] GitHub Actions ran a successful sync (Actions tab shows green)
- [ ] `fly status` shows the machine as `started` and `https://sierra-fub-webhook.fly.dev/` returns OK
- [ ] Sierra webhook test fires correctly (`fly logs` shows the incoming POST and its result)
- [ ] FUB email template merge tag resolves to the correct URL when sent

## Migrating off the old DigitalOcean droplet

The webhook used to run on a DigitalOcean droplet. Cutover order matters — don't kill the droplet until Fly is confirmed receiving Sierra's webhooks:

1. Deploy to Fly (section 3) and confirm `https://sierra-fub-webhook.fly.dev/` returns `{"status":"ok"}`.
2. **Rotate the webhook secret.** The old secret was committed to this repo in an earlier version of `test_webhook.py`, so treat it as burned. Generate a fresh UUID and run `fly secrets set WEBHOOK_SECRET="new-value"` (this restarts the machine automatically). Put the same value in your local `.env`.
3. In Sierra Admin, edit the existing webhook: change the URL to `https://sierra-fub-webhook.fly.dev/sierra-webhook` and the `X-Webhook-Secret` header to the new secret. From this moment Fly is live and the droplet stops receiving traffic.
4. Verify end-to-end: run `python test_webhook.py`, then register a fake lead on the IDX site and watch `fly logs` — you should see the POST arrive and the FUB contact get the URL fields.
5. Let both run for a day or two if you want a safety net; the droplet receives nothing but costs nothing extra while it idles.
6. Decommission the droplet: DigitalOcean control panel → the droplet → **Destroy** → "Destroy this Droplet" (destroying, not just powering off, is what stops billing). If anything else runs on that droplet, just stop the webhook service instead (`systemctl disable --now <service>`) and leave the droplet up.
7. Optional cleanup: delete any DNS record that pointed at the droplet's IP, and revoke/rotate the Sierra + FUB API keys that lived on it if you're unsure who had access.

## Troubleshooting

**`fly deploy` fails or the app won't start**: run `fly logs` — a Python `KeyError` on startup means a missing secret (`SIERRA_API_KEY` and `FUB_API_KEY` are required). `fly secrets list` shows what's set (names only, values stay hidden).

**Webhook returns 401**: the `X-Webhook-Secret` header from Sierra doesn't match `WEBHOOK_SECRET` on Fly. Fix by aligning them (`fly secrets set WEBHOOK_SECRET=...` and update the header in Sierra).

**Machine shows stopped**: `fly.toml` sets `min_machines_running = 1`, so the Fly proxy keeps one machine up and restarts it if it crashes. If it's stuck, `fly machine restart` or `fly deploy` brings it back.
