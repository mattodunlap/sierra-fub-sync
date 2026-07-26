# Handoff: deploy the Sierra→FUB URL populator to Fly (run on the laptop)

**You are a session running on Matthew's laptop** (Linux Mint, residential IP, `flyctl` installed and logged in to the `personal` Fly org). Your job: deploy the `sierra-fub-sync` URL populator to Fly.io and confirm it's running. Everything you need is in the `sierra-fub-sync` git repo.

## What this is

A 60-second poll loop (`url_populator.py`) that watches Follow Up Boss for newly-created leads and writes their Sierra auto-login / saved-search URLs into custom fields. It runs as a tiny always-on Fly machine with **no inbound endpoint** (no webhook, nothing for Sierra to ban). This replaces the old droplet poll-bridge timer whose Sierra calls were WAF-blocked.

## Guardrails (important)

- Deploy **only** the app named `sierra-fub-sync` (that's what `fly.toml` says). **Never** deploy this onto `maittrix-engine` or `dunlap-automation` — a `flyctl deploy` replaces the target app's image, and clobbering the engine would take down live sending. The script `deploy_fly.sh` refuses to run if `fly.toml`'s app is either of those, but don't override it.
- This app talks only to the FUB and Sierra **REST APIs** with API keys. It does no browser automation and needs no cookies.

## Steps

1. **Get the repo on the migration branch** (or `main` if it's already merged):
   ```bash
   cd ~/sierra-fub-sync        # or wherever the clone lives; clone it if missing:
   # git clone https://github.com/mattodunlap/sierra-fub-sync.git ~/sierra-fub-sync && cd ~/sierra-fub-sync
   git fetch origin
   git checkout claude/fub-fly-migration-7qyfhf
   git pull --ff-only origin claude/fub-fly-migration-7qyfhf
   ```

2. **Confirm Fly auth** (should already be logged in):
   ```bash
   flyctl auth whoami          # if this errors: fly auth login  (pick the 'personal' org)
   ```

3. **Run the deploy.** It reads `SIERRA_API_KEY` / `FUB_API_KEY` from the environment, then `./.env`, then `~/automation/.env` (that's where the automation stack keeps them). If they're somewhere else, pass them inline.
   ```bash
   ./deploy_fly.sh
   # or, if the keys aren't in any .env it can find:
   # SIERRA_API_KEY=... FUB_API_KEY=... ./deploy_fly.sh
   ```
   The script creates the app if needed, stages the secrets, deploys `--ha=false` (single machine), and tails the logs.

## Verify (definition of done)

- `flyctl status --app sierra-fub-sync` shows the machine `started`.
- `flyctl logs --app sierra-fub-sync` prints, about once a minute:
  - `url_populator: polling FUB every 60s, lookback 30 min`
  - `pass: N recent FUB people, M need URLs` (the `pass:` line only appears when there are recent leads; a quiet minute with no new leads is normal)
- Sanity end-to-end (optional): register a test lead on the IDX site, wait ~2 min, confirm its FUB contact gets `customSierraSearchURL` + `customSierraAdminURL`.

## After it's confirmed running

1. **Stop the old droplet bridge** so the two don't both run (on the droplet, not the laptop):
   ```bash
   systemctl --user disable --now new-lead-url-populate.timer
   ```
2. **Delete the old Render service** (Render dashboard → the service → Settings → Delete). It still holds API keys in its env.
3. **Repair the leads written while the droplet was WAF-blocked** (they got homepage URLs instead of filtered saved-search URLs). One-time pass, from clean egress:
   ```bash
   flyctl ssh console --app sierra-fub-sync -C 'python url_populator.py --once --since-minutes 30000'
   ```
4. Merge PR #5 so `main` reflects the deployed code (future handler changes then auto-deploy via `.github/workflows/fly_deploy.yml` if `FLY_API_TOKEN` is ever added to Actions).

Report back: the `flyctl status` output and a few log lines showing the poll loop, so we know it's live.
