# Deployment Guide

Two pieces to deploy:

1. **GitHub Actions polling sync** — the catch-everything backstop, runs every 5 min
2. **Fly.io URL populator** — near-real-time (60s) URL population for new lead registrations

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

## 3. Deploy the URL populator to Fly.io

Real-time URL population runs as a tiny always-on Fly machine (`url_populator.py`): every 60 seconds it polls FUB for newly-created leads and fills in `customSierraSearchURL` + `customSierraAdminURL`. It has **no public endpoint** — nothing to secure, no webhook secret, and no Sierra webhook subscription to get silently banned. Config lives in `fly.toml` and `Dockerfile`.

### Option A — from GitHub Actions (recommended, no local tooling)

1. Create a Fly org token: https://fly.io/dashboard → Tokens (an **org** token, so the workflow can create the app; app-scoped deploy tokens can't).
2. Repo → Settings → Secrets and variables → Actions → add `FLY_API_TOKEN` = that token.
3. Actions tab → **Deploy URL populator to Fly** → Run workflow.

That one run creates the app, sets the Fly secrets from the repo's existing `SIERRA_API_KEY`/`FUB_API_KEY` secrets, deploys, and confirms the machine is running. After merge, any change to the populator auto-deploys on push to `main`.

### Option B — from your machine

1. Sign up at https://fly.io and install flyctl: https://fly.io/docs/flyctl/install/
2. `fly auth login`
3. From the project folder:

```bash
fly apps create sierra-fub-sync
fly secrets set SIERRA_API_KEY="your-sierra-key" FUB_API_KEY="your-fub-key"
fly deploy --ha=false
```

   If the app name is taken globally, pick another and update the `app = ` line in `fly.toml` to match. (`--ha=false` keeps it to a single machine — one is plenty; only needed the first time.)

4. Watch it work: `fly logs` shows a poll pass every 60s and a line per lead it populates. `fly status` shows machine health.

## 4. No Sierra webhook needed

The poller replaces the old LeadRegistered webhook on purpose: Sierra silently bans webhook subscriptions after 4 failed/slow deliveries (it banned this project's Render subscription on 2026-06-01), and a banned subscription fails silently. Polling FUB every 60s gets effectively the same latency with nothing to ban and no public attack surface.

If you ever want true seconds-level latency back, `webhook_handler.py` is still in the image — run it with `uvicorn webhook_handler:app`, add an `[http_service]` block to `fly.toml`, set `WEBHOOK_SECRET`, and register with `register_sierra_webhook.py`. Not recommended unless something actually needs it.

## 5. Verify the whole stack

- [ ] GitHub Actions ran a successful sync (Actions tab shows green)
- [ ] `fly status` shows the machine `started`; `fly logs` shows poll passes
- [ ] Register a fake lead on the IDX site (private/incognito browser, fake name, real-looking email you control) — within ~2 minutes the FUB contact should have `customSierraSearchURL` + `customSierraAdminURL` populated
- [ ] FUB email template merge tag resolves to the correct URL when sent

## Cutover from the current setup

History, so the steps below make sense: Sierra **banned** the original Render webhook subscription on 2026-06-01 (4 failed deliveries), and since then URL population has been handled by a 1-minute poll bridge on the droplet (`new-lead-url-populate.timer`). The Render app is still deployed but receives nothing. The droplet's direct Sierra API calls are WAF-blocked, so the bridge has been writing homepage fallback URLs instead of filtered saved-search URLs — the Fly poller fixes that (clean IPs).

1. Deploy to Fly (section 3) and confirm `fly logs` shows poll passes.
2. Verify end-to-end with a fake IDX lead (section 5).
3. Turn off the droplet poll bridge: `systemctl --user disable --now new-lead-url-populate.timer` (redundant now — the 5-min GitHub Actions sync stays as the backstop).
4. Delete the Render service: https://dashboard.render.com → the service → Settings → Delete Web Service. It holds Sierra/FUB API keys (and the old burned webhook secret) in its env vars, so it shouldn't outlive the migration.
5. **Repair recent leads**: while the droplet was WAF-blocked, new leads got homepage URLs instead of filtered saved-search URLs. One-time fix for the last ~3 weeks:

```bash
fly ssh console -C "python url_populator.py --once --since-minutes 30000"
```

6. Optional cleanup: rotate the Sierra + FUB API keys that lived on Render if you're unsure who had access.

## Troubleshooting

**`fly deploy` fails or the app won't start**: run `fly logs` — a Python `KeyError` on startup means a missing secret (`SIERRA_API_KEY` and `FUB_API_KEY` are required). `fly secrets list` shows what's set (names only, values stay hidden).

**Leads not getting URLs**: `fly logs` should show a poll pass every 60s. If passes run but a lead is skipped with `no sierra id derivable`, the FUB contact has no Sierra URL fields and no email match in Sierra — check the lead exists in Sierra. The 5-min GitHub Actions sync is the backstop either way.

**Machine shows stopped**: `restart.policy = "always"` in `fly.toml` restarts it on crash. If it's stuck, `fly machine restart` or `fly deploy` brings it back.
